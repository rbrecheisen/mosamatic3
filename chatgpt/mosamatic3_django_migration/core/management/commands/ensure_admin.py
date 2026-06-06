from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Create or update the configured admin user from ADMIN_PASSWORD_FILE.'

    def handle(self, *args, **options):
        if not settings.ADMIN_PASSWORD_FILE.exists():
            raise RuntimeError(f'Admin password file does not exist: {settings.ADMIN_PASSWORD_FILE}')
        password = settings.ADMIN_PASSWORD_FILE.read_text(encoding='utf-8').strip()
        if not password:
            raise RuntimeError('Could not load admin password')
        user, created = User.objects.get_or_create(username=settings.ADMIN_USERNAME, defaults={'email': settings.ADMIN_USERNAME})
        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.save()
        self.stdout.write(self.style.SUCCESS(('Created' if created else 'Updated') + f' admin user {user.username}'))
