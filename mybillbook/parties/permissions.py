from users.models import Business, Role,User,SubscriptionPlan,Subscription,AuditLog,StaffInvite
from users.utils import get_current_business
from rest_framework import permissions
from datetime import timedelta
from django.utils import timezone

class HasPartyPermission(permissions.BasePermission):
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
            permission_key = 'party.view'
        elif method in ['POST', 'PUT', 'PATCH']:
            permission_key = 'party.create'
        elif method == 'DELETE':
            permission_key = 'party.delete'

        return role.permissions.get(permission_key, False)


# class HasPartyPermission(permissions.BasePermission):
#     def has_permission(self, request, view):
#         user = request.user
#         business = get_current_business(user)
#         print(business)
#         if not business:
#             return False

#         role = Role.objects.filter(user=user, business=business).first()
#         print(role)
#         if not role or not role.permissions:
#             return False

#         party_perms = role.permissions.get('party', {})

#         # If category is wildcard
#         if party_perms == {"*": True}:
#             return True

#         method = request.method.upper()
#         if method in ['GET', 'HEAD', 'OPTIONS']:
#             return party_perms.get("view") is True
#         elif method in ['POST']:
#             return party_perms.get("create") is True
#         elif method in ['PUT', 'PATCH']:
#             return party_perms.get("edit") is True
#         elif method == 'DELETE':
#             return party_perms.get("delete") is True

#         return False