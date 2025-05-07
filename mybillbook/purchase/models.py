from django.db import models 
from parties.models import Party
from inventory.models import Item, Service, GSTTaxRate
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.core.cache import cache
from decimal import Decimal, ROUND_HALF_UP
from users.models import Business
from sales.models import Tds, Tcs

class Purchase(models.Model):
    STATUS_CHOICES = [
        ('Unpaid', 'Unpaid'),
        ('Partially Paid', 'Partially Paid'),
        ('Paid', 'Paid')
    ]
    
    PAYMENT_METHOD_CHOICES = (
        ('Cash', "Cash"),
        ('UPI', "UPI"),
        ('Card', "Card"),
        ('Netbanking', "Netbanking"),
        ('Bank Transfer', "Bank Transfer"),
        ('Cheque', "Cheque"),
    )

    TCS_ON_CHOICES = (
        ('taxable', 'taxable'),
        ('total', 'total'),
    )

    business = models.ForeignKey(Business, on_delete=models.CASCADE, blank=True , null=True, related_name='purchase')
    purchase_no = models.CharField(max_length=50)
    date = models.DateField(auto_now_add=False)
    party = models.ForeignKey(Party, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Unpaid')
    payment_term = models.PositiveIntegerField(help_text="Number of days for the payment term", blank=True, null=True,default=30)
    due_date = models.DateField(blank=True, null=True)
    original_invoice_no=models.CharField(max_length=50,null=True,blank= True)
    is_fully_paid = models.BooleanField(default=False, help_text="Mark as fully paid")
    amount_received = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Amount received")
    balance_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Balance Amount")
    taxable_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Taxable Amount")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Total Amount")
    total_payable_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Total Payable Amount")
    bank_account = models.ForeignKey('cash_and_bank.BankAccount', on_delete=models.SET_NULL, null=True, blank=True, related_name='purchase')
    

    apply_tcs = models.BooleanField(default=False)
    tcs = models.ForeignKey('sales.Tcs' ,on_delete=models.SET_NULL, blank=True , null=True, related_name='purchase_tcs')
    tcs_on = models.CharField(max_length=20, choices=TCS_ON_CHOICES,default='total',help_text="Apply TCS on either taxable or total amount")
    tcs_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="TCS Amount")

    apply_tds = models.BooleanField(default=False)
    tds = models.ForeignKey('sales.Tds', on_delete=models.SET_NULL, blank=True, null=True, related_name='purchase_tds')
    tds_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES,  default='Cash', blank=True, null=True)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0,blank=True , null=True, help_text="Discount in percentage.")
    notes = models.TextField(blank=True,null=True)
    signature = models.ImageField(upload_to='static/images/', null=True, blank=True)
    
    def save(self, *args, **kwargs):
        # Automatically calculate due_date
        if self.date and self.payment_term:
            self.due_date = self.date + timedelta(days=self.payment_term)

        # Save the invoice first to get the primary key (for editing)
        is_new = not self.pk

        if is_new:
            # For new invoice, do the first save
            print("new save --")
            super().save(*args, **kwargs)

        self.balance_amount = self.get_balance_amount()
        self.taxable_amount = self.get_taxable_amount()
        self.total_amount = self.get_total_amount()
        self.total_payable_amount = self.get_total_payable_amount()
        self.tcs_amount = self.get_tcs_amount()
        self.tds_amount = self.get_tds_amount()
 
        # Now that it has a primary key, you can safely calculate total amount
        if not is_new:
            print("old invoice -- 1")
            self.reverse_previous_balance_impact()

        # Now that the invoice has been saved, proceed with the balance update
        if self.is_fully_paid:
            self.handle_fully_paid()
        elif self.amount_received > 0:
            self.handle_partially_paid()
        else:
            self.handle_unpaid()

        # Update the status of the invoice (Paid/Unpaid/Partially Paid)
        self.update_status()

        # Save the updated fields (no double save)
        super().save(update_fields=['party','purchase_no', 'status', 'amount_received','total_amount','balance_amount' ,'is_fully_paid', 'due_date', 'notes', 'discount', 'payment_method', 'payment_term', 'tcs_amount','tds_amount','taxable_amount','business' ,'total_payable_amount','tcs','apply_tcs','tds','apply_tds','bank_account'])

    
    def handle_fully_paid(self):
        # ✅ Scenario 1 & Scenario 4: Fully Paid (at creation or after edit)
        # No balance changes to the party
        self.status = 'Paid'
        if self.apply_tds and self.tds and self.business and self.business.tds:
            self.amount_received = self.get_total_payable_amount()
        else:
            self.amount_received = self.get_total_amount()
        print("paid success")

       

    
    def handle_partially_paid(self):
        # ✅ Scenario 3 & Scenario 5: Partially Paid
        if self.apply_tds and self.tds and self.business and self.business.tds:
           total_amount = self.get_total_payable_amount()
        else:
            total_amount = self.get_total_amount()
        print(f"Total Amount: {total_amount}") 
        remaining_amount = total_amount - self.amount_received
        print(remaining_amount , total_amount , self.amount_received)

        # Step 1: Deduct from To Pay
        if self.party.balance_type == 'To Collect' and self.party.closing_balance > 0:
            if remaining_amount >= self.party.closing_balance:
                remaining_amount -= self.party.closing_balance
                self.party.closing_balance = 0
                self.party.balance_type = 'To Pay'
            else:
                self.party.closing_balance -= remaining_amount
                remaining_amount = 0

        # Step 2: Add remaining amount (if any) to To Collect
        if remaining_amount > 0:
            if self.party.balance_type == 'To Collect' and self.party.closing_balance == 0:
                self.party.balance_type = 'To Pay'
            self.party.closing_balance += remaining_amount

        self.party.save()
        self.status = 'Partially Paid'
        print("Partially paid success")


    def handle_unpaid(self):
        # ✅ Scenario 2 & Scenario 6: Unpaid
        if self.apply_tds and self.tds and self.business and self.business.tds:
           total_amount = self.get_total_payable_amount()
        else:
            total_amount = self.get_total_amount()
        print(f"Total Amount: {total_amount}")  # Debugging line
        remaining_amount = total_amount

        # Step 1: Deduct from To Pay
        if self.party.balance_type == 'To Collect' and self.party.closing_balance > 0:
            if remaining_amount >= self.party.closing_balance:
                remaining_amount -= self.party.closing_balance
                self.party.closing_balance = 0
                self.party.balance_type = 'To Pay'
            else:
                self.party.closing_balance -= remaining_amount
                remaining_amount = 0

        # Step 2: Add remaining amount (if any) to To Collect
        if remaining_amount > 0:
            if self.party.balance_type == 'To Collect' and self.party.closing_balance == 0:
                self.party.balance_type = 'To Pay'
            self.party.closing_balance += remaining_amount

        self.party.save()
        self.status = 'Unpaid'
        print("Unpaid success")

    def reverse_previous_balance_impact(self):
        # ✅ Reverse any previous balance impact based on the old status
        try:
            old_invoice = Purchase.objects.get(pk=self.pk)
        except Purchase.DoesNotExist:
            # Handle the case where the old invoice doesn't exist (shouldn't happen in a valid state)
            print("Old invoice does not exist.")
            return
        

        # Case 1: Fully Paid - No impact to reverse
        if old_invoice.status == 'Paid':
            return

        # Case 2: Unpaid or Partially Paid
        if old_invoice.status in ['Unpaid', 'Partially Paid']:
            if old_invoice.apply_tds and old_invoice.tds and old_invoice.business and old_invoice.business.tds:
                total_amount = old_invoice.total_payable_amount
            else:
                total_amount = old_invoice.total_amount
            received_amount = old_invoice.amount_received  # Should be set correctly during the save
            balance_amount = total_amount - received_amount  # Should be set correctly during the save

            print(f"Total Amount: {total_amount}")
            print(f"Received Amount: {received_amount}")
            print(f"Balance Amount: {balance_amount}")
            print(f"Old invoice status: {old_invoice.status}")

            # Reverse impact based on the old balance type
            if old_invoice.status == 'Unpaid':
                self.reverse_unpaid_balance(total_amount)
            elif old_invoice.status == 'Partially Paid':
                self.reverse_partially_paid_balance(balance_amount)
            
        old_party = old_invoice.party
        if old_party != self.party:
            print("Party changed. Reversing old party balance impact.")
            self.transfer_balance_to_new_party(old_party,balance_amount)

    def reverse_unpaid_balance(self, total_amount):
        # ✅ Reverse the unpaid logic impact
        if self.party.balance_type == 'To Pay':
            self.party.closing_balance -= total_amount
            if self.party.closing_balance < 0:
                self.party.balance_type = 'To Collect'
                self.party.closing_balance = abs(self.party.closing_balance)
        elif self.party.balance_type == 'To Collect':
            self.party.closing_balance += total_amount
        self.party.save()

    def reverse_partially_paid_balance(self, received_amount):
        # Reverse the partially paid logic impact based on previous payments
        if self.party.balance_type == 'To Pay':
            self.party.closing_balance -= received_amount
            if self.party.closing_balance < 0:
                self.party.balance_type = 'To Collect'
                self.party.closing_balance = abs(self.party.closing_balance)
        elif self.party.balance_type == 'To Collect':
            self.party.closing_balance += received_amount
        self.party.save()


    def update_status(self):
        total_amount = self.get_total_amount()
        if self.is_fully_paid or self.amount_received >= total_amount:
            self.status = 'Paid'
        elif self.amount_received > 0:
            self.status = 'Partially Paid'
        else:
            self.status = 'Unpaid'
        print(self.status)

    def get_tcs_amount(self):
        if self.apply_tcs and self.tcs and self.business and self.business.tcs:
            rate = self.tcs.rate or Decimal('0.00')

            if self.tcs_on == 'total':
                base_amount = self.get_total_amount(without_tcs=True)
            else:
                base_amount = self.get_taxable_amount()

            return (base_amount * rate / Decimal('100.00')).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)

        return Decimal("0.00")
    
    def get_tds_amount(self):
        if self.apply_tds and self.tds and self.business and self.business.tds:
            rate = self.tds.rate or Decimal('0.00')
            base = self.get_taxable_amount()
            return (base * rate / Decimal('100.00')).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
        return Decimal("0.00")

    def get_total_amount(self, without_tcs=False):
        total_amount = sum(Decimal(str(item.get_amount())) for item in self.purchase_items.all())

        discount = Decimal(self.discount or 0)
        if discount > 0:
            total_amount -= (total_amount * (discount / Decimal("100")))

        # Ensure total_amount is Decimal before quantizing
        total_amount = Decimal(total_amount)

        if not without_tcs and self.apply_tcs and self.tcs and self.business and self.business.tcs:
            rate = Decimal(str(self.tcs.rate or 0))
            tcs_base = self.get_taxable_amount() if self.tcs_on == 'taxable' else total_amount
            self.tcs_amount = (tcs_base * rate / Decimal("100")).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
            total_amount += self.tcs_amount
        else:
            self.tcs_amount = Decimal("0.00")

        return total_amount.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
    
    def get_total_payable_amount(self, without_tcs=False):
        total_amount = sum(Decimal(str(item.get_amount())) for item in self.purchase_items.all())

        discount = Decimal(self.discount or 0)
        if discount > 0:
            total_amount -= (total_amount * (discount / Decimal("100")))

        # Ensure total_amount is Decimal before quantizing
        total_amount = Decimal(total_amount)

        if not without_tcs and self.apply_tcs and self.tcs and self.business and self.business.tcs:
            rate = Decimal(str(self.tcs.rate or 0))
            tcs_base = self.get_taxable_amount() if self.tcs_on == 'taxable' else total_amount
            self.tcs_amount = (tcs_base * rate / Decimal("100")).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
            total_amount += self.tcs_amount
        else:
            self.tcs_amount = Decimal("0.00")

        if self.apply_tds and self.tds and self.business and self.business.tds:
            rate = Decimal(str(self.tds.rate or 0))
            tds_base = self.get_taxable_amount()
            self.tds_amount = (tds_base * rate / Decimal("100")).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
            total_amount -= self.tds_amount
        else:
            self.tds_amount = Decimal("0.00")

        return total_amount.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)


    def get_taxable_amount(self):
        # Convert each price item to Decimal before summing
        total_amount = sum(Decimal(item.get_price_item()) for item in self.purchase_items.all())
        
        # Use 0 if discount is None
        discount = self.discount if self.discount is not None else 0
        
        if discount >= 0:
            discount_amount = total_amount * Decimal(discount / 100)  # Discount is a percentage
            total_amount -= discount_amount  # Subtract discount from total amount
        
        return total_amount

    
    def get_balance_amount(self):
        if self.apply_tds:
            total_amount = self.get_total_payable_amount()
        else:
            total_amount = self.get_total_amount()
        amount_received = Decimal(self.amount_received or 0)
        return total_amount - amount_received

    def transfer_balance_to_new_party(self, old_party,balance_amount):
        # total_amount = self.get_total_amount()  # Get total amount from the invoice
        new_party = self.party  # The new party to receive the amount
        print(f"Old Party Balance before: {old_party.closing_balance}")
        print(f"New Party Balance before: {new_party.closing_balance}")

        # # Step 1: Deduct the balance from the old party (only once)
        if old_party.balance_type == 'To Pay':
            old_party.closing_balance -= balance_amount
            if old_party.closing_balance < 0:
                old_party.balance_type = 'To Collect'
                old_party.closing_balance = abs(old_party.closing_balance)
        elif old_party.balance_type == 'To Collect':
            old_party.closing_balance += balance_amount
        
        # # Step 2: Add the balance from the old party (only once)
        if new_party.balance_type == 'To Pay':
            new_party.closing_balance += balance_amount
            if new_party.closing_balance < 0:
                new_party.balance_type = 'To Collect'
                new_party.closing_balance = abs(new_party.closing_balance)
        elif new_party.balance_type == 'To Collect':
            new_party.closing_balance -= balance_amount


        old_party.save()  # Save the old party after the deduction
        print(f"Old party balance reduced by: {balance_amount}")

        # # Save the new party once to avoid duplication
        new_party.save()  # Save the new party after the correct balance update
        # print(f"New party balance updated with: {remaining_amount}")

        print(f"Old Party Balance after: {old_party.closing_balance}")
        print(f"New Party Balance after: {new_party.closing_balance}")

    def delete(self, *args, **kwargs):
        # Handle necessary clean up before deleting the invoice or invoice item
        self.reverse_previous_balance_impact()  # Example: Reverse balance impact for the party
        super().delete(*args, **kwargs)

    def make_payment(self, total_payment_amount):
        """
        Method to handle payment logic without calling the full save method.
        It will update the `amount_received`, `balance_amount`, and status based on the payment.
        This method now returns the total payment amount used by this invoice.
        """
        self.balance_amount = self.get_balance_amount()  # Update balance amount

        # If the invoice balance is greater than the payment amount
        if self.balance_amount >= total_payment_amount:
            self.amount_received += total_payment_amount
            total_payment_amount = 0  # All the payment has been consumed
        else:
            # If the invoice balance is less than the payment amount, deduct the entire balance
            total_payment_amount -= self.balance_amount
            self.amount_received += self.balance_amount
            self.balance_amount = 0  # Invoice is fully paid

        self.is_fully_paid = self.balance_amount == 0  # Mark as fully paid if balance is zero
        self.update_status()  # Update the status (Paid/Partially Paid/Unpaid)

        # Save the updated invoice
        self.save(update_fields=['amount_received', 'balance_amount', 'is_fully_paid', 'status'])

        return total_payment_amount  # Return the remaining amount that can be used for other invoices
    
    class Meta:
        unique_together = ('business', 'purchase_no')  # or UniqueConstraint
        ordering = ['purchase_no']

    def __str__(self):
        return f"Purchase {self.purchase_no} - {self.party}"
    
    @classmethod
    def get_next_purchase_number(cls, business):
        """Generate the next invoice number for a business."""
        # Get the latest invoice for this specific business
        latest_purchase = cls.objects.filter(business=business).order_by('-id').first()
        
        if latest_purchase:
            # Extract the number part and increment
            last_number = int(latest_purchase.purchase_no)
            next_purchase_no = last_number + 1
        else:
            # First invoice for this business
            next_purchase_no = 1
            
        return next_purchase_no
        
class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, related_name='purchase_items', on_delete=models.CASCADE)
    item = models.ForeignKey(Item, null=True, blank=True, on_delete=models.CASCADE)  
    service = models.ForeignKey(Service, null=True, blank=True, on_delete=models.CASCADE)  # For services
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Unit price for both products and services
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Total amount for the item or service
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Discount in percentage.")
    price_item = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Price of item/service before tax
    gstTaxRate = models.ForeignKey(GSTTaxRate, on_delete=models.SET_NULL, null=True)
    stock_updated = models.BooleanField(default=False)  # Flag to track if stock has been updated
    
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
            return (Decimal(self.get_price_item()) * tax_rate)
        return Decimal(0)

    def get_cess_rate_amount(self):
        """Calculate cess amount."""
        if self.gstTaxRate:
            cess_rate = self.gstTaxRate.cess_rate / 100 if self.gstTaxRate else 0
            return (Decimal(self.get_price_item()) * cess_rate)
        return Decimal(0)
    
    def get_cgst_amount(self):
        """Calculate GST tax amount."""
        if self.gstTaxRate:
            tax_rate = self.gstTaxRate.rate / 200 if self.gstTaxRate else 0
            return (Decimal(self.get_price_item()) * tax_rate)
        return Decimal(0)

    def get_sgst_amount(self):
        """Calculate cess amount."""
        if self.gstTaxRate:
            tax_rate = self.gstTaxRate.rate / 200 if self.gstTaxRate else 0
            return (Decimal(self.get_price_item()) * tax_rate)
        return Decimal(0)
    
    def get_igst_amount(self):
        """Calculate IGST tax amount."""
        if self.gstTaxRate:
            igst_rate = self.gstTaxRate.rate / 100 if self.gstTaxRate else 0  # IGST uses full rate
            return (Decimal(self.get_price_item()) * igst_rate)
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
            if self.item.purchasePriceType == "With Tax":
                return (self.item.purchasePriceType)
            return (self.item.purchasePriceType)  # Already tax-exclusive
        elif self.service:
             if self.service.salesPriceType == "With Tax":
                return 0  # Service price * quantity
    
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

            return 0.0       
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
        
            return 0.0
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
                    available_stock = self.item.closingStock + self.quantity
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
            self.unit_price = self.item.purchasePrice  # For products
            self.price_item = self.item.purchasePrice  # Price of item before tax
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
            self.unit_price = 0  # For services
            self.price_item = 0  # Service price before tax
        
        self.amount = self.get_amount()  # Calculate the total amount (based on item or service)

        super().save(*args, **kwargs)

    def __str__(self):
        if self.item:
            return f"{self.item.itemName} ({self.quantity} * {self.unit_price})"
        elif self.service:
            return f"{self.service.serviceName} ({self.quantity} * {self.unit_price})"
        return "Unknown Item or Service"


class PaymentOut(models.Model):
    PAYMENT_MODE = (
        ('Cash', "Cash"),
        ('UPI', "UPI"),
        ('Card', "Card"),
        ('Netbanking', "Netbanking"),
        ('Bank Transfer', "Bank Transfer"),
        ('Cheque', "Cheque"),
    )
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='paymentout')
    party = models.ForeignKey(Party, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=False)
    payment_mode = models.CharField(max_length=100, choices=PAYMENT_MODE)
    payment_out_number = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(blank=True, null=True)
    bank_account = models.ForeignKey(
    'cash_and_bank.BankAccount',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='payment_outs'
)

    # Many-to-Many with extra data (through model)
    settled_purchase = models.ManyToManyField(
        'Purchase',
        through='PaymentOutPurchase',
        related_name='payments_settled',
        blank=True
    )

    def adjust_party_balance(self, remaining_amount):
        if self.party.balance_type == "To Collect":
            if self.party.closing_balance >= remaining_amount:
                self.party.closing_balance -= remaining_amount
            else:
                remaining_amount -= self.party.closing_balance
                self.party.closing_balance = 0
                self.party.balance_type = "To Pay"
                self.party.closing_balance = remaining_amount
        else:
            self.party.closing_balance += remaining_amount

        self.party.save()

    

    class Meta:
        unique_together = ('business', 'payment_out_number')  # or UniqueConstraint
        ordering = ['payment_out_number']

    
    def __str__(self):
        return f"PaymentOut {self.party} - {self.payment_out_number}"

    @classmethod
    def get_next_payment_out_number(cls, business):
        """Generate the next invoice number for a business."""
        # Get the latest invoice for this specific business
        latest_purchase = cls.objects.filter(business=business).order_by('-id').first()
        
        if latest_purchase:
            # Extract the number part and increment
            last_number = int(latest_purchase.payment_out_number)
            next_purchase_no = last_number + 1
        else:
            # First invoice for this business
            next_purchase_no = 1
            
        return next_purchase_no
        

class PaymentOutPurchase(models.Model):
    payment_out = models.ForeignKey(PaymentOut, on_delete=models.CASCADE)
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE)
    purchase_amount = models.DecimalField(max_digits=10, decimal_places=2)
    settled_amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Payment {self.payment_out.payment_out_number} - Purchase {self.purchase.purchase_no}"

 
class PurchaseReturn(models.Model):
    STATUS_CHOICES = [
        ('Unpaid', 'Unpaid'),
        ('Partially Paid', 'Partially Paid'),
        ('Paid', 'Paid')
    ]
    
    PAYMENT_METHOD_CHOICES = (
        ('Cash', "Cash"),
        ('UPI', "UPI"),
        ('Card', "Card"),
        ('Netbanking', "Netbanking"),
        ('Bank Transfer', "Bank Transfer"),
        ('Cheque', "Cheque"),
    )

    TCS_ON_CHOICES = (
        ('taxable', 'taxable'),
        ('total', 'total'),
    )
    
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='purchasereturn')
    purchasereturn_no = models.CharField(max_length=50)
    date = models.DateField(auto_now_add=False)
    party = models.ForeignKey(Party, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Unpaid')
    is_fully_paid = models.BooleanField(default=False, help_text="Mark as fully paid")
    amount_received = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Amount received")
    balance_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Balance Amount")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Total Amount")
    taxable_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Taxable Amount")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES,  default='Cash', blank=True, null=True)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0,blank=True , null=True, help_text="Discount in percentage.")
    notes = models.TextField(blank=True,null=True)
    signature = models.ImageField(upload_to='static/images/', null=True, blank=True)
    purchase_id = models.PositiveIntegerField()
    purchase_no = models.PositiveIntegerField(blank=True, null= True)
    total_payable_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Total Payable Amount")
    bank_account = models.ForeignKey('cash_and_bank.BankAccount', on_delete=models.SET_NULL, null=True, blank=True, related_name='purchasereturn')
    
    apply_tcs = models.BooleanField(default=False)
    tcs = models.ForeignKey('sales.Tcs' ,on_delete=models.SET_NULL, blank=True , null=True, related_name='purchasereturn_tcs')
    tcs_on = models.CharField(max_length=20, choices=TCS_ON_CHOICES,default='total',help_text="Apply TCS on either taxable or total amount")
    tcs_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="TCS Amount")

    apply_tds = models.BooleanField(default=False)
    tds = models.ForeignKey('sales.Tds', on_delete=models.SET_NULL, blank=True, null=True, related_name='purchasereturn_tds')
    tds_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)


    
    def save(self, *args, **kwargs):
        is_new = not self.pk  # Check if this is a new instance
        if is_new:
            super().save(*args, **kwargs)  # Save the object to generate primary key
            self.create_invoice(*args, **kwargs)  # Handle logic specific to new invoice
        else:
            self.update_invoice(*args, **kwargs)  # Handle update logic for existing invoice
        
        self.balance_amount = self.get_balance_amount()
        self.taxable_amount = self.get_taxable_amount()
        self.total_amount = self.get_total_amount()
        self.tcs_amount = self.get_tcs_amount()
        self.tds_amount = self.get_tds_amount()
        self.total_payable_amount = self.get_total_payable_amount()
         # Only save the object once after logic is handled
        # If any specific fields are updated, use `update_fields` to save only those fields
        super().save(update_fields=['status', 'amount_received', 'total_amount','balance_amount', 'payment_method', 'is_fully_paid', 'notes', 'discount', 'signature','business','purchase_id','purchase_no','tcs_amount','tds_amount','taxable_amount','business' ,'total_payable_amount','tcs','apply_tcs','tds','apply_tds','bank_account'])


    def create_invoice(self, *args, **kwargs):
        """Handles the creation of a new invoice."""
        print("new save --")
        try:
            print(self.purchase_id)
            purchase = Purchase.objects.get(id=self.purchase_id)
        except Purchase.DoesNotExist:
            # Handle the error, maybe log it or raise a custom exception
            print(f"Invoice with id {self.purchase_id} does not exist.")
            return  # or raise an exception
        self.purchase_no = purchase.purchase_no
        # After saving the invoice, handle balance and payment status for the new invoice
        if self.is_fully_paid:
            self.handle_fully_paid()
        elif self.amount_received > 0:
            self.handle_partially_paid()
        else:
            self.handle_unpaid()

        # Update the status of the invoice
        self.update_status()

    def update_invoice(self, *args, **kwargs):
        """Handles updating an existing invoice."""
        print("old invoice -- 1")
        # Reverse previous balance impact when updating an existing invoice
        self.reverse_previous_balance_impact()

        # Handle balance and payment status based on current state
        if self.is_fully_paid:
            self.handle_fully_paid()
        elif self.amount_received > 0:
            self.handle_partially_paid()
        else:
            self.handle_unpaid()

        # Update the status of the invoice
        self.update_status()

    def handle_fully_paid(self):
        # ✅ Scenario 1 & Scenario 4: Fully Paid (at creation or after edit)
        # No balance changes to the party
        self.status = 'Paid'
        if self.apply_tds and self.tds and self.business and self.business.tds:
            self.amount_received = self.get_total_payable_amount()
        else:
            self.amount_received = self.get_total_amount()
        print("paid success")

    def handle_partially_paid(self):
    # ✅ Scenario 3 & Scenario 5: Partially Paid
        # total_amount = self.get_total_amount()  # Get the total amount of the sales return
        if self.apply_tds and self.tds and self.business and self.business.tds:
           total_amount = self.get_total_payable_amount()
        else:
            total_amount = self.get_total_amount()
        print(f"Total Amount: {total_amount}")  # Debugging line
        
        # Ensure that the remaining amount cannot be negative
        if total_amount < 0:
            total_amount = 0  # Ensure the total amount isn't negative (this is just a safeguard)

        remaining_amount = total_amount - self.amount_received  # Calculate the remaining amount
        print(f"Remaining Amount: {remaining_amount}, Amount Received: {self.amount_received}")  # Debugging line

        # If the remaining amount is negative, we correct it to 0
        if remaining_amount < 0:
            remaining_amount = 0
            print(f"Adjusted Remaining Amount: {remaining_amount}")  # Debugging line

        # Step 1: Deduct from To Pay (if any balance exists)
        if self.party.balance_type == 'To Pay' and self.party.closing_balance > 0:
            # If the remaining amount is greater than or equal to closing_balance, adjust accordingly
            if remaining_amount >= self.party.closing_balance:
                remaining_amount -= self.party.closing_balance  # Reduce the remaining amount
                self.party.closing_balance = 0  # Clear the opening balance
                self.party.balance_type = 'To Collect'  # Set the balance type to 'To Pay'
            else:
                # If the remaining amount is less than the closing_balance, reduce the opening balance
                self.party.closing_balance -= remaining_amount
                remaining_amount = 0  # Set the remaining amount to zero as it's fully accounted for

        # Step 2: Add remaining amount (if any) to To Collect
        if remaining_amount > 0:
            # If there's any remaining amount after deduction, add it to the To Collect balance
            if self.party.balance_type == 'To Pay' and self.party.closing_balance == 0:
                self.party.balance_type = 'To Collect'  # Change the balance type to 'To Pay' if it's zero
            self.party.closing_balance += remaining_amount  # Add the remaining amount to the opening balance

        self.party.save()  # Save the updated party balance
        self.status = 'Partially Paid'  # Set the invoice status to 'Partially Paid'
        print(f"Party Balance After Partial Payment: {self.party.closing_balance}")  # Debugging line
        print("Partially paid success")

    def handle_unpaid(self):
        # ✅ Scenario 2 & Scenario 6: Unpaid
        # total_amount = self.get_total_amount()
        if self.apply_tds and self.tds and self.business and self.business.tds:
           total_amount = self.get_total_payable_amount() 
        else:
            total_amount = self.get_total_amount()
        print(f"Total Amount: {total_amount}")  # Debugging line
        remaining_amount = total_amount

        # Step 1: Deduct from To Pay
        if self.party.balance_type == 'To Pay' and self.party.closing_balance > 0:
            if remaining_amount >= self.party.closing_balance:
                remaining_amount -= self.party.closing_balance
                self.party.closing_balance = 0
                self.party.balance_type = 'To Collect'
            else:
                self.party.closing_balance -= remaining_amount
                remaining_amount = 0

        # Step 2: Add remaining amount (if any) to To Collect
        if remaining_amount > 0:
            if self.party.balance_type == 'To Pay' and self.party.closing_balance == 0:
                self.party.balance_type = 'To Collect'
            self.party.closing_balance += remaining_amount

        self.party.save()
        self.status = 'Unpaid'
        print("Unpaid success")

    def reverse_previous_balance_impact(self):
        # ✅ Reverse any previous balance impact based on the old status
        try:
            old_invoice = PurchaseReturn.objects.get(pk=self.pk)
        except PurchaseReturn.DoesNotExist:
            # Handle the case where the old invoice doesn't exist (shouldn't happen in a valid state)
            print("Old invoice does not exist.")
            return
        

        # Case 1: Fully Paid - No impact to reverse
        if old_invoice.status == 'Paid':
            return

        # Case 2: Unpaid or Partially Paid
        if old_invoice.status in ['Unpaid', 'Partially Paid']:
            # total_amount = old_invoice.get_total_amount()
            if old_invoice.apply_tds and old_invoice.tds and old_invoice.business and old_invoice.business.tds:
                total_amount = old_invoice.total_payable_amount
            else:
                total_amount = old_invoice.total_amount
            received_amount = old_invoice.amount_received  # Should be set correctly during the save
            balance_amount = total_amount - received_amount  # Should be set correctly during the save

            print(f"Total Amount: {total_amount}")
            print(f"Received Amount: {received_amount}")
            print(f"Balance Amount: {balance_amount}")
            print(f"Old invoice status: {old_invoice.status}")

            # Reverse impact based on the old balance type
            if old_invoice.status == 'Unpaid':
                self.reverse_unpaid_balance(total_amount)
            elif old_invoice.status == 'Partially Paid':
                self.reverse_partially_paid_balance(balance_amount)
            
        old_party = old_invoice.party
        if old_party != self.party:
            print("Party changed. Reversing old party balance impact.")
            self.transfer_balance_to_new_party(old_party,balance_amount)

    def reverse_unpaid_balance(self, total_amount):
        # ✅ Reverse the unpaid logic impact
        if self.party.balance_type == 'To Collect':
            self.party.closing_balance -= total_amount
            if self.party.closing_balance < 0:
                self.party.balance_type = 'To Pay'
                self.party.closing_balance = abs(self.party.closing_balance)
        elif self.party.balance_type == 'To Pay':
            self.party.closing_balance += total_amount
        self.party.save()

    def reverse_partially_paid_balance(self, received_amount):
        print("Reverse the partially paid logic impact based on previous payments")
        if self.party.balance_type == 'To Collect':
            self.party.closing_balance -= received_amount
            if self.party.closing_balance < 0:
                self.party.balance_type = 'To Pay'
                self.party.closing_balance = abs(self.party.closing_balance)
        elif self.party.balance_type == 'To Pay':
            self.party.closing_balance += received_amount
        self.party.save()

    def update_status(self):
        total_amount = self.get_total_amount()
        if self.is_fully_paid or self.amount_received >= total_amount:
            self.status = 'Paid'
        elif self.amount_received > 0:
            self.status = 'Partially Paid'
        else:
            self.status = 'Unpaid'
        print(self.status)

    def get_tcs_amount(self):
        if self.apply_tcs and self.tcs and self.business and self.business.tcs:
            rate = self.tcs.rate or Decimal('0.00')

            if self.tcs_on == 'total':
                base_amount = self.get_total_amount(without_tcs=True)
            else:
                base_amount = self.get_taxable_amount()

            return (base_amount * rate / Decimal('100.00')).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)

        return Decimal("0.00")
    
    def get_tds_amount(self):
        if self.apply_tds and self.tds and self.business and self.business.tds:
            rate = self.tds.rate or Decimal('0.00')
            base = self.get_taxable_amount()
            return (base * rate / Decimal('100.00')).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
        return Decimal("0.00")


    def get_total_amount(self, without_tcs=False):
        total_amount = sum(Decimal(str(item.get_amount())) for item in self.purchasereturn_items.all())

        discount = Decimal(self.discount or 0)
        if discount > 0:
            total_amount -= (total_amount * (discount / Decimal("100")))

        # Ensure total_amount is Decimal before quantizing
        total_amount = Decimal(total_amount)

        if not without_tcs and self.apply_tcs and self.tcs and self.business and self.business.tcs:
            rate = Decimal(str(self.tcs.rate or 0))
            tcs_base = self.get_taxable_amount() if self.tcs_on == 'taxable' else total_amount
            self.tcs_amount = (tcs_base * rate / Decimal("100")).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
            total_amount += self.tcs_amount
        else:
            self.tcs_amount = Decimal("0.00")

        return total_amount.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
    
    def get_total_payable_amount(self, without_tcs=False):
        total_amount = sum(Decimal(str(item.get_amount())) for item in self.purchasereturn_items.all())

        discount = Decimal(self.discount or 0)
        if discount > 0:
            total_amount -= (total_amount * (discount / Decimal("100")))

        # Ensure total_amount is Decimal before quantizing
        total_amount = Decimal(total_amount)

        if not without_tcs and self.apply_tcs and self.tcs and self.business and self.business.tcs:
            rate = Decimal(str(self.tcs.rate or 0))
            tcs_base = self.get_taxable_amount() if self.tcs_on == 'taxable' else total_amount
            self.tcs_amount = (tcs_base * rate / Decimal("100")).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
            total_amount += self.tcs_amount
        else:
            self.tcs_amount = Decimal("0.00")

        if self.apply_tds and self.tds and self.business and self.business.tds:
            rate = Decimal(str(self.tds.rate or 0))
            tds_base = self.get_taxable_amount()
            self.tds_amount = (tds_base * rate / Decimal("100")).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
            total_amount -= self.tds_amount
        else:
            self.tds_amount = Decimal("0.00")

        return total_amount.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)


    def get_taxable_amount(self):
        # Convert each price item to Decimal before summing
        total_amount = sum(Decimal(item.get_price_item()) for item in self.purchasereturn_items.all())
        
        # Use 0 if discount is None
        discount = self.discount if self.discount is not None else 0
        
        if discount >= 0:
            discount_amount = total_amount * Decimal(discount / 100)  # Discount is a percentage
            total_amount -= discount_amount  # Subtract discount from total amount
        
        return total_amount

    
    def get_balance_amount(self):
        if self.apply_tds:
            total_amount = self.get_total_payable_amount()
        else:
            total_amount = self.get_total_amount()
        amount_received = Decimal(self.amount_received or 0)
        return total_amount - amount_received
    
    def transfer_balance_to_new_party(self, old_party,balance_amount):
        # total_amount = self.get_total_amount()  # Get total amount from the invoice
        new_party = self.party  # The new party to receive the amount
        print(f"Old Party Balance before: {old_party.closing_balance}")
        print(f"New Party Balance before: {new_party.closing_balance}")

        # # Step 1: Deduct the balance from the old party (only once)
        if old_party.balance_type == 'To Collect':
            old_party.closing_balance -= balance_amount
            if old_party.closing_balance < 0:
                old_party.balance_type = 'To Pay'
                old_party.closing_balance = abs(old_party.closing_balance)
        elif old_party.balance_type == 'To Pay':
            old_party.closing_balance += balance_amount
        
        # # Step 2: Add the balance from the old party (only once)
        if new_party.balance_type == 'To Collect':
            new_party.closing_balance += balance_amount
            if new_party.closing_balance < 0:
                new_party.balance_type = 'To Pay'
                new_party.closing_balance = abs(new_party.closing_balance)
        elif new_party.balance_type == 'To Pay':
            new_party.closing_balance -= balance_amount


        old_party.save()  # Save the old party after the deduction
        print(f"Old party balance reduced by: {balance_amount}")

        # # Save the new party once to avoid duplication
        new_party.save()  # Save the new party after the correct balance update
        print(f"Old Party Balance after: {old_party.closing_balance}")
        print(f"New Party Balance after: {new_party.closing_balance}")

    def delete(self, *args, **kwargs):
        # Handle necessary clean up before deleting the invoice or invoice item
        self.reverse_previous_balance_impact()  # Example: Reverse balance impact for the party
        super().delete(*args, **kwargs)
    
    class Meta:
        unique_together = ('business', 'purchasereturn_no')  # or UniqueConstraint
        ordering = ['purchasereturn_no']
    
    def __str__(self):
        return f"Purchasereturn {self.purchasereturn_no} - {self.party}"
    
    @classmethod
    def get_next_purchase_return_number(cls, business):
        """Generate the next invoice number for a business."""
        # Get the latest invoice for this specific business
        latest_purchase = cls.objects.filter(business=business).order_by('-id').first()
        
        if latest_purchase:
            # Extract the number part and increment
            last_number = int(latest_purchase.purchasereturn_no)
            next_purchase_no = last_number + 1
        else:
            # First invoice for this business
            next_purchase_no = 1
            
        return next_purchase_no
        
    
class PurchaseReturnItem(models.Model):
    purchasereturn = models.ForeignKey(PurchaseReturn, related_name='purchasereturn_items', on_delete=models.CASCADE)
    item = models.ForeignKey(Item, null=True, blank=True, on_delete=models.CASCADE)  # For products
    service = models.ForeignKey(Service, null=True, blank=True, on_delete=models.CASCADE)  # For services
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Unit price for both products and services
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Total amount for the item or service
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Discount in percentage.")
    price_item = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Price of item/service before tax
    gstTaxRate = models.ForeignKey(GSTTaxRate, on_delete=models.SET_NULL, null=True)
    
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
            return (Decimal(self.get_price_item()) * tax_rate)
        return Decimal(0)

    def get_cess_rate_amount(self):
        """Calculate cess amount."""
        if self.gstTaxRate:
            cess_rate = self.gstTaxRate.cess_rate / 100 if self.gstTaxRate else 0
            return (Decimal(self.get_price_item()) * cess_rate)
        return Decimal(0)
    
    def get_cgst_amount(self):
        """Calculate GST tax amount."""
        if self.gstTaxRate:
            tax_rate = self.gstTaxRate.rate / 200 if self.gstTaxRate else 0
            return (Decimal(self.get_price_item()) * tax_rate)
        return Decimal(0)

    def get_sgst_amount(self):
        """Calculate cess amount."""
        if self.gstTaxRate:
            tax_rate = self.gstTaxRate.rate / 200 if self.gstTaxRate else 0
            return (Decimal(self.get_price_item()) * tax_rate)
        return Decimal(0)
    
    def get_igst_amount(self):
        """Calculate IGST tax amount."""
        if self.gstTaxRate:
            igst_rate = self.gstTaxRate.rate / 100 if self.gstTaxRate else 0  # IGST uses full rate
            return (Decimal(self.get_price_item()) * igst_rate)
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
            if self.item.purchasePriceType == "With Tax":
                return (self.item.purchasePriceType)
            return (self.item.purchasePriceType)  # Already tax-exclusive
        elif self.service:
            return 0
        return 0  # Service price * quantity
    
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
        total_amount = 0.0

        if self.item:
            if self.item.salesPriceType == "Without Tax":
                price_with_tax = self.calculate_price(self.item.purchasePrice, "Without Tax")
                total_amount = round(price_with_tax * self.quantity, 2)
            else:
                total_amount = round(self.item.purchasePrice * self.quantity, 2)  # Already tax-inclusive

            # Apply the discount to the total amount (if any)
            if self.discount > 0:
                discount_amount = total_amount * (self.discount / 100)  # Discount is a percentage
                total_amount -= discount_amount  # Subtract discount from total amount

        elif self.service:
            return 0.0
        return round(total_amount, 2)  # Return the final amount, rounded to two decimal places

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
            
            return 0.0
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
                    available_stock = self.item.closingStock + self.quantity
                else:
                    available_stock = 0  # Out-of-stock for products
                # Store the result in cache for 15 minutes (adjustable)
                cache.set(cache_key, available_stock, timeout=60*15)
            if available_stock <= 0:
                raise ValidationError(f"Not enough stock for {self.item.itemName}. Available stock: {self.item.closingStock}")
            return available_stock
        return None  # Services don't have stock management

    def save(self, *args, **kwargs):
        """Override save method to calculate amount and unit price for both items and services."""
        self.full_clean()  # Ensure validation
        if self.item:
            self.unit_price = self.item.purchasePrice  # For products
            self.price_item = self.item.purchasePrice  # Price of item before tax
            # Check if sufficient stock is available and update
            available_stock = self.get_available_stock()
            if available_stock >= 0:
                self.item.closingStock = available_stock
                self.item.save()  # Persist the updated stock to the database
                # Invalidate the cache for this item
                cache_key = f'item_{self.item.id}_stock'
                cache.delete(cache_key)  # Clear the old cached value
                # Optionally, you could also update the cache with the new stock value
                cache.set(cache_key, self.item.closingStock, timeout=60*15)
            else:
                raise ValidationError("Not enough stock available.")
        elif self.service:
            self.unit_price = 0  # For services
            self.price_item = 0  # Service price before tax
        self.amount = self.get_amount()  # Calculate the total amount (based on item or service)

        super().save(*args, **kwargs)
    
    def __str__(self):
        if self.item:
            return f"{self.item.itemName} ({self.quantity} * {self.unit_price})"
        elif self.service:
            return f"{self.service.serviceName} ({self.quantity} * {self.unit_price})"
        return "Unknown Item or Service"


class DebitNote(models.Model):
    STATUS_CHOICES = [
        ('Unpaid', 'Unpaid'),
        ('Partially Paid', 'Partially Paid'),
        ('Paid', 'Paid')
    ]
    
    PAYMENT_METHOD_CHOICES = (
        ('Cash', "Cash"),
        ('UPI', "UPI"),
        ('Card', "Card"),
        ('Netbanking', "Netbanking"),
        ('Bank Transfer', "Bank Transfer"),
        ('Cheque', "Cheque"),
    )
    
    TCS_ON_CHOICES = (
        ('taxable', 'taxable'),
        ('total', 'total'),
    )
    
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='debitnote')
    debitnote_no = models.CharField(max_length=50)
    date = models.DateField(auto_now_add=False)
    party = models.ForeignKey(Party, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Unpaid')
    is_fully_paid = models.BooleanField(default=False, help_text="Mark as fully paid")
    amount_received = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Amount received")
    balance_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Balance Amount")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Total Amount")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES,  default='Cash', blank=True, null=True)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0,blank=True , null=True, help_text="Discount in percentage.")
    taxable_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Taxable Amount")
    notes = models.TextField(blank=True,null=True)
    signature = models.ImageField(upload_to='static/images/', null=True, blank=True)
    purchasereturn_id = models.PositiveIntegerField()
    purchasereturn_no = models.PositiveIntegerField(blank=True,null=True)
    total_payable_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Total Payable Amount")
    bank_account = models.ForeignKey('cash_and_bank.BankAccount', on_delete=models.SET_NULL, null=True, blank=True, related_name='debitnote')
    
    apply_tcs = models.BooleanField(default=False)
    tcs = models.ForeignKey('sales.Tcs',on_delete=models.SET_NULL, blank=True , null=True, related_name='debitnote_tcs')
    tcs_on = models.CharField(max_length=20, choices=TCS_ON_CHOICES,default='total',help_text="Apply TCS on either taxable or total amount")
    tcs_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="TCS Amount")
    
    apply_tds = models.BooleanField(default=False)
    tds = models.ForeignKey('sales.Tds', on_delete=models.SET_NULL, blank=True, null=True, related_name='debitnote_tds')
    tds_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    
    def save(self, *args, **kwargs):
        is_new = not self.pk  # Check if this is a new instance

        if is_new:
            super().save(*args, **kwargs)  # Save the object to generate primary key
            self.create_invoice(*args, **kwargs)  # Handle logic specific to new invoice
        else:
            self.update_invoice(*args, **kwargs)  # Handle update logic for existing invoice
        
        self.balance_amount = self.get_balance_amount()
        self.taxable_amount = self.get_taxable_amount()
        self.total_amount = self.get_total_amount()
        self.tcs_amount = self.get_tcs_amount()
        self.tds_amount = self.get_tds_amount()
        self.total_payable_amount = self.get_total_payable_amount()
        
        # Only save the object once after logic is handled
        # If any specific fields are updated, use `update_fields` to save only those fields
        super().save(update_fields=['purchasereturn_no','party','debitnote_no', 'status', 'amount_received','total_amount','balance_amount' ,'is_fully_paid', 'notes', 'discount', 'payment_method', 'tcs_amount','tds_amount','taxable_amount','business' , 'total_payable_amount','tcs','apply_tcs','tds','apply_tds','bank_account'])

    def create_invoice(self, *args, **kwargs):
        """Handles the creation of a new invoice."""
        print("new save --")
        try:
            print(self.purchasereturn_id)
            purchasereturn = PurchaseReturn.objects.get(id=self.purchasereturn_id)
        except PurchaseReturn.DoesNotExist:
            # Handle the error, maybe log it or raise a custom exception
            print(f"purchase return with id {self.purchasereturn_id} does not exist.")
            return  # or raise an exception
        self.purchasereturn_no = purchasereturn.purchasereturn_no
        # After saving the invoice, handle balance and payment status for the new invoice
        if self.is_fully_paid:
            self.handle_fully_paid()
        elif self.amount_received > 0:
            self.handle_partially_paid()
        else:
            self.handle_unpaid()

        # Update the status of the invoice
        self.update_status()

    def update_invoice(self, *args, **kwargs):
        """Handles updating an existing invoice."""
        print("old invoice -- 1")
        # Reverse previous balance impact when updating an existing invoice
        self.reverse_previous_balance_impact()

        # Handle balance and payment status based on current state
        if self.is_fully_paid:
            self.handle_fully_paid()
        elif self.amount_received > 0:
            self.handle_partially_paid()
        else:
            self.handle_unpaid()

        # Update the status of the invoice
        self.update_status()

    def handle_fully_paid(self):
        # ✅ Scenario 1 & Scenario 4: Fully Paid (at creation or after edit)
        # No balance changes to the party
        self.status = 'Paid'
        if self.apply_tds and self.tds and self.business and self.business.tds:
            self.amount_received = self.get_total_payable_amount()
        else:
            self.amount_received = self.get_total_amount()
        print("paid success")
        print("paid success")

    def handle_partially_paid(self):
    # ✅ Scenario 3 & Scenario 5: Partially Paid
        if self.apply_tds and self.tds and self.business and self.business.tds:
           total_amount = self.get_total_payable_amount()
        else:
            total_amount = self.get_total_amount()
        print(f"Total Amount: {total_amount}")  # Debugging line
        

        # Ensure that the remaining amount cannot be negative
        if total_amount < 0:
            total_amount = 0  # Ensure the total amount isn't negative (this is just a safeguard)

        remaining_amount = total_amount - self.amount_received  # Calculate the remaining amount
        print(f"Remaining Amount: {remaining_amount}, Amount Received: {self.amount_received}")  # Debugging line

        # If the remaining amount is negative, we correct it to 0
        if remaining_amount < 0:
            remaining_amount = 0
            print(f"Adjusted Remaining Amount: {remaining_amount}")  # Debugging line

        # Step 1: Deduct from To Pay (if any balance exists)
        if self.party.balance_type == 'To Pay' and self.party.closing_balance > 0:
            # If the remaining amount is greater than or equal to closing_balance, adjust accordingly
            if remaining_amount >= self.party.closing_balance:
                remaining_amount -= self.party.closing_balance  # Reduce the remaining amount
                self.party.closing_balance = 0  # Clear the opening balance
                self.party.balance_type = 'To Collect'  # Set the balance type to 'To Pay'
            else:
                # If the remaining amount is less than the closing_balance, reduce the opening balance
                self.party.closing_balance -= remaining_amount
                remaining_amount = 0  # Set the remaining amount to zero as it's fully accounted for

        # Step 2: Add remaining amount (if any) to To Collect
        if remaining_amount > 0:
            # If there's any remaining amount after deduction, add it to the To Collect balance
            if self.party.balance_type == 'To Pay' and self.party.closing_balance == 0:
                self.party.balance_type = 'To Collect'  # Change the balance type to 'To Pay' if it's zero
            self.party.closing_balance += remaining_amount  # Add the remaining amount to the opening balance

        self.party.save()  # Save the updated party balance
        self.status = 'Partially Paid'  # Set the invoice status to 'Partially Paid'
        print(f"Party Balance After Partial Payment: {self.party.closing_balance}")  # Debugging line
        print("Partially paid success")

    def handle_unpaid(self):
        # ✅ Scenario 2 & Scenario 6: Unpaid
        if self.apply_tds and self.tds and self.business and self.business.tds:
           total_amount = self.get_total_payable_amount()
        else:
            total_amount = self.get_total_amount()
        print(f"Total Amount: {total_amount}")  # Debugging line
        remaining_amount = total_amount

        # Step 1: Deduct from To Pay
        if self.party.balance_type == 'To Pay' and self.party.closing_balance > 0:
            if remaining_amount >= self.party.closing_balance:
                remaining_amount -= self.party.closing_balance
                self.party.closing_balance = 0
                self.party.balance_type = 'To Collect'
            else:
                self.party.closing_balance -= remaining_amount
                remaining_amount = 0

        # Step 2: Add remaining amount (if any) to To Collect
        if remaining_amount > 0:
            if self.party.balance_type == 'To Pay' and self.party.closing_balance == 0:
                self.party.balance_type = 'To Collect'
            self.party.closing_balance += remaining_amount

        self.party.save()
        self.status = 'Unpaid'
        print("Unpaid success")

    def reverse_previous_balance_impact(self):
        # ✅ Reverse any previous balance impact based on the old status
        try:
            old_invoice = DebitNote.objects.get(pk=self.pk)
        except DebitNote.DoesNotExist:
            # Handle the case where the old invoice doesn't exist (shouldn't happen in a valid state)
            print("Old invoice does not exist.")
            return
        

        # Case 1: Fully Paid - No impact to reverse
        if old_invoice.status == 'Paid':
            return

        # Case 2: Unpaid or Partially Paid
        if old_invoice.status in ['Unpaid', 'Partially Paid']:
            total_amount = old_invoice.get_total_amount()
            received_amount = old_invoice.amount_received  # Should be set correctly during the save
            balance_amount = total_amount - received_amount  # Should be set correctly during the save

            print(f"Total Amount: {total_amount}")
            print(f"Received Amount: {received_amount}")
            print(f"Balance Amount: {balance_amount}")
            print(f"Old invoice status: {old_invoice.status}")

            # Reverse impact based on the old balance type
            if old_invoice.status == 'Unpaid':
                self.reverse_unpaid_balance(total_amount)
            elif old_invoice.status == 'Partially Paid':
                self.reverse_partially_paid_balance(balance_amount)
            
        old_party = old_invoice.party
        if old_party != self.party:
            print("Party changed. Reversing old party balance impact.")
            self.transfer_balance_to_new_party(old_party,balance_amount)

    def reverse_unpaid_balance(self, total_amount):
        # ✅ Reverse the unpaid logic impact
        if self.party.balance_type == 'To Collect':
            self.party.closing_balance -= total_amount
            if self.party.closing_balance < 0:
                self.party.balance_type = 'To Pay'
                self.party.closing_balance = abs(self.party.closing_balance)
        elif self.party.balance_type == 'To Pay':
            self.party.closing_balance += total_amount
        self.party.save()

    def reverse_partially_paid_balance(self, received_amount):
        print("Reverse the partially paid logic impact based on previous payments")
        if self.party.balance_type == 'To Collect':
            self.party.closing_balance -= received_amount
            if self.party.closing_balance < 0:
                self.party.balance_type = 'To Pay'
                self.party.closing_balance = abs(self.party.closing_balance)
        elif self.party.balance_type == 'To Pay':
            self.party.closing_balance += received_amount
        self.party.save()

    def update_status(self):
        total_amount = self.get_total_amount()
        if self.is_fully_paid or self.amount_received >= total_amount:
            self.status = 'Paid'
        elif self.amount_received > 0:
            self.status = 'Partially Paid'
        else:
            self.status = 'Unpaid'
        print(self.status)
    
    def get_tcs_amount(self):
        if self.apply_tcs and self.tcs and self.business and self.business.tcs:
            rate = self.tcs.rate or Decimal('0.00')

            if self.tcs_on == 'total':
                base_amount = self.get_total_amount(without_tcs=True)
            else:
                base_amount = self.get_taxable_amount()

            return (base_amount * rate / Decimal('100.00')).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)

        return Decimal("0.00")
    
    def get_tds_amount(self):
        if self.apply_tds and self.tds and self.business and self.business.tds:
            rate = self.tds.rate or Decimal('0.00')
            base = self.get_taxable_amount()
            return (base * rate / Decimal('100.00')).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
        return Decimal("0.00")

    def get_total_amount(self, without_tcs=False):
        total_amount = sum(Decimal(str(item.get_amount())) for item in self.debitnote_items.all())

        discount = Decimal(self.discount or 0)
        if discount > 0:
            total_amount -= (total_amount * (discount / Decimal("100")))

        # Ensure total_amount is Decimal before quantizing
        total_amount = Decimal(total_amount)

        if not without_tcs and self.apply_tcs and self.tcs and self.business and self.business.tcs:
            rate = Decimal(str(self.tcs.rate or 0))
            tcs_base = self.get_taxable_amount() if self.tcs_on == 'taxable' else total_amount
            self.tcs_amount = (tcs_base * rate / Decimal("100")).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
            total_amount += self.tcs_amount
        else:
            self.tcs_amount = Decimal("0.00")

        return total_amount.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
    
    def get_total_payable_amount(self, without_tcs=False):
        total_amount = sum(Decimal(str(item.get_amount())) for item in self.debitnote_items.all())

        discount = Decimal(self.discount or 0)
        if discount > 0:
            total_amount -= (total_amount * (discount / Decimal("100")))

        # Ensure total_amount is Decimal before quantizing
        total_amount = Decimal(total_amount)

        if not without_tcs and self.apply_tcs and self.tcs and self.business and self.business.tcs:
            rate = Decimal(str(self.tcs.rate or 0))
            tcs_base = self.get_taxable_amount() if self.tcs_on == 'taxable' else total_amount
            self.tcs_amount = (tcs_base * rate / Decimal("100")).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
            total_amount += self.tcs_amount
        else:
            self.tcs_amount = Decimal("0.00")

        if self.apply_tds and self.tds and self.business and self.business.tds:
            rate = Decimal(str(self.tds.rate or 0))
            tds_base = self.get_taxable_amount()
            self.tds_amount = (tds_base * rate / Decimal("100")).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
            total_amount -= self.tds_amount
        else:
            self.tds_amount = Decimal("0.00")

        return total_amount.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)


    def get_taxable_amount(self):
        # Convert each price item to Decimal before summing
        total_amount = sum(Decimal(item.get_price_item()) for item in self.debitnote_items.all())
        
        # Use 0 if discount is None
        discount = self.discount if self.discount is not None else 0
        
        if discount >= 0:
            discount_amount = total_amount * Decimal(discount / 100)  # Discount is a percentage
            total_amount -= discount_amount  # Subtract discount from total amount
        
        return total_amount

    
    def get_balance_amount(self):
        if self.apply_tds:
            total_amount = self.get_total_payable_amount()
        else:
            total_amount = self.get_total_amount()
        amount_received = Decimal(self.amount_received or 0)
        return total_amount - amount_received

    def transfer_balance_to_new_party(self, old_party,balance_amount):
        # total_amount = self.get_total_amount()  # Get total amount from the invoice
        new_party = self.party  # The new party to receive the amount
        print(f"Old Party Balance before: {old_party.closing_balance}")
        print(f"New Party Balance before: {new_party.closing_balance}")

        # # Step 1: Deduct the balance from the old party (only once)
        if old_party.balance_type == 'To Collect':
            old_party.closing_balance -= balance_amount
            if old_party.closing_balance < 0:
                old_party.balance_type = 'To Pay'
                old_party.closing_balance = abs(old_party.closing_balance)
        elif old_party.balance_type == 'To Pay':
            old_party.closing_balance += balance_amount
        
        # # Step 2: Add the balance from the old party (only once)
        if new_party.balance_type == 'To Collect':
            new_party.closing_balance += balance_amount
            if new_party.closing_balance < 0:
                new_party.balance_type = 'To Pay'
                new_party.closing_balance = abs(new_party.closing_balance)
        elif new_party.balance_type == 'To Pay':
            new_party.closing_balance -= balance_amount


        old_party.save()  # Save the old party after the deduction
        print(f"Old party balance reduced by: {balance_amount}")

        # # Save the new party once to avoid duplication
        new_party.save()  # Save the new party after the correct balance update
        # print(f"New party balance updated with: {remaining_amount}")

        print(f"Old Party Balance after: {old_party.closing_balance}")
        print(f"New Party Balance after: {new_party.closing_balance}")

    def delete(self, *args, **kwargs):
        # Handle necessary clean up before deleting the invoice or invoice item
        self.reverse_previous_balance_impact()  # Example: Reverse balance impact for the party
        super().delete(*args, **kwargs)

    class Meta:
        unique_together = ('business', 'debitnote_no')  # or UniqueConstraint
        ordering = ['debitnote_no']

    @classmethod
    def get_next_purchase_debit_number(cls, business):
        """Generate the next invoice number for a business."""
        # Get the latest invoice for this specific business
        latest_purchase = cls.objects.filter(business=business).order_by('-id').first()
        
        if latest_purchase:
            # Extract the number part and increment
            last_number = int(latest_purchase.debitnote_no)
            next_purchase_no = last_number + 1
        else:
            # First invoice for this business
            next_purchase_no = 1
            
        return next_purchase_no
    
    def __str__(self):
        return f"DebitNote {self.debitnote_no} - {self.party}"
    
class DebitNoteItem(models.Model):
    debitnote = models.ForeignKey(DebitNote, related_name='debitnote_items', on_delete=models.CASCADE)
    item = models.ForeignKey(Item, null=True, blank=True, on_delete=models.CASCADE)  # For products
    service = models.ForeignKey(Service, null=True, blank=True, on_delete=models.CASCADE)  # For services
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Unit price for both products and services
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Total amount for the item or service
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Discount in percentage.")
    price_item = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Price of item/service before tax
    gstTaxRate = models.ForeignKey(GSTTaxRate, on_delete=models.SET_NULL, null=True)
    
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
            return (Decimal(self.get_price_item()) * tax_rate)
        return Decimal(0)

    def get_cess_rate_amount(self):
        """Calculate cess amount."""
        if self.gstTaxRate:
            cess_rate = self.gstTaxRate.cess_rate / 100 if self.gstTaxRate else 0
            return (Decimal(self.get_price_item()) * cess_rate)
        return Decimal(0)
    
    def get_cgst_amount(self):
        """Calculate GST tax amount."""
        if self.gstTaxRate:
            tax_rate = self.gstTaxRate.rate / 200 if self.gstTaxRate else 0
            return (Decimal(self.get_price_item()) * tax_rate)
        return Decimal(0)

    def get_sgst_amount(self):
        """Calculate cess amount."""
        if self.gstTaxRate:
            tax_rate = self.gstTaxRate.rate / 200 if self.gstTaxRate else 0
            return (Decimal(self.get_price_item()) * tax_rate)
        return Decimal(0)
    
    def get_igst_amount(self):
        """Calculate IGST tax amount."""
        if self.gstTaxRate:
            igst_rate = self.gstTaxRate.rate / 100 if self.gstTaxRate else 0  # IGST uses full rate
            return (Decimal(self.get_price_item()) * igst_rate)
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
            if self.item.purchasePriceType == "With Tax":
                return (self.item.purchasePriceType)
            return (self.item.purchasePriceType)  # Already tax-exclusive
        elif self.service:
            return 0
        return 0  # Service price * quantity
    
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
           
            return 0.0       
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
            # if self.service.purchasePriceType == "With Tax":
            #     price_without_tax =0
            #     total_price = 0
            # else:
            #     total_price = self.service.purchasePrice * self.quantity
            return 0.0
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
                    available_stock = self.item.closingStock + self.quantity
                else:
                    available_stock = 0  # Out-of-stock for products
                # Store the result in cache for 15 minutes (adjustable)
                cache.set(cache_key, available_stock, timeout=60*15)
            if available_stock <= 0:
                raise ValidationError(f"Not enough stock for {self.item.itemName}. Available stock: {self.item.closingStock}")
            return available_stock
        return None  # Services don't have stock management

    def save(self, *args, **kwargs):
        """Override save method to calculate amount and unit price for both items and services."""
        self.full_clean()  # Ensure validation
        if self.item:
            self.unit_price = self.item.purchasePrice  # For products
            self.price_item = self.item.purchasePrice  # Price of item before tax
            # Check if sufficient stock is available and update
            available_stock = self.get_available_stock()
            if available_stock >= 0:
                self.item.closingStock = available_stock
                self.item.save()  # Persist the updated stock to the database
                # Invalidate the cache for this item
                cache_key = f'item_{self.item.id}_stock'
                cache.delete(cache_key)  # Clear the old cached value
                # Optionally, you could also update the cache with the new stock value
                cache.set(cache_key, self.item.closingStock, timeout=60*15)
            else:
                raise ValidationError("Not enough stock available.")
        elif self.service:
            self.unit_price = 0  # For services
            self.price_item = 0  # Service price before tax
        self.amount = self.get_amount()  # Calculate the total amount (based on item or service)

        super().save(*args, **kwargs)
    
    def __str__(self):
        if self.item:
            return f"{self.item.itemName} ({self.quantity} * {self.unit_price})"
        elif self.service:
            return f"{self.service.serviceName} ({self.quantity} * {self.unit_price})"
        return "Unknown Item or Service"

    
class PurchaseOrder(models.Model):
    STATUS_CHOICES = (
        ('Open', "Open"),
        ('Closed', "Closed"),
    )
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='purchaseorder')
    purchase_order_no = models.CharField(max_length=50)
    date = models.DateField(auto_now_add=False)  
    party = models.ForeignKey(Party, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Open')
    payment_term= models.PositiveIntegerField(blank=True,null=True,default=30)
    balance_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Balance Amount")
    due_date = models.DateField(blank=True, null=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Total Amount")
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0,blank=True , null=True, help_text="Discount in percentage.")
    notes = models.TextField(blank=True,null=True)
    signature = models.ImageField(upload_to='static/signature/', null=True, blank=True)
    
    def save(self, *args, **kwargs):
        # Calculate due_date if payment_term is provided
        if self.date and self.payment_term:
            self.due_date = self.date + timedelta(days=self.payment_term)
            print(f"Calculated due_date: {self.due_date}")  # Log the due_date calculation
        is_new = not self.pk
        if is_new:
            # For new invoice, do the first save
            print("new save --")
            super().save(*args, **kwargs)
        self.total_amount = self.get_total_amount()
        self.balance_amount = self.get_total_amount()
        super().save(update_fields=['party', 'business','payment_term','status', 'balance_amount', 'total_amount','due_date', 'notes', 'discount'])

    def get_taxable_amount(self):
        # Convert each price item to Decimal before summing
        total_amount = sum(Decimal(item.get_price_item()) for item in self.purchaseorder_items.all())
        
        # Use 0 if discount is None
        discount = self.discount if self.discount is not None else 0
        
        if discount >= 0:
            discount_amount = total_amount * Decimal(discount / 100)  # Discount is a percentage
            total_amount -= discount_amount  # Subtract discount from total amount
        
        return total_amount
    
    
    def get_total_amount(self):
        # Convert each amount to Decimal before summing
        total_amount = sum(Decimal(item.get_amount()) for item in self.purchaseorder_items.all())
        
        # Use 0 if discount is None
        discount = self.discount if self.discount is not None else 0
        
        if discount >= 0:
            discount_amount = total_amount * Decimal(discount / 100)  # Discount is a percentage
            total_amount -= discount_amount  # Subtract discount from total amount
    
        return total_amount
    
    class Meta:
        unique_together = ('business', 'purchase_order_no')  # or UniqueConstraint
        ordering = ['purchase_order_no']
    
    def __str__(self):
        return f"PurchaseOrders {self.purchase_order_no} "
    
    @classmethod
    def get_next_purchase_order_number(cls, business):
        """Generate the next invoice number for a business."""
        # Get the latest invoice for this specific business
        latest_purchase = cls.objects.filter(business=business).order_by('-id').first()
        
        if latest_purchase:
            # Extract the number part and increment
            last_number = int(latest_purchase.purchase_order_no)
            next_purchase_no = last_number + 1
        else:
            # First invoice for this business
            next_purchase_no = 1
            
        return next_purchase_no
    
class PurchaseOrderItem(models.Model):
    purchaseorder = models.ForeignKey(PurchaseOrder, related_name='purchaseorder_items', on_delete=models.CASCADE)
    item = models.ForeignKey(Item, null=True, blank=True, on_delete=models.CASCADE)  # For products
    service = models.ForeignKey(Service, null=True, blank=True, on_delete=models.CASCADE)  # For services
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Unit price for both products and services
    amount = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)  # Total amount for the item or service
    price_item = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Price of item/service before tax
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Discount in percentage.")
    gstTaxRate = models.ForeignKey(GSTTaxRate, on_delete=models.SET_NULL, null=True, blank=True)

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
            return (Decimal(self.get_price_item()) * tax_rate)
        return Decimal(0)

    def get_cess_rate_amount(self):
        """Calculate cess amount."""
        if self.gstTaxRate:
            cess_rate = self.gstTaxRate.cess_rate / 100 if self.gstTaxRate else 0
            return (Decimal(self.get_price_item()) * cess_rate)
        return Decimal(0)
    
    def get_cgst_amount(self):
        """Calculate GST tax amount."""
        if self.gstTaxRate:
            tax_rate = self.gstTaxRate.rate / 200 if self.gstTaxRate else 0
            return (Decimal(self.get_price_item()) * tax_rate)
        return Decimal(0)

    def get_sgst_amount(self):
        """Calculate cess amount."""
        if self.gstTaxRate:
            tax_rate = self.gstTaxRate.rate / 200 if self.gstTaxRate else 0
            return (Decimal(self.get_price_item()) * tax_rate)
        return Decimal(0)
    
    def get_igst_amount(self):
        """Calculate IGST tax amount."""
        if self.gstTaxRate:
            igst_rate = self.gstTaxRate.rate / 100 if self.gstTaxRate else 0  # IGST uses full rate
            return (Decimal(self.get_price_item()) * igst_rate)
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
            if self.item.purchasePriceType == "With Tax":
                return (self.item.purchasePriceType)
            return (self.item.purchasePriceType)  # Already tax-exclusive
        elif self.service:
            return 0
    
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
           
            return 0.0       
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
            
            return 0.0
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
                    available_stock = self.item.closingStock + self.quantity
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
        skip_stock_update = kwargs.pop('skip_stock_update', False)  # Avoid stock update during creation
        self.full_clean()  # Ensure validation

        if self.item:
            self.unit_price = self.item.purchasePrice  # For products
            self.price_item = self.item.purchasePrice  # Price of item before tax
            
            # Prevent stock update during creation (only show stock)
            if not skip_stock_update:  # Only update stock if flag is False
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
                self.unit_price=0
                self.price_item=0

        self.amount = self.get_amount()  # Calculate the total amount (based on item or service)
        super().save(*args, **kwargs)

    def __str__(self):
        if self.item:
            return f"{self.item.itemName} ({self.quantity} * {self.unit_price})"
        elif self.service:
            return f"{self.service.serviceName} ({self.quantity} * {self.unit_price})"
        return "Unknown Item or Service"
    