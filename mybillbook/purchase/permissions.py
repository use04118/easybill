from users.models import Business, Role,User,SubscriptionPlan,Subscription,AuditLog,StaffInvite
from users.utils import get_current_business
from rest_framework import permissions
from datetime import timedelta
from django.utils import timezone

class HasPurchasePermission(permissions.BasePermission):
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
            permission_key = 'purchase.view'
        elif method in ['POST']:
            permission_key = 'purchase.create'
        elif method in [ 'PUT', 'PATCH']:
            permission_key = 'purchase.edit'
        elif method == 'DELETE':
            permission_key = 'purchase.delete'

        return role.permissions.get(permission_key, False)

class HasDebitNotePermission(permissions.BasePermission):
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
            permission_key = 'debitnote.view'
        elif method in ['POST']:
            permission_key = 'debitnote.create'
        elif method in [ 'PUT', 'PATCH']:
            permission_key = 'debitnote.edit'
        elif method == 'DELETE':
            permission_key = 'debitnote.delete'

        return role.permissions.get(permission_key, False)

class HasPurchaseReturnPermission(permissions.BasePermission):
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
            permission_key = 'purchasereturn.view'
        elif method in ['POST']:
            permission_key = 'purchasereturn.create'
        elif method in [ 'PUT', 'PATCH']:
            permission_key = 'purchasereturn.edit'
        elif method == 'DELETE':
            permission_key = 'purchasereturn.delete'

        return role.permissions.get(permission_key, False)

