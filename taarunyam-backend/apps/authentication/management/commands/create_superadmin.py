import os
from django.core.management.base import BaseCommand
from apps.authentication.models import AdminUser

class Command(BaseCommand):
    help = 'Creates a superadmin if one does not exist.'

    def handle(self, *args, **options):
        if AdminUser.objects.filter(role='superadmin').exists():
            self.stdout.write(self.style.SUCCESS('Superadmin already exists. Skipping.'))
            return

        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123')

        AdminUser.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )

        self.stdout.write(self.style.SUCCESS(f'Successfully created superadmin "{username}" ({email})'))
