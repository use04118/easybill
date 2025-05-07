from django.db import models
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from sales.models import Invoice, InvoiceItem, Tcs
from users.models import Business
from parties.models import Party
from inventory.models import Item, Service, GSTTaxRate
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.db import IntegrityError

class AutomatedInvoiceExtension(Invoice):
    automated_invoice = models.ForeignKey('AutomatedInvoice', on_delete=models.CASCADE)
    invoice_data = models.JSONField()

    class Meta:
        verbose_name = 'Automated Invoice Extension'
        verbose_name_plural = 'Automated Invoice Extensions'

# Create your models here.
class AutomatedInvoice(models.Model):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Paused', 'Paused'),
        ('Stopped', 'Stopped'),
    ]

    REPEAT_UNIT_CHOICES = [
        ('Days', 'Days'),
        ('Weeks', 'Weeks'),
        ('Months', 'Months'),
        ('Yearly', 'Yearly'),
    ]
    TCS_ON_CHOICES = (
    ('taxable', 'Taxable Amount'),
    ('total', 'Total Amount'),
)

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='automatedinvoices')
    automated_invoice_no=models.CharField(max_length=50, unique=True)
    party = models.ForeignKey(Party, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    repeat_every = models.PositiveIntegerField(default=1)
    repeat_unit = models.CharField(max_length=10, choices=REPEAT_UNIT_CHOICES, default='Weeks')
    payment_terms = models.PositiveIntegerField(default=30)
    # Invoice Configurations
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    apply_tcs = models.BooleanField(default=False)
    tcs = models.ForeignKey(Tcs, null=True, blank=True, on_delete=models.SET_NULL)
    tcs_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    tcs_on = models.CharField(max_length=20, choices=TCS_ON_CHOICES,default='Total Amount',help_text="Apply TCS on either taxable or total amount")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Total Amount")
    # Notes
    notes = models.TextField(null=True, blank=True)
    signature = models.ImageField(upload_to='static/images/', null=True, blank=True)
    # Status Tracking
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Active')

    def save(self, *args, **kwargs):
        self.status = 'Active'
        is_new = self._state.adding  # Only run logic below on first creation
        super().save(*args, **kwargs)

        if is_new and self.automatedinvoice_items.exists():
            # 1. Create JSON snapshot for extension
            item_data = []
            for item in self.automatedinvoice_items.all():
                item_data.append({
                    'item': str(item.item) if item.item else None,
                    'service': str(item.service) if item.service else None,
                    'quantity': float(item.quantity),
                    'unit_price': float(item.unit_price or 0),
                    'amount': float(item.get_amount()),  # Use get_amount() for individual items
                    'price_item': float(item.price_item or 0),
                })

            invoice_data = {
                'invoice_no': self.automated_invoice_no,
                'party': str(self.party),
                'start_date': str(self.start_date),
                'due_date': str(self.end_date),
                'payment_terms': self.payment_terms,
                'discount': str(self.discount),
                'tcs_amount': str(self.tcs_amount),
                'total_amount': str(self.get_total_amount()),  # Correct use of get_total_amount for the full invoice
                'status': 'Unpaid',
                'notes': self.notes,
                'apply_tcs': self.apply_tcs,
                'tcs_on': self.tcs_on,
                'items': item_data
            }

            AutomatedInvoiceExtension.objects.create(
                automated_invoice=self,
                invoice_data=invoice_data
            )

            # 2. Create real Invoice
            invoice = Invoice.objects.create(
                business=self.business,
                party=self.party,
                invoice_no=self.automated_invoice_no,  # Must match
                date=self.start_date,
                due_date=self.end_date,
                discount=self.discount,
                total_amount=self.get_total_amount(),  # Correct use of get_total_amount for the full invoice
                notes=self.notes,
                tcs=self.tcs if self.apply_tcs else None,
                tcs_amount=self.tcs_amount,
                status='Unpaid',
            )

            # 3. Create InvoiceItems
            for item in self.automatedinvoice_items.all():
                InvoiceItem.objects.create(
                    invoice=invoice,
                    item=item.item,
                    quantity=item.quantity,
                    amount=item.get_amount(),  # Correct use of get_amount for individual items
                    unit_price=item.unit_price,
                )

        # Update total_amount on the AutomatedInvoice object
        self.total_amount = self.get_total_amount()  # Use get_total_amount() on AutomatedInvoice instance


    def get_tcs_amount(self):
        if self.apply_tcs and self.tcs and self.business and self.business.tcs:
            rate = self.tcs.rate or Decimal('0.00')

            if self.tcs_on == 'Total Amount':
                base_amount = self.get_total_amount(without_tcs=True)
            else:
                base_amount = self.get_taxable_amount()

            return (base_amount * rate / Decimal('100.00')).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        return Decimal("0.00")

    def get_total_amount(self, without_tcs=False):
        total_amount = sum(Decimal(str(item.get_amount())) for item in self.automatedinvoice_items.all())

        # Convert discount to Decimal safely
        discount = Decimal(self.discount or 0)

        if discount > 0:
            total_amount -= (total_amount * (discount / Decimal("100")))

        # Ensure total_amount is Decimal before quantizing
        total_amount = Decimal(total_amount)

        if not without_tcs and self.apply_tcs and self.tcs and self.business and self.business.tcs:
            rate = Decimal(str(self.tcs.rate or 0))
            tcs_base = self.get_taxable_amount() if self.tcs_on == 'Taxable Amount' else total_amount
            self.tcs_amount = (tcs_base * rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            total_amount += self.tcs_amount
        else:
            self.tcs_amount = Decimal("0.00")

        return total_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    def get_taxable_amount(self):
        # Convert each price item to Decimal before summing
        total_amount = sum(Decimal(item.get_price_item()) for item in self.automatedinvoice_items.all())
        
        # Use 0 if discount is None
        discount = self.discount if self.discount is not None else 0
        
        if discount >= 0:
            discount_amount = total_amount * Decimal(discount / 100)  # Discount is a percentage
            total_amount -= discount_amount  # Subtract discount from total amount
        
        return total_amount
    
    def is_within_schedule(self):
        """Helper to check if today falls within schedule."""
        today = date.today()
        return self.status == 'Active' and self.start_date <= today <= self.end_date
    
    def __str__(self):
        return f"Automated Invoice for {self.party} [{self.start_date} to {self.end_date}] - {self.status}"

class AutomatedInvoiceItem(models.Model):
    automatedinvoice = models.ForeignKey(AutomatedInvoice, related_name='automatedinvoice_items', on_delete=models.CASCADE)
    item = models.ForeignKey(Item, null=True, blank=True, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, null=True, blank=True, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    hsn_code = models.CharField(max_length=20, blank=True, null=True)
    gstTaxRate = models.ForeignKey(GSTTaxRate, on_delete=models.SET_NULL, null=True)
    price_item = models.DecimalField(max_digits=10, decimal_places=2,null=True, blank=True, help_text="Unit price in ₹")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Unit price for both products and services
    
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
    
    def get_salesPrice_with_tax(self):
        """Returns the tax-inclusive sales price if stored without tax."""
        if self.item:
            if self.item.salesPriceType == "With Tax":
                price_with_tax = self.calculate_price(self.item.salesPrice, "With Tax")
                return (price_with_tax)
            return (self.item.salesPrice)  # Already tax-exclusive
        elif self.service:
            if self.service.salesPriceType == "With Tax":
                price_with_tax = self.calculate_price(self.service.salesPrice, "With Tax")
                return (price_with_tax)
            return (self.service.salesPrice)  # Service price * quantity
        return 0.0
    
    def get_salesPrice_without_tax(self):
        """Returns the tax-inclusive sales price if stored without tax."""
        if self.item:
            if self.item.salesPriceType == "Without Tax":
                price_without_tax = self.calculate_price(self.item.salesPrice, "Without Tax")
                return (price_without_tax)
            return (self.item.salesPrice)  # Already tax-exclusive
        elif self.service:
            if self.service.salesPriceType == "Without Tax":
                price_without_tax = self.calculate_price(self.service.salesPrice, "Without Tax")
                return (price_without_tax)
            return (self.service.salesPrice)  # Service price * quantity
        return 0.0
    
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
            if self.item.salesPriceType == "With Tax":
                return (self.item.salesPriceType)
            return (self.item.salesPriceType)  # Already tax-exclusive
        elif self.service:
            if self.service.salesPriceType == "With Tax":
                return (self.service.salesPriceType)
            return (self.service.salesPriceType)  # Service price * quantity
    
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
            if self.item.salesPriceType == "Without Tax":
                price_with_tax = self.calculate_price(self.item.salesPrice, "Without Tax")
                total_amount = round(price_with_tax * self.quantity, 2)
            else:
                total_amount = round(self.item.salesPrice * self.quantity, 2)  # Already tax-inclusive
             # Apply the discount to the total amount (if any)
            if self.discount > 0:
                discount_amount = total_amount * (self.discount / 100)  # Discount is a percentage
                total_amount -= discount_amount  # Subtract discount from total amount
            return round(total_amount, 2)
        elif self.service:
            if self.service.salesPriceType == "Without Tax":
                price_with_tax = self.calculate_price(self.service.salesPrice, "Without Tax")
                total_amount = round(price_with_tax * self.quantity, 2)
            else:
            # For services, calculate the amount based on the service price and apply discount
                total_amount = round(self.service.salesPrice * self.quantity, 2)
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
            if self.item.salesPriceType == "With Tax":
                price_without_tax = self.calculate_price(self.item.salesPrice, "With Tax")
                total_price = price_without_tax * self.quantity
            else:
                total_price = self.item.salesPrice * self.quantity  # Already tax-exclusive
            
            # Apply discount if any
            if hasattr(self, 'discount') and self.discount > 0:
                discount_amount = total_price * (self.discount / 100)
                total_price -= discount_amount
        
        elif self.service:
            # Handle service price calculation based on sales type
            if self.service.salesPriceType == "With Tax":
                price_without_tax = self.calculate_price(self.service.salesPrice, "With Tax")
                total_price = price_without_tax * self.quantity
            else:
                total_price = self.service.salesPrice * self.quantity
            
            # Apply discount if any
            if hasattr(self, 'discount') and self.discount > 0:
                discount_amount = total_price * (self.discount / 100)
                total_price -= discount_amount
        # Return the final price, rounded to two decimal places
        return round(total_price, 2)

    def get_available_stock(self):
        """Returns the remaining stock for products. For services, stock is not managed."""
        if self.item:
            # Create a unique cache key for each item
            cache_key = f'item_{self.item.id}_stock_{self.quantity}'  # Include quantity in the key to handle dynamic changes
            available_stock = cache.get(cache_key)  # Check if the result is cached
            if available_stock is None:  # Cache miss - calculate available stock
                if self.item.closingStock >= self.quantity:
                    available_stock = self.item.closingStock - self.quantity
                else:
                    available_stock = 0  # Out-of-stock for products
                # Store the result in cache for 15 minutes (adjustable)
                cache.set(cache_key, available_stock)
            if available_stock <= 0:
                raise ValidationError(f"Not enough stock for {self.item.itemName}. Available stock: {self.item.closingStock}")
            return available_stock
        return None  # Services don't have stock management

    def save(self, *args, **kwargs):
        """Override save method to calculate amount and unit price for both items and services."""
        self.full_clean()  # Ensure validation
        if self.item:
            self.unit_price = self.item.salesPrice  # For products
            self.price_item = self.item.salesPrice  # Price of item before tax
            # Check if sufficient stock is available and update
            available_stock = self.get_available_stock()
            if available_stock >= 0:
                self.item.closingStock = available_stock
                self.item.save()  # Persist the updated stock to the database
                # Invalidate the cache for this item
                cache_key = f'item_{self.item.id}_stock'
                cache.delete(cache_key)  # Clear the old cached value
                # Optionally, you could also update the cache with the new stock value
                cache.set(cache_key, self.item.closingStock)
            else:
                raise ValidationError("Not enough stock available.")
        elif self.service:
            self.unit_price = self.service.salesPrice  # For services
            self.price_item = self.service.salesPrice  # Service price before tax
        self.amount = self.get_amount()  # Calculate the total amount (based on item or service)
        super().save(*args, **kwargs)

    def __str__(self):
        if self.item:
            return f"{self.item.itemName} ({self.quantity} * {self.unit_price})"
        elif self.service:
            return f"{self.service.serviceName} ({self.quantity} * {self.unit_price})"
        return "Unknown Item or Service"

    
