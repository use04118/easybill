# users/management/commands/create_missing_cash_accounts.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from users.models import Business
from cash_and_bank.models import BankAccount

class Command(BaseCommand):
    help = 'Creates cash accounts for businesses that do not have one'

    def handle(self, *args, **options):
        businesses = Business.objects.all()
        count = 0
        
        for business in businesses:
            cash_account = BankAccount.objects.filter(
                business=business,
                account_type='Cash'
            ).first()
            
            if not cash_account:
                BankAccount.objects.create(
                    business=business,
                    account_name="Cash",
                    account_type="Cash",
                    opening_balance=0,
                    current_balance=0,
                    as_of_date=timezone.now().date()
                )
                count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {count} cash accounts'
            )
        )