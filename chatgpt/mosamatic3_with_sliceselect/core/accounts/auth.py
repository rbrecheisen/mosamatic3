from datetime import datetime, timedelta, timezone
import jwt
from django.conf import settings
from django.contrib.auth.models import User
from rest_framework import authentication, exceptions

ALGORITHM = 'HS256'

def create_access_token(subject: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({'sub': subject, 'exp': expires}, settings.SECRET_KEY, algorithm=ALGORITHM)

class BearerJWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        header = authentication.get_authorization_header(request).decode('utf-8')
        if not header:
            return None
        parts = header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return None
        token = parts[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get('sub')
        except jwt.PyJWTError as exc:
            raise exceptions.AuthenticationFailed('Could not validate credentials') from exc
        if not username:
            raise exceptions.AuthenticationFailed('Could not validate credentials')
        try:
            user = User.objects.get(username=username, is_active=True)
        except User.DoesNotExist as exc:
            raise exceptions.AuthenticationFailed('Could not validate credentials') from exc
        return (user, None)
