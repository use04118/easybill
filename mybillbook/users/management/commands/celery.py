from django.core.management.base import BaseCommand
from users.models import Subscription
from django.utils import timezone

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        now = timezone.now()
        expired = Subscription.objects.filter(end_date__lt=now, is_active=True)
        for sub in expired:
            sub.is_active = False
            sub.save()
            print(f"Expired: {sub.business.name} - {sub.plan.name}")
