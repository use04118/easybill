from django.core.management.base import BaseCommand
from inventory.models import GSTTaxRate

class Command(BaseCommand):
    help = 'Seed default GST Tax Rates entries'

    def handle(self, *args, **kwargs):
        default_gst_tax_rates = [
            {"rate": 0, "cess_rate": 0, "description": "None"},
            {"rate": 0, "cess_rate": 0, "description": "Exempted"},
            {"rate": 0, "cess_rate": 0, "description": "GST @ 0%"},
            {"rate": 0.1, "cess_rate": 0, "description": "GST @ 0.1%"},
            {"rate": 0.25, "cess_rate": 0, "description": "GST @ 0.25%"},
            {"rate": 1.5, "cess_rate": 0, "description": "GST @ 1.5%"},
            {"rate": 3, "cess_rate": 0, "description": "GST @ 3%"},
            {"rate": 5, "cess_rate": 0, "description": "GST @ 5%"},
            {"rate": 6, "cess_rate": 0, "description": "GST @ 6%"},
            {"rate": 12, "cess_rate": 0, "description": "GST @ 12%"},
            {"rate": 13.8, "cess_rate": 0, "description": "GST @ 13.8%"},
            {"rate": 18, "cess_rate": 0, "description": "GST @ 18%"},
            {"rate": 14, "cess_rate": 12, "description": "GST @ 14% + cess @ 12%"},
            {"rate": 28, "cess_rate": 0, "description": "GST @ 28%"},
            {"rate": 28, "cess_rate": 12, "description": "GST @ 28% + Cess @ 12%"},
            {"rate": 28, "cess_rate": 60, "description": "GST @ 28% + Cess @ 60%"}
        ]

        created_count = 0
        for data in default_gst_tax_rates:
            obj, created = GSTTaxRate.objects.get_or_create(**data)
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"✅ Seeded {created_count} new GST Tax Rate entries globally."))
