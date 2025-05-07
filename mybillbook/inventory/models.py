from django.db import models
from godown.models import Godown
import uuid
from users.models import Business
from decimal import Decimal

# Model for Item Categories
class ItemCategory(models.Model):
    name = models.CharField(max_length=100)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='item_categories')

    class Meta:
        app_label = 'inventory'
        unique_together = ['business', 'name']  # ✅ Ensures unique per business
        ordering = ['name']

    def __str__(self):
        return self.name


# Model for Measuring Units
class MeasuringUnit(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        app_label = 'inventory'

    def __str__(self):
        return self.name


# Model for GST Tax Rates
class GSTTaxRate(models.Model):
    rate = models.DecimalField(max_digits=5, decimal_places=2)
    cess_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    description = models.CharField(max_length=255, default="No description provided")

    class Meta:
        app_label = 'inventory'

    def __str__(self):
        return f"{self.description}"

# Model for Items
class Item(models.Model):
    ITEM_TYPE_CHOICES = [
        ('Product', 'Product')
    ]
    
    SALES_PRICE_TYPE = [
        ('With Tax', 'With Tax'),
        ('Without Tax', 'Without Tax')
    ]
    
    PURCHASE_PRICE_TYPE = [
        ('With Tax', 'With Tax'),
        ('Without Tax', 'Without Tax')
    ]
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='items')
    itemName = models.CharField(max_length=255)
    category = models.ForeignKey('ItemCategory', on_delete=models.CASCADE)
    itemType = models.CharField(max_length=10, choices=ITEM_TYPE_CHOICES, default="Product")
    salesPrice = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    salesPriceType = models.CharField(max_length=50, choices=SALES_PRICE_TYPE, default="With Tax")
    purchasePrice = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    purchasePriceType = models.CharField(max_length=50, choices=PURCHASE_PRICE_TYPE, default="With Tax")
    gstTaxRate = models.ForeignKey('GSTTaxRate', on_delete=models.SET_NULL, null=True)
    measuringUnit = models.ForeignKey('MeasuringUnit', on_delete=models.SET_NULL, null=True)
    itemCode = models.CharField(max_length=100)
    godown = models.ForeignKey(Godown, on_delete=models.SET_NULL, null=True, related_name='inventory_items')
    # godown = models.ForeignKey(Godown, on_delete=models.CASCADE, related_name='inventory_items')
    
    # Stock Management
    openingStock = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    closingStock = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    date = models.DateField()
    itemBatch = models.CharField(max_length=50, blank=True, null=True)
    
    enableLowStockWarning = models.BooleanField(null=True, blank=True, default=False)
    lowStockQty = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    item_image = models.ImageField(upload_to='static/images/', null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    hsnCode = models.CharField(max_length=15, blank=True, null=True)
    created_at = models.DateField(auto_now=True)  # Automatically updates the date when stock changes
    
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
        if self.closingStock is None:
            # This condition ensures it only runs once when the object is first created
            self.closingStock = self.openingStock
            
        if self.itemType == "Product" and self.closingStock is not None and self.lowStockQty is not None:
            self.enableLowStockWarning = self.closingStock <= self.lowStockQty
        super(Item, self).save(*args, **kwargs)
                    
    def calculate_stock_value(self):
        """ Calculates the stock value based on opening stock and purchase price. """
        return self.closingStock * self.purchasePrice if self.closingStock and self.purchasePrice else 0.00

    def decrease_stock(self, quantity):
        """ Reduce stock when an item is sold. """
        if self.closingStock >= quantity:
            self.closingStock -= quantity
            self.enableLowStockWarning = self.closingStock <= self.lowStockQty
            self.save()
        else:
            raise ValueError(f"Not enough stock for {self.itemName}. Available stock: {self.closingStock}")

    def increase_stock(self, quantity):
        """ Increase stock when new items are added. """
        self.closingStock += quantity
        self.enableLowStockWarning = self.closingStock <= self.lowStockQty
        self.save()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['business', 'itemCode'], name='unique_itemcode_per_business')
        ]

    def __str__(self):
        return f"{self.itemName} - {self.godown.godownName if self.godown else 'No Godown'}"

# Model for Services
class Service(models.Model):
    SERVICE_TYPE_CHOICES = [
        ('Service', 'Service')  
    ]
    
    SALES_PRICE_TYPE = [
        ('With Tax', 'With Tax'),
        ('Without Tax', 'Without Tax')
    ]
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='service')
    serviceName = models.CharField(max_length=255)
    category = models.ForeignKey(ItemCategory, on_delete=models.CASCADE)
    serviceType = models.CharField(max_length=10, choices=SERVICE_TYPE_CHOICES, default="Service")
    salesPrice = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    salesPriceType = models.CharField(max_length=50, choices=SALES_PRICE_TYPE, default="With Tax")
    gstTaxRate = models.ForeignKey(GSTTaxRate, on_delete=models.SET_NULL, null=True)
    measuringUnit = models.ForeignKey(MeasuringUnit, on_delete=models.SET_NULL, null=True)
    sacCode = models.CharField(max_length=15, blank=True, null=True)
    serviceCode = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

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
            models.UniqueConstraint(fields=['business', 'serviceCode'], name='unique_servicecode_per_business')
        ]


    def save(self, *args, **kwargs):
        """ If service code is not set, generate a new one using uuid. """
        
        if not self.serviceCode:
            self.serviceCode = str(uuid.uuid4())  # Generate service code
        super(Service, self).save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.serviceName}"