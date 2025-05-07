from django.core.management.base import BaseCommand
from godown.models import State


class Command(BaseCommand):
    help = 'Seeds the database with Indian states'

    def handle(self, *args, **options):
        states_data = [
            {"name": "Andaman & Nicobar Islands"},
            {"name": "Andhra Pradesh"},
            {"name": "Arunachal Pradesh"},
            {"name": "Assam"},
            {"name": "Bihar"},
            {"name": "Chandigarh"},
            {"name": "Chhattisgarh"},
            {"name": "Dadra & Nagar Haveli & Daman & Diu"},
            {"name": "Delhi"},
            {"name": "Goa"},
            {"name": "Gujarat"},
            {"name": "Haryana"},
            {"name": "Himachal Pradesh"},
            {"name": "Jammu & Kashmir"},
            {"name": "Jharkhand"},
            {"name": "Karnataka"},
            {"name": "Kerala"},
            {"name": "Ladakh"},
            {"name": "Lakshadweep"},
            {"name": "Madhya Pradesh"},
            {"name": "Maharashtra"},
            {"name": "Manipur"},
            {"name": "Meghalaya"},
            {"name": "Mizoram"},
            {"name": "Nagaland"},
            {"name": "Odisha"},
            {"name": "Puducherry"},
            {"name": "Punjab"},
            {"name": "Rajasthan"},
            {"name": "Sikkim"},
            {"name": "Tamil Nadu"},
            {"name": "Telangana"},
            {"name": "Tripura"},
            {"name": "Uttar Pradesh"},
            {"name": "Uttarakhand"},
            {"name": "West Bengal"},
            {"name": "Dadra & Nagar Haveli"},
            {"name": "Daman & Diu"}
        ]
        
        created_count = 0
        for state_data in states_data:
            state, created = State.objects.get_or_create(**state_data)
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created state: {state.name}'))
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {created_count} new states')) 