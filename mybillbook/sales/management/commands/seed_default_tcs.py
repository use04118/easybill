from django.core.management.base import BaseCommand
from sales.models import Tcs

class Command(BaseCommand):
    help = 'Seed default global TCS entries (visible to all businesses)'

    def handle(self, *args, **kwargs):
        default_tcs_list = [
            {"rate": 1.0, "section": None, "description": "Scrap", "condition": None},
            {"rate": 0.1, "section": "206C(IH)", "description": None, "condition": "turnover > 1Cr"},
            {"rate": 5.0, "section": None, "description": "Tendu leaves", "condition": None},
            {"rate": 2.5, "section": None, "description": "Timber wood by any other mode than forest leased", "condition": None},
            {"rate": 1.0, "section": None, "description": "Purchase of Motor vehicle exceeding Rs.10 lakh", "condition": None},
            {"rate": 1.0, "section": None, "description": "Minerals like lignite, coal and iron ore", "condition": None},
            {"rate": 1.0, "section": None, "description": "Liquor of alcoholic nature, made for consumption by humans", "condition": None},
            {"rate": 2.0, "section": None, "description": "Parking lot, Toll Plaza and Mining and Quarrying", "condition": None},
            {"rate": 2.5, "section": None, "description": "Timber wood under a forest leased", "condition": None},
            {"rate": 2.5, "section": None, "description": "Forest produce other than Tendu leaves and timber", "condition": None},
            {"rate": 1.0, "section": "206C(IH)", "description": None, "condition": "turnover > 1Cr (Without PAN)"},
        ]

        created_count = 0
        for data in default_tcs_list:
            obj, created = Tcs.objects.get_or_create(business=None, **data)
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"✅ Seeded {created_count} new TCS entries globally."))
