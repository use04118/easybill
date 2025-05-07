# cash_and_bank/models.py
from django.db import models
from users.models import Business
from django.core.exceptions import ValidationError

class BankAccount(models.Model):
    ACCOUNT_TYPE_CHOICES = [
        ('Cash', 'Cash'),
        ('Bank', 'Bank'),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='bank_accounts')
    account_name = models.CharField(max_length=100)
    account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPE_CHOICES)
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    current_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    as_of_date = models.DateField()

    # Optional Bank Details
    bank_account_number = models.CharField(max_length=20, blank=True, null=True)
    ifsc_code = models.CharField(max_length=20, blank=True, null=True)
    bank_branch_name = models.CharField(max_length=100, blank=True, null=True)
    account_holder_name = models.CharField(max_length=100, blank=True, null=True)
    upi_id = models.CharField(max_length=50, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.account_name} ({self.account_type})"

class BankTransaction(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ('ADD', 'Add Money'),
        ('REDUCE', 'Reduce Money'),
        ('TRANSFER_IN', 'Transfer In'),
        ('TRANSFER_OUT', 'Transfer Out'),
        ('PAYMENT_IN', 'Payment In'),
        ('PAYMENT_OUT', 'Payment Out'),
        ('SALES_RETURN', 'Sales Return'),
        ('PURCHASE_RETURN', 'Purchase Return'),
        ('CREDIT_NOTE', 'Credit Note'),
        ('DEBIT_NOTE', 'Debit Note')
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    reference = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    # Sales related transactions
    invoice = models.ForeignKey('sales.Invoice', on_delete=models.SET_NULL, null=True, blank=True, related_name='bank_transactions')
    payment_in = models.ForeignKey('sales.PaymentIn', on_delete=models.SET_NULL, null=True, blank=True, related_name='bank_transactions')
    sales_return = models.ForeignKey('sales.SalesReturn', on_delete=models.SET_NULL, null=True, blank=True, related_name='bank_transactions')
    credit_note = models.ForeignKey('sales.CreditNote', on_delete=models.SET_NULL, null=True, blank=True, related_name='bank_transactions')
    
    # Purchase related transactions
    purchase = models.ForeignKey('purchase.Purchase', on_delete=models.SET_NULL, null=True, blank=True, related_name='bank_transactions')
    payment_out = models.ForeignKey('purchase.PaymentOut', on_delete=models.SET_NULL, null=True, blank=True, related_name='bank_transactions')
    purchase_return = models.ForeignKey('purchase.PurchaseReturn', on_delete=models.SET_NULL, null=True, blank=True, related_name='bank_transactions')
    debit_note = models.ForeignKey('purchase.DebitNote', on_delete=models.SET_NULL, null=True, blank=True, related_name='bank_transactions')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.transaction_type} - {self.amount} - {self.date}"

    @property
    def is_credit(self):
        return self.transaction_type in ['ADD', 'TRANSFER_IN', 'PAYMENT_IN', 'PURCHASE_RETURN', 'CREDIT_NOTE']

    @property
    def is_debit(self):
        return self.transaction_type in ['REDUCE', 'TRANSFER_OUT', 'PAYMENT_OUT', 'SALES_RETURN', 'DEBIT_NOTE']

    def get_related_transaction(self):
        """Get the related transaction object based on transaction type"""
        if self.transaction_type == 'PAYMENT_IN':
            return self.payment_in
        elif self.transaction_type == 'PAYMENT_OUT':
            return self.payment_out
        elif self.transaction_type == 'SALES_RETURN':
            return self.sales_return
        elif self.transaction_type == 'PURCHASE_RETURN':
            return self.purchase_return
        elif self.transaction_type == 'CREDIT_NOTE':
            return self.credit_note
        elif self.transaction_type == 'DEBIT_NOTE':
            return self.debit_note
        return None

    def get_transaction_details(self):
        """Get details of the related transaction"""
        related = self.get_related_transaction()
        if not related:
            return {
                'type': self.transaction_type,
                'amount': self.amount,
                'date': self.date,
                'reference': self.reference
            }
        
        details = {
            'type': self.transaction_type,
            'amount': self.amount,
            'date': self.date,
            'reference': self.reference or getattr(related, 'invoice_no', None) or getattr(related, 'payment_in_number', None)
        }
        
        if hasattr(related, 'party'):
            details['party'] = {
                'id': related.party.id,
                'name': related.party.name
            }
            
        return details

    def save(self, *args, **kwargs):
        if not self.pk:  # only on create
            # Calculate the effect on balance
            if self.transaction_type in ['ADD', 'PAYMENT_IN', 'TRANSFER_IN', 'PURCHASE_RETURN', 'CREDIT_NOTE']:
                self.account.current_balance += self.amount
            elif self.transaction_type in ['REDUCE', 'PAYMENT_OUT', 'TRANSFER_OUT', 'SALES_RETURN', 'DEBIT_NOTE']:
                # Check if there's enough balance
                if self.account.current_balance < self.amount:
                    raise ValidationError("Insufficient balance for this transaction")
                self.account.current_balance -= self.amount
            
            # Save the account first
            self.account.save()
            
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Reverse the balance effect when deleting
        if self.transaction_type in ['ADD', 'PAYMENT_IN', 'TRANSFER_IN', 'PURCHASE_RETURN', 'CREDIT_NOTE']:
            self.account.current_balance -= self.amount
        elif self.transaction_type in ['REDUCE', 'PAYMENT_OUT', 'TRANSFER_OUT', 'SALES_RETURN', 'DEBIT_NOTE']:
            self.account.current_balance += self.amount
        
        self.account.save()
        super().delete(*args, **kwargs)

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['business', 'account']),
            models.Index(fields=['transaction_type']),
            models.Index(fields=['date']),
        ]
