from django.core.management.base import BaseCommand
from sales.models import Tds

class Command(BaseCommand):
    help = 'Seed default global TDS entries (visible to all businesses)'

    def handle(self, *args, **kwargs):
        default_tds_list = [
            {"rate": 1.0, "section": "194C", "description": "Payment to Contractor (individuals/ HUF)"},
            {"rate": 2.0, "section": "194C", "description": "Payment to Contractor (others)"},
            {"rate": 5.0, "section": "194D", "description": "Insurance Commission"},
            {"rate": 30.0, "section": "194B", "description": "Lottery / Crossword Puzzle"},
            {"rate": 0.75, "section": "194C", "description": "Payment to Contractor (individuals/ HUF) (Reduced)"},
            {"rate": 1.5, "section": "194C", "description": "Payment to Contractor (others) (reduced)"},
            {"rate": 2.0, "section": "194I", "description": "Rent (Plant / Machinery / Equipment)"},
            {"rate": 2.0, "section": "194J", "description": "Professional Fees / Technical Services / Royalty (technical services)"},
            {"rate": 3.75, "section": "194H", "description": "Commission or Brokerage (Reduced)"},
            {"rate": 7.5, "section": "194", "description": "Dividend (Reduced)"},
            {"rate": 7.5, "section": "194J", "description": "Professional Fees / Technical Services / Royalty (others) (reduced)"},
            {"rate": 10.0, "section": "193", "description": "Interest on Securities"},
            {"rate": 10.0, "section": "194", "description": "Dividend"},
            {"rate": 10.0, "section": "194A", "description": "Interest other than Interest on Securities (by banks)"},
            {"rate": 10.0, "section": "194I", "description": "Rent (Land & Building)"},
            {"rate": 10.0, "section": "194J", "description": "Professional Fees / Technical Services / Royalty (others)"},
            {"rate": 10.0, "section": "194K", "description": "Payment to resident units"},
            {"rate": 0.1, "section": "194Q", "description": "Purchase of goods"},
            {"rate": 2.0, "section": "194H", "description": "Commission or Brokerage"},
        ]

        created_count = 0
        for data in default_tds_list:
            obj, created = Tds.objects.get_or_create(business=None, **data)
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"✅ Seeded {created_count} new TDS entries globally."))
