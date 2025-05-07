from rest_framework import serializers
from .models import Item, ItemCategory, MeasuringUnit, GSTTaxRate, Service


class ItemCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemCategory
        fields = '__all__'
        read_only_fields = ['business']  # ✅ This fixes the issue


class MeasuringUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeasuringUnit
        fields = '__all__'


class GSTTaxRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = GSTTaxRate
        fields = '__all__'


class ServiceSerializer(serializers.ModelSerializer):
    salesPrice_with_tax = serializers.SerializerMethodField()
    salesPrice_without_tax = serializers.SerializerMethodField()

    class Meta:
        model = Service
        fields = ['business','id', 'serviceName', 'category', 'serviceType', 'salesPrice', 'salesPriceType',
                  'gstTaxRate', 'measuringUnit', 'serviceCode', 'sacCode', 'description',
                  'salesPrice_with_tax', 'salesPrice_without_tax']
        read_only_fields = ['business']  # ✅ This fixes the issue
        ordering = ['serviceName']
        
    def get_salesPrice_with_tax(self, obj):
        """Returns the tax-inclusive sales price if stored without tax."""
        if obj.salesPriceType == "Without Tax":
            return obj.calculate_price(obj.salesPrice, "Without Tax")
        return obj.salesPrice  # Already tax-inclusive

    def get_salesPrice_without_tax(self, obj):
        """Returns the tax-exclusive purchase price if stored with tax."""
        if obj.salesPriceType == "With Tax":
            return obj.calculate_price(obj.salesPrice, "With Tax")
        return obj.salesPrice  # Already tax-exclusive

    def to_representation(self, instance):
        data = super().to_representation(instance)

        # List of keys to remove if they are None
        keys_to_remove = [
            "salesPrice_with_tax", "salesPrice_without_tax"
        ]

        # Remove the keys if they exist and have a value of None
        for key in keys_to_remove:
            if key in data and data.get(key) is None:
                del data[key]

        return data


class ItemSerializer(serializers.ModelSerializer):
    salesPrice_with_tax = serializers.SerializerMethodField()
    purchasePrice_with_tax = serializers.SerializerMethodField()
    salesPrice_without_tax = serializers.SerializerMethodField()
    purchasePrice_without_tax = serializers.SerializerMethodField()
    stock_value = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)

    class Meta:
        model = Item
        fields = [
            'business','id', 'itemName', 'category', 'itemType', 'salesPrice', 'salesPriceType',
            'purchasePrice', 'purchasePriceType', 'gstTaxRate', 'measuringUnit', 'itemCode',
            'godown', 'openingStock','closingStock', 'date', 'itemBatch', 'enableLowStockWarning',
            'lowStockQty', 'item_image', 'description', 'hsnCode', 'stock_value',
            'salesPrice_with_tax', 'purchasePrice_with_tax', 'salesPrice_without_tax', 'purchasePrice_without_tax',
        ]
        read_only_fields = ['business']  # ✅ This fixes the issue
        ordering = ['itemName']
        
    def validate(self, attrs):
        closingStock = attrs.get('closingStock')
        lowStockQty = attrs.get('lowStockQty')

        if closingStock is not None and lowStockQty is not None:
            attrs['enableLowStockWarning'] = closingStock <= lowStockQty

        return attrs

    def get_salesPrice_with_tax(self, obj):
        if isinstance(obj, dict):
            return None
        """Returns the tax-inclusive sales price if stored without tax."""
        if obj.salesPriceType == "Without Tax":
            return obj.calculate_price(obj.salesPrice, "Without Tax")
        return obj.salesPrice  # Already tax-inclusive

    def get_salesPrice_without_tax(self, obj):
        if isinstance(obj, dict):
            return None
        """Returns the tax-exclusive purchase price if stored with tax."""
        if obj.salesPriceType == "With Tax":
            return obj.calculate_price(obj.salesPrice, "With Tax")
        return obj.salesPrice  # Already tax-exclusive

    def get_purchasePrice_with_tax(self, obj):
        if isinstance(obj, dict):
            return None
        """Returns the tax-inclusive purchase price if stored without tax."""
        if obj.purchasePriceType == "Without Tax":
            return obj.calculate_price(obj.purchasePrice, "Without Tax")
        return obj.purchasePrice  # Already tax-inclusive

    def get_purchasePrice_without_tax(self, obj):
        if isinstance(obj, dict):
            return None
        """Returns the tax-exclusive purchase price if stored with tax."""
        if obj.purchasePriceType == "With Tax":
            return obj.calculate_price(obj.purchasePrice, "With Tax")
        return obj.purchasePrice  # Already tax-exclusive

    def to_representation(self, instance):
        """
        Removes `None` values from the response to keep it clean.
        """
        data = super().to_representation(instance)
        keys_to_remove = [
            key for key in ["salesPrice_with_tax", "purchasePrice_with_tax", "salesPrice_without_tax", "purchasePrice_without_tax"]
            if data.get(key) is None and key != 'enableLowStockWarning'
        ]
        for key in keys_to_remove:
            del data[key]
        return data
