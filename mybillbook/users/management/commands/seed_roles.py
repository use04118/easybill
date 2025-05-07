from django.core.management.base import BaseCommand
from users.models import Role
import json

ROLE_PERMISSIONS = {
    "salesman": {"sales.view": True, "sales.create": True},
    "delivery_boy": {"sales.payment_only": True},
    "stock_manager": {"items.create": True, "stock.adjust": True},
    "partner": {"reports.view": True, "expenses.edit": True},
    "admin": {"*": True},
    "accountant": {
        "reports.view": True,
        "purchase.view": True, "purchase.create": True,
        "sales.view": True, "sales.create": True
    },
}

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        for role_name, perms in ROLE_PERMISSIONS.items():
            role, created = Role.objects.get_or_create(
                role_name=role_name, user=None, business=None
            )
            role.permissions = perms
            role.save()
            print(f"{'Created' if created else 'Updated'}: {role_name}")
            
            
    # utils.py or business signals
    def create_default_roles_for_business(user, business):
        for role_name, perms in ROLE_PERMISSIONS.items():
            Role.objects.create(
                user=user,
                business=business,
                role_name=role_name,
                permissions=perms
            )
