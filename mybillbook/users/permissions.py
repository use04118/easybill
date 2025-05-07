from .utils import get_current_business
from rest_framework import permissions
from .models import Role,Subscription
from datetime import timedelta
from django.utils import timezone

ROLE_PERMISSIONS = {
    "admin": ["*"],

    "partner": [
        "sales.*", "purchase.*", "expenses.*", "stock.*", "items.*",
        "customers.*", "suppliers.*", "reports.*", "settings.*",
        "users.manage", "reminders.*", "sms.marketing",
        "cashbank.*", "payroll.*", "einvoice.*", "parties.*"
    ],

    "accountant": [
        "sales.*", "purchase.*", "expenses.*",
        "reports.*", "einvoice.*", "cashbank.*", "parties.*"
    ],

    "salesman": [
        "sales.view", "sales.create",
        "expenses.create", "customers.create",
        "rating", "referral"
    ],

    "stock_manager": [
        "items.*", "stock.create",
        "purchase.create", "bulk_upload",
        "rating"
    ],

    "delivery_boy": [
        "sales.view", "expenses.create"
    ]
}


def generate_permissions(role_name):
    if role_name == "admin":
        return {"*": True}

    allowed = ROLE_PERMISSIONS.get(role_name, [])
    permissions = {}

    for perm in allowed:
        if perm.endswith(".*"):
            category = perm.split(".")[0]
            permissions[category] = {"*": True}
        elif "." in perm:
            category, action = perm.split(".", 1)
            if category not in permissions:
                permissions[category] = {}
            permissions[category][action] = True
        else:
            # Single feature/flag permission (like "referral", "rating")
            permissions[perm] = True

    return permissions

class IsBusinessAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        business = get_current_business(request.user)
        return Role.objects.filter(user=request.user, business=business, role_name='admin').exists()

class IsSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_staff and request.user.is_superuser   

def activate_subscription(business, plan):
    now = timezone.now()
    end = now + timedelta(days=plan.duration_days)
    subscription, created = Subscription.objects.update_or_create(
        business=business,
        defaults={"plan": plan, "start_date": now, "end_date": end, "is_active": True}
    )
    return subscription

