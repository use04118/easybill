from django.core.management.base import BaseCommand
from django.apps import apps
from django.core.management import call_command
from django.db.migrations.recorder import MigrationRecorder
from django.db import connection


class Command(BaseCommand):
    help = 'Unapplies all migrations (migrate to zero) for every app except user-related apps and their dependencies'

    def handle(self, *args, **options):
        # List of apps to exclude from migration zero
        excluded_apps = [
            'users',           # Main users app
            'auth',           # Authentication framework
            'contenttypes',   # Content types framework (used by auth)
            'sessions',       # Session framework (used by auth)
            'admin',          # Admin interface (uses auth)
            'django.contrib.auth',  # Full path for auth
            'django.contrib.contenttypes',  # Full path for contenttypes
            'django.contrib.sessions',  # Full path for sessions
            'django.contrib.admin',  # Full path for admin
        ]
        
        recorder = MigrationRecorder(connection)
        applied_migrations = recorder.applied_migrations()
        apps_with_migrations = {app_label for app_label, _ in applied_migrations}

        # Filter out the excluded apps
        apps_to_migrate_zero = [app for app in apps_with_migrations if app not in excluded_apps]

        if not apps_to_migrate_zero:
            self.stdout.write(self.style.WARNING("No applicable migrations found to revert."))
            return

        # Unapply migrations for each app, skipping the excluded ones
        for app_label in sorted(apps_to_migrate_zero):
            self.stdout.write(self.style.NOTICE(f"Unapplying all migrations for '{app_label}'..."))
            try:
                call_command('migrate', app_label, 'zero', verbosity=0)
                self.stdout.write(self.style.SUCCESS(f"Successfully migrated '{app_label}' to zero."))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error while migrating '{app_label}' to zero: {e}"))
