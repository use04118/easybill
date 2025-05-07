from django.db import models
from users.models import Business

# Create your models here.
# Model for Category
class PartyCategory(models.Model):
    name = models.CharField(max_length=100)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='categories')
    class Meta:
        app_label = 'parties'
        unique_together = ['business', 'name']  # ✅ Ensures unique per business
        ordering = ['name']
    
    def __str__(self):
        return self.name

INDIAN_STATES = [
    ('Andhra Pradesh', 'Andhra Pradesh'),
    ('Arunachal Pradesh', 'Arunachal Pradesh'),
    ('Assam', 'Assam'),
    ('Bihar', 'Bihar'),
    ('Chhattisgarh', 'Chhattisgarh'),
    ('Goa', 'Goa'),
    ('Gujarat', 'Gujarat'),
    ('Haryana', 'Haryana'),
    ('Himachal Pradesh', 'Himachal Pradesh'),
    ('Jharkhand', 'Jharkhand'),
    ('Karnataka', 'Karnataka'),
    ('Kerala', 'Kerala'),
    ('Madhya Pradesh', 'Madhya Pradesh'),
    ('Maharashtra', 'Maharashtra'),
    ('Manipur', 'Manipur'),
    ('Meghalaya', 'Meghalaya'),
    ('Mizoram', 'Mizoram'),
    ('Nagaland', 'Nagaland'),
    ('Odisha', 'Odisha'),
    ('Punjab', 'Punjab'),
    ('Rajasthan', 'Rajasthan'),
    ('Sikkim', 'Sikkim'),
    ('Tamil Nadu', 'Tamil Nadu'),
    ('Telangana', 'Telangana'),
    ('Tripura', 'Tripura'),
    ('Uttar Pradesh', 'Uttar Pradesh'),
    ('Uttarakhand', 'Uttarakhand'),
    ('West Bengal', 'West Bengal'),
    ('Delhi', 'Delhi'),
    ('Jammu and Kashmir', 'Jammu and Kashmir'),
    ('Ladakh', 'Ladakh'),
    ('Puducherry', 'Puducherry'),
    ('Chandigarh', 'Chandigarh'),
    ('Andaman and Nicobar Islands', 'Andaman and Nicobar Islands'),
    ('Dadra and Nagar Haveli and Daman and Diu', 'Dadra and Nagar Haveli and Daman and Diu'),
    ('Lakshadweep', 'Lakshadweep'),
]


class Party(models.Model):
    PARTY_TYPE_CHOICES = [
        ("Customer", 'Customer'),
        ("Supplier", 'Supplier'),
    ]
    OPENING_BALANCE_CHOICES = [
        ("To Collect", 'To Collect'),
        ("To Pay", 'To Pay'),
    ]
    
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='parties')
    party_name = models.CharField(max_length=250)
    category = models.ForeignKey(PartyCategory, on_delete=models.SET_NULL, null=True, blank=True)
    mobile_number = models.CharField(max_length=15)
    email = models.EmailField(max_length=254)
    gstin = models.CharField(max_length=20, null=True, blank=True)
    pan = models.CharField(max_length=10, null=True, blank=True)
    party_type = models.CharField(max_length=10, choices=PARTY_TYPE_CHOICES, default="Customer")
    balance_type = models.CharField(max_length=10, choices=OPENING_BALANCE_CHOICES, default="To Collect")
    opening_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    closing_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    shipping_address = models.TextField()
    billing_address = models.TextField()
    street_address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100,choices=INDIAN_STATES, blank=True, null=True)
    pincode = models.CharField(max_length=10, blank=True, null=True)
    credit_period = models.IntegerField(default=0)
    credit_limit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateField(auto_now=True)  # Automatically updates the date when stock changes
    
    class Meta:
        app_label = 'parties'
        constraints = [
        models.UniqueConstraint(fields=['business', 'party_name'], name='unique_party_per_business'),
    ]
        ordering = ['party_name']
        
    def save(self, *args, **kwargs):
        if self.closing_balance == 0.00:
            self.closing_balance = self.opening_balance
        super().save(*args, **kwargs)
        
    def __str__(self):
        return self.party_name
