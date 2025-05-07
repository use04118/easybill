from users.models import Business, Role,User,SubscriptionPlan,Subscription,AuditLog,StaffInvite
from users.utils import get_current_business
from rest_framework import permissions
from datetime import timedelta
from django.utils import timezone

class HasGodownPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        business = get_current_business(user)

        if not business:
            return False

        role = Role.objects.filter(user=user, business=business).first()
        if not role:
            return False

        # ✅ Wildcard admin shortcut
        if "*" in role.permissions and role.permissions["*"]:
            return True

        method = view.request.method
        permission_key = None

        if method in ['GET']:
            permission_key = 'godown.view'
        elif method in ['POST']:
            permission_key = 'godown.create'
        elif method in [ 'PUT', 'PATCH']:
            permission_key = 'godown.edit'
        elif method == 'DELETE':
            permission_key = 'godown.delete'

        return role.permissions.get(permission_key, False)
    