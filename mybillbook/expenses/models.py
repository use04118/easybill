from django.db import models, transaction
from django.db.models import Max
from inventory.models import GSTTaxRate,MeasuringUnit
from datetime import timedelta
from django.utils import timezone
from parties.models import Party
from decimal import Decimal
from django.db import models
import uuid
from users.models import Business
from django.db import models, transaction
from django.db.models import Max
from inventory.models import Item, Service, GSTTaxRate
from datetime import timedelta
from django.utils import timezone
from parties.models import Party  
import uuid
from django.db import models
from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError



# Model Categories
class ExpenseCategory(models.Model):
    name = models.CharField(max_length=100)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='expenses_categories')
    created_at = models.DateField(auto_now=True)  # Automatically updates the date when stock changes
    class Meta:
        app_label = 'expenses'
        unique_together = ['business', 'name']  # ✅ Ensures unique per business
        ordering = ['name']

    def __str__(self):
        return self.name

# Model for Items
class Item(models.Model):
    ITEM_TYPE_CHOICES = [
        ('Product', 'Product')
    ]
    
    ITC_CHOICE = [
        ('Eligible', 'Eligible'),
        ('Ineligible', 'Ineligible'),
        ('Ineligible Others', 'Ineligible Others'),
    ]
    PURCHASE_PRICE_TYPE = [
        ('With Tax', 'With Tax'),
        ('Without Tax', 'Without Tax')
    ]
    
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='expense_items')
    itemName = models.CharField(max_length=255)
    itemType = models.CharField(max_length=10, choices=ITEM_TYPE_CHOICES, default="Product")
    purchasePrice = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    purchasePriceType = models.CharField(max_length=50, choices=PURCHASE_PRICE_TYPE, default="With Tax")
    ITC = models.CharField(max_length=50, choices=ITC_CHOICE, default="Eligible")
    gstTaxRate = models.ForeignKey(GSTTaxRate, on_delete=models.SET_NULL, null=True,related_name='item_gsttaxrate')
    measuringUnit = models.ForeignKey(MeasuringUnit, on_delete=models.SET_NULL, null=True,related_name='item_measuringuunit')
    hsnCode = models.CharField(max_length=15, blank=True, null=True)

    def calculate_price(self, price, price_type):
        price = Decimal(price)
        """Calculates tax-inclusive or tax-exclusive price based on GST and Cess rate."""
        tax_rate = self.gstTaxRate.rate / 100 if self.gstTaxRate else 0
        cess_rate = self.gstTaxRate.cess_rate / 100 if self.gstTaxRate else 0
        
        # Combined GST + Cess rate
        total_rate = tax_rate + cess_rate
        
        if price_type == "With Tax":
            # Extract base price from tax-inclusive price
            return (price / (1 + total_rate)) if total_rate > 0 else price
        else:
            # Add GST + Cess to the base price
            return (price * (1 + total_rate))

    def save(self, *args, **kwargs):
        """ Automatically set the `enableLowStockWarning` field based on `openingStock` and `lowStockQty` """
        super(Item, self).save(*args, **kwargs)
        
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['business', 'itemName'], name='unique_itemName_per_business')
        ]

    def __str__(self):
        return f"{self.itemName}"

# Model for Services
class ExpenseService(models.Model):
    SERVICE_TYPE_CHOICES = [
        ('Service', 'Service')  
    ]
    
    ITC_CHOICE = [
        ('Eligible', 'Eligible'),
        ('Ineligible', 'Ineligible'),
        ('Ineligible Others', 'Ineligible Others')
    ]
    
    PURCHASE_PRICE_TYPE = [
        ('With Tax', 'With Tax'),
        ('Without Tax', 'Without Tax')
    ]
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='expenses_service')
    serviceName = models.CharField(max_length=255)
    serviceType = models.CharField(max_length=10, choices=SERVICE_TYPE_CHOICES, default="Service")
    purchasePrice = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    purchasePriceType = models.CharField(max_length=50, choices=PURCHASE_PRICE_TYPE, default="With Tax")
    ITC = models.CharField(max_length=50, choices=ITC_CHOICE, default="Eligible")
    gstTaxRate = models.ForeignKey(GSTTaxRate, on_delete=models.SET_NULL, null=True,related_name='expenses_gsttaxrate')
    measuringUnit = models.ForeignKey(MeasuringUnit, on_delete=models.SET_NULL, null=True,related_name='expenses_measuringuunit')
    sacCode = models.CharField(max_length=15, blank=True, null=True)

    def calculate_price(self, price, price_type):
        price = Decimal(price)
        """Calculates tax-inclusive or tax-exclusive price based on GST and Cess rate."""
        tax_rate = self.gstTaxRate.rate / 100 if self.gstTaxRate else 0
        cess_rate = self.gstTaxRate.cess_rate / 100 if self.gstTaxRate else 0
        
        # Combined GST + Cess rate
        total_rate = tax_rate + cess_rate
        
        if price_type == "With Tax":
            # Extract base price from tax-inclusive price
            return (price / (1 + total_rate)) if total_rate > 0 else price
        else:
            # Add GST + Cess to the base price
            return (price * (1 + total_rate))

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['business', 'serviceName'], name='unique_serviceName_per_business')
        ]
    
    def __str__(self):
        return f"{self.serviceName}"
    

class Expense(models.Model):
    PAYMENT_METHOD_CHOICES = (
        ('Cash', "Cash"),
        ('UPI', "UPI"),
        ('Card', "Card"),
        ('Netbanking', "Netbanking"),
        ('Bank Transfer', "Bank Transfer"),
        ('Cheque', "Cheque"),
    )

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='expenses', null=True, blank=True)
    expense_no = models.CharField(max_length=50)
    original_invoice_no = models.CharField(max_length=50, null=True, blank=True)
    date = models.DateField()
    party = models.ForeignKey(Party, on_delete=models.CASCADE, null=True, blank=True)
    category = models.ForeignKey('ExpenseCategory', on_delete=models.CASCADE)
    
    expense_with_gst = models.BooleanField(default=False)

    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='Cash', blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, help_text="Discount in %")

    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)

    class Meta:
        unique_together = ('business', 'expense_no')
        ordering = ['-date']

    def __str__(self):
        return f"Expense {self.expense_no} - {self.party}"

    def save(self, *args, **kwargs):
        is_new = not self.pk

        if is_new:
            super().save(*args, **kwargs)

        self.taxable_amount = self.get_taxable_amount()
        self.total_amount = self.get_total_amount()
        self.update_party_balance() 
        super().save(update_fields=['party', 'category','taxable_amount', 'total_amount', 'payment_method', 'notes', 'discount'])


    def get_total_amount(self):
        total_amount = sum(Decimal(str(item.get_amount())) for item in self.expense_items.all())

        discount = Decimal(self.discount or 0)
        if discount > 0:
            total_amount -= (total_amount * (discount / Decimal("100")))

        # Ensure total_amount is Decimal before quantizing
        total_amount = Decimal(total_amount)

        return total_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    

    def get_taxable_amount(self):
        # Convert each price item to Decimal before summing
        total_amount = sum(Decimal(item.get_price_item()) for item in self.expense_items.all())
        
        # Use 0 if discount is None
        discount = self.discount if self.discount is not None else 0
        
        if discount >= 0:
            discount_amount = total_amount * Decimal(discount / 100)  # Discount is a percentage
            total_amount -= discount_amount  # Subtract discount from total amount
        
        return total_amount
    

    def update_party_balance(self):
        amount = self.total_amount
        
        if self.party:
            if self.party.balance_type == 'To Pay':
                self.party.closing_balance -= amount
                if self.party.closing_balance < 0:
                    self.party.balance_type = 'To Collect'
                    self.party.closing_balance = abs(self.party.closing_balance)
            elif self.party.balance_type == 'To Collect':
                self.party.closing_balance += amount

            self.party.save()

    def reverse_party_balance(self):
        amount = self.total_amount
        
        if self.party:
            if self.party.balance_type == 'To Collect':
                self.party.closing_balance -= amount
                if self.party.closing_balance < 0:
                    self.party.balance_type = 'To Pay'
                    self.party.closing_balance = abs(self.party.closing_balance)
            elif self.party.balance_type == 'To Pay':
                self.party.closing_balance += amount

            self.party.save()

    def delete(self, *args, **kwargs):
        self.reverse_party_balance()
        super().delete(*args, **kwargs)


class ExpenseItem(models.Model):
    expense = models.ForeignKey('Expense', related_name='expense_items', on_delete=models.CASCADE)
    item = models.ForeignKey('Item', null=True, blank=True, on_delete=models.CASCADE)
    service = models.ForeignKey('ExpenseService', null=True, blank=True, on_delete=models.CASCADE)

    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, help_text="Discount in percentage.")
    gstTaxRate = models.ForeignKey(GSTTaxRate, on_delete=models.SET_NULL, blank=True, null=True)

    unit_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    
    def clean(self):
        """Ensure either item or service is selected, not both."""
        if not self.item and not self.service:
            raise ValidationError("Either 'item' or 'service' must be provided.")
        if self.item and self.service:
            raise ValidationError("You can only select either 'item' or 'service', not both.")
    
    def get_tax_rate_amount(self):
        """Calculate GST tax amount."""
        if self.gstTaxRate:
            tax_rate = self.gstTaxRate.rate / 100 if self.gstTaxRate else 0
            return (self.get_price_item() * tax_rate)
        return Decimal(0)

    def get_cess_rate_amount(self):
        """Calculate cess amount."""
        if self.gstTaxRate:
            cess_rate = self.gstTaxRate.cess_rate / 100 if self.gstTaxRate else 0
            return (self.get_price_item() * cess_rate)
        return Decimal(0)
    
    def get_cgst_amount(self):
        """Calculate GST tax amount."""
        if self.gstTaxRate:
            tax_rate = self.gstTaxRate.rate / 200 if self.gstTaxRate else 0
            return (self.get_price_item() * tax_rate)
        return Decimal(0)

    def get_sgst_amount(self):
        """Calculate cess amount."""
        if self.gstTaxRate:
            tax_rate = self.gstTaxRate.rate / 200 if self.gstTaxRate else 0
            return (self.get_price_item() * tax_rate)
        return Decimal(0)
    
    def get_igst_amount(self):
        """Calculate IGST tax amount."""
        if self.gstTaxRate:
            igst_rate = self.gstTaxRate.rate / 100 if self.gstTaxRate else 0  # IGST uses full rate
            return (self.get_price_item() * igst_rate)
        return Decimal(0)
        
    def get_cgst(self):
        if self.gstTaxRate:
            return (self.gstTaxRate.rate/2)
        return Decimal(0)
    
    def get_sgst(self):
        if self.gstTaxRate:
            return (self.gstTaxRate.rate/2)
        return Decimal(0)
    
    
    
    def get_purchasePrice_with_tax(self):
        """Returns the tax-inclusive sales price if stored without tax."""
        if self.item:
            if self.item.purchasePriceType == "With Tax":
                price_without_tax = self.calculate_price(self.item.purchasePrice, "With Tax")
                return (price_without_tax)
            return (self.item.purchasePrice)  # Already tax-exclusive
        return 0.0
    
    def get_purchasePrice_without_tax(self):
        """Returns the tax-inclusive sales price if stored without tax."""
        if self.item:
            if self.item.purchasePriceType == "Without Tax":
                price_without_tax = self.calculate_price(self.item.purchasePrice, "Without Tax")
                return (price_without_tax)
            return (self.item.purchasePrice)  # Already tax-exclusive
        return 0.0
    
    def get_price_type(self):
        if self.item:
            if self.item.purchasePriceType == "With Tax":
                return (self.item.purchasePriceType)
            return (self.item.purchasePriceType)  # Already tax-exclusive
        elif self.service:
            if self.service.purchasePriceType == "With Tax":
                return (self.service.purchasePriceType)
            return (self.service.purchasePriceType)  # Service price * quantity
    
    def get_type(self):
        if self.item:
            if self.item.itemType == "Product":
                return 'item'
        elif self.service:
            if self.service.serviceType == "Service":
                return 'service'
    
    def calculate_price(self, price, price_type):
        """Calculates tax-inclusive or tax-exclusive price based on GST and Cess rate."""
        tax_rate = self.gstTaxRate.rate / 100 if self.gstTaxRate else 0
        cess_rate = self.gstTaxRate.cess_rate / 100 if self.gstTaxRate else 0
        
        # Combined GST + Cess rate
        total_rate = tax_rate + cess_rate
        
        if price_type == "With Tax":
            # Extract base price from tax-inclusive price
            return (price / (1 + total_rate)) if total_rate > 0 else price
        else:
            # Add GST + Cess to the base price
            return (price * (1 + total_rate))
        
    def get_amount(self):
        """Calculates the total amount for the item or service, applying discounts if any."""
        if self.item:
            if self.item.purchasePriceType == "Without Tax":
                price_with_tax = self.calculate_price(self.item.purchasePrice, "Without Tax")
                total_amount = round(price_with_tax * self.quantity, 2)
            else:
                total_amount = round(self.item.purchasePrice * self.quantity, 2)  # Already tax-inclusive
             # Apply the discount to the total amount (if any)
            if self.discount > 0:
                discount_amount = total_amount * (self.discount / 100)  # Discount is a percentage
                total_amount -= discount_amount  # Subtract discount from total amount
            return round(total_amount, 2)
        elif self.service:
            if self.service.purchasePriceType == "Without Tax":
                price_with_tax = self.calculate_price(self.service.purchasePrice, "Without Tax")
                total_amount = round(price_with_tax * self.quantity, 2)
            else:
            # For services, calculate the amount based on the service price and apply discount
                total_amount = round(self.service.purchasePrice * self.quantity, 2)
            # Apply the discount to the total amount (if any)
            if self.discount > 0:
                discount_amount = total_amount * (self.discount / 100)  # Discount is a percentage
                total_amount -= discount_amount  # Subtract discount from total amount
            return round(total_amount, 2)       
        return 0.0  # If no item or service, return 0

    def get_price_item(self):
        """Returns the price of the item or service (excluding tax), applying discounts if any."""
        
        total_price = 0.0
        
        if self.item:
            # Handle item price calculation based on sales type
            if self.item.purchasePriceType == "With Tax":
                price_without_tax = self.calculate_price(self.item.purchasePrice, "With Tax")
                total_price = price_without_tax * self.quantity
            else:
                total_price = self.item.purchasePrice * self.quantity  # Already tax-exclusive
            
            # Apply discount if any
            if hasattr(self, 'discount') and self.discount > 0:
                discount_amount = total_price * (self.discount / 100)
                total_price -= discount_amount
        
        elif self.service:
            # Handle service price calculation based on sales type
            if self.service.purchasePriceType == "With Tax":
                price_without_tax = self.calculate_price(self.service.purchasePrice, "With Tax")
                total_price = price_without_tax * self.quantity
            else:
                total_price = self.service.purchasePrice * self.quantity
            
            # Apply discount if any
            if hasattr(self, 'discount') and self.discount > 0:
                discount_amount = total_price * (self.discount / 100)
                total_price -= discount_amount
        
        # Return the final price, rounded to two decimal places
        return round(total_price, 2)

    def save(self, *args, **kwargs):
        """Override save method to calculate amount and unit price for both items and services."""
        self.full_clean()  # Ensure validation
        if self.item:
            self.unit_price = self.item.purchasePrice  # For products
            self.price_item = self.item.purchasePrice  # Price of item before tax
        elif self.service:
            self.unit_price = self.service.purchasePrice  # For services
            self.price_item = self.service.purchasePrice  # Service price before tax
        self.amount = self.get_amount()  # Calculate the total amount (based on item or service)
        super().save(*args, **kwargs)

    def __str__(self):
        if self.item:
            return f"{self.item.itemName} ({self.quantity} * {self.unit_price})"
        elif self.service:
            return f"{self.service.serviceName} ({self.quantity} * {self.unit_price})"
        return "Unknown Item or Service"
