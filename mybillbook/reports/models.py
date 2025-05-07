from django.db import models
from users.models import Business, User

# Create your models here.

class AuditTrail(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    date = models.DateTimeField(auto_now_add=True)
    voucher_no = models.CharField(max_length=50)
    action = models.CharField(max_length=255)
    model_name = models.CharField(max_length=100)  # Name of the model being modified
    record_id = models.IntegerField()  # ID of the record being modified
    old_values = models.JSONField(null=True, blank=True)  # Previous values
    new_values = models.JSONField(null=True, blank=True)  # New values

    class Meta:
        ordering = ['-date']
        indexes = [
            models.Index(fields=['business', 'date']),
            models.Index(fields=['business', 'model_name', 'record_id']),
        ]

    def __str__(self):
        return f"{self.action} by {self.user} on {self.date}"


class CapitalEntry(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    date = models.DateField()
    ledger_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.ledger_name} - {self.amount} on {self.date}"

class CurrentLiabilityEntry(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    date = models.DateField()
    ledger_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.ledger_name} - {self.amount} on {self.date}"
 
class LoanEntry(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    date = models.DateField()
    ledger_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(blank=True, null=True)
    # Add more fields as needed

    def __str__(self):
        return f"{self.ledger_name} - {self.amount}"

class CurrentAssetEntry(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    date = models.DateField()
    ledger_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.ledger_name} - {self.amount} on {self.date}"


class FixedAssetEntry(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    date = models.DateField()
    ledger_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.ledger_name} - {self.amount} on {self.date}"

class InvestmentEntry(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    date = models.DateField()
    ledger_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.ledger_name} - {self.amount} on {self.date}"

class LoansAdvanceEntry(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    date = models.DateField()
    ledger_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.ledger_name} - {self.amount} on {self.date}"