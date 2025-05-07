from django.contrib import admin
from .models import User, Business, Role,Subscription,SubscriptionPlan,StaffInvite,AuditLog

admin.site.register(User)
admin.site.register(Business)
admin.site.register(Role)
admin.site.register(StaffInvite)
admin.site.register(Subscription)
admin.site.register(SubscriptionPlan)
admin.site.register(AuditLog)
