from .models import Business, Role,User,SubscriptionPlan,Subscription,AuditLog,StaffInvite
from django.core.cache import cache
from rest_framework.exceptions import NotFound

def has_permission(user, permission):
    if not user or not user.current_business:
        return False

    role = Role.objects.filter(user=user, business=user.current_business).first()
    if not role or not role.permissions:
        return False

    perms = role.permissions
    if perms.get("*"):
        return True
    if perms.get(permission):
        return True

    # Check for wildcard permission like "sales.*"
    for key in perms:
        if key.endswith(".*") and permission.startswith(key[:-2]):
            return True
    return False

def get_current_business(user):
    if not user.current_business:
        raise NotFound("No active business selected")

    try:
        return user.current_business
    except Business.DoesNotExist:
        raise NotFound("Business not found")

def has_subscription_feature(user, feature):
    business = get_current_business(user)
    if not business or not hasattr(business, 'subscription') or not business.subscription.is_active:
        return False

    plan = business.subscription.plan
    return plan.features.get(feature, False)

def has_feature(user, feature_key):
    business = get_current_business(user)
    if not business or not hasattr(business, 'subscription'):
        return False

    features = business.subscription.plan.features
    return features.get(feature_key, False)

def log_action(user, business, action, metadata=None):
    """Log an action in the audit log"""
    # Skip creating audit log if business is None
    if business is None:
        return
        
    AuditLog.objects.create(
        user=user,
        business=business,
        action=action,
        metadata=metadata or {}
    )

def is_rate_limited(mobile, limit=5, timeout=300):
        key = f"rate_limit_{mobile}"
        count = cache.get(key, 0)
        if count >= limit:
            return True
        cache.set(key, count + 1, timeout=timeout)
        return False