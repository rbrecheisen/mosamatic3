from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create the configured admin user if it does not already exist.'

    def _get_initial_password(self) -> str:
        password_file = getattr(settings, 'ADMIN_PASSWORD_FILE', None)

        if password_file is not None and password_file.exists():
            password = password_file.read_text(encoding='utf-8').strip()
        else:
            password = getattr(settings, 'ADMIN_PASSWORD', 'admin').strip()

        if not password:
            raise RuntimeError('Could not load initial admin password')

        return password

    def handle(self, *args, **options):
        password = self._get_initial_password()

        user, created = User.objects.get_or_create(
            username=settings.ADMIN_USERNAME,
            defaults={
                'email': settings.ADMIN_USERNAME,
            },
        )

        if created:
            user.set_password(password)

        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.save()

        action = 'Created' if created else 'Found existing'
        self.stdout.write(
            self.style.SUCCESS(f'{action} admin user {user.username}')
        )