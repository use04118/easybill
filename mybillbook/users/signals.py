# users/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Business
from cash_and_bank.models import BankAccount

@receiver(post_save, sender=Business)
def create_default_cash_account(sender, instance, created, **kwargs):
    if created:
        # Create default cash account for the business
        BankAccount.objects.create(
            business=instance,
            account_name="Cash",
            account_type="Cash",
            opening_balance=0,
            current_balance=0,
            as_of_date=timezone.now().date()
        )