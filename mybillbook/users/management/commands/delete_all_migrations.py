import os
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = "Delete all migration files across the project"

    def handle(self, *args, **kwargs):
        deleted_count = 0
        skipped_count = 0
        project_root = settings.BASE_DIR  # Root directory of the project

        # Traverse all apps in the project
        for root, dirs, files in os.walk(project_root):
            if root.endswith('migrations'):
                # Ignore the `__init__.py` file and only delete actual migration files
                migration_files = [f for f in files if f.endswith('.py') and f != '__init__.py']

                for migration_file in migration_files:
                    migration_file_path = os.path.join(root, migration_file)
                    try:
                        os.remove(migration_file_path)
                        deleted_count += 1
                        self.stdout.write(self.style.SUCCESS(f"Deleted: {migration_file_path}"))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error deleting {migration_file_path}: {str(e)}"))
                        skipped_count += 1

        self.stdout.write(self.style.SUCCESS(f"✅ Total migrations deleted: {deleted_count}"))
        self.stdout.write(self.style.WARNING(f"⚠️ Skipped {skipped_count} files due to errors"))
