"""
Management command to create initial admin user
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from apps.accounts.models import UserProfile


class Command(BaseCommand):
    help = 'Create initial admin user for Meeting Intelligence system'
    
    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='admin', help='Admin username')
        parser.add_argument('--email', type=str, required=True, help='Admin email')
        parser.add_argument('--password', type=str, help='Admin password (will prompt if not provided)')
        parser.add_argument('--first-name', type=str, default='', help='Admin first name')
        parser.add_argument('--last-name', type=str, default='', help='Admin last name')
    
    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']
        first_name = options['first_name']
        last_name = options['last_name']
        
        # Check if admin user already exists
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'User "{username}" already exists')
            )
            return
        
        # Prompt for password if not provided
        if not password:
            import getpass
            password = getpass.getpass('Enter admin password: ')
            confirm_password = getpass.getpass('Confirm admin password: ')
            
            if password != confirm_password:
                self.stdout.write(
                    self.style.ERROR('Passwords do not match')
                )
                return
        
        try:
            # Create admin user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_staff=True,
                is_superuser=True
            )
            
            # Create admin profile
            profile = UserProfile.objects.create(
                user=user,
                role='admin',
                title='System Administrator',
                department='IT'
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully created admin user "{username}" with email "{email}"'
                )
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    'Admin user can now log in to the system and manage other users'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating admin user: {str(e)}')
            )