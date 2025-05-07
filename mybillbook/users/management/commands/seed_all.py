from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Run all seed commands in the project'

    def handle(self, *args, **kwargs):
        seed_commands = [
            'seed_default_gst',  # Inventory app
            'seed_default_unit',  # Inventory app
            'seed_default_tcs',  # Sales app
            'seed_default_tds',  # Sales app
            'import_hsn',  # HSN API app
            'import_sac',  # SAC API app
            'seed_plans',  # Users app
            'seed_roles',  # Users app,
            'seed_states',  # Godown app,
            'celery',
        ]

        for command in seed_commands:
            try:
                self.stdout.write(f"Running seed command: {command}...")
                call_command(command)
                self.stdout.write(self.style.SUCCESS(f"✅ {command} ran successfully."))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ {command} failed with error: {str(e)}"))
