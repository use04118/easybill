from django.core.management.base import BaseCommand
from users.models import SubscriptionPlan
import json

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        plans = [
            {
                "name": "Free Trial",
                "price": 0,
                "duration_days": 14,
                "features": {
                    "invoice_limit": 100,
                    "support": "email_only"
                }
            },
            {
                "name": "Premium Monthly",
                "price": 499,
                "duration_days": 30,
                "features": {
                    "invoice_limit": 1000,
                    "support": "priority",
                    "multi_user": True
                }
            },
            {
                "name": "Premium Annual",
                "price": 4999,
                "duration_days": 365,
                "features": {
                    "invoice_limit": "unlimited",
                    "support": "dedicated",
                    "multi_user": True
                }
            }
        ]

        for plan_data in plans:
            plan, created = SubscriptionPlan.objects.get_or_create(name=plan_data["name"], defaults=plan_data)
            print(f"{'Created' if created else 'Exists'}: {plan.name}")
