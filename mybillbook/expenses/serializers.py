from rest_framework import serializers, viewsets
from .models import Item, ExpenseCategory,ExpenseService
from rest_framework import serializers
from django.db import transaction
from decimal import Decimal
from .models import Expense, ExpenseItem

class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = '__all__'
        read_only_fields = ['business']  # ✅ This fixes the issue


class ExpenseServiceSerializer(serializers.ModelSerializer):
    purchasePrice_with_tax = serializers.SerializerMethodField()
    purchasePrice_without_tax = serializers.SerializerMethodField()

    class Meta:
        model = ExpenseService
        fields = ['business','id', 'serviceName', 'serviceType', 'purchasePrice', 'purchasePriceType',
                  'gstTaxRate', 'measuringUnit', 'sacCode',
                  'purchasePrice_with_tax', 'purchasePrice_without_tax']
        read_only_fields = ['business']  # ✅ This fixes the issue
        ordering = ['serviceName']
        
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


    # def to_representation(self, instance):
    #     """
    #     Removes `None` values from the response to keep it clean.
    #     """
    #     data = super().to_representation(instance)
    #     keys_to_remove = [
    #         key for key in ["purchasePrice_with_tax", "purchasePrice_without_tax"]
    #     ]
    #     for key in keys_to_remove:
    #         del data[key]
    #     return data


class ItemSerializer(serializers.ModelSerializer):
    purchasePrice_with_tax = serializers.SerializerMethodField()
    purchasePrice_without_tax = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = [
            'business','id', 'itemName', 'itemType',
            'purchasePrice', 'purchasePriceType', 'gstTaxRate', 
            'measuringUnit', 'hsnCode', 'purchasePrice_with_tax','purchasePrice_without_tax',
        ]
        read_only_fields = ['business']  # ✅ This fixes the issue
        ordering = ['itemName']
        
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

    # def to_representation(self, instance):
    #     """
    #     Removes `None` values from the response to keep it clean.
    #     """
    #     data = super().to_representation(instance)
    #     keys_to_remove = [
    #         key for key in ["purchasePrice_with_tax", "purchasePrice_without_tax"]
    #     ]
    #     for key in keys_to_remove:
    #         del data[key]
    #     return data


from rest_framework import serializers
from decimal import Decimal
from .models import ExpenseItem

class ExpenseItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.itemName', read_only=True)
    service_name = serializers.CharField(source='service.serviceName', read_only=True)
    price_item = serializers.DecimalField(source='get_price_item', read_only=True, max_digits=10, decimal_places=2)
    amount = serializers.DecimalField(source='get_amount', read_only=True, max_digits=10, decimal_places=2)
    tax_rate = serializers.DecimalField(source='gstTaxRate.rate', read_only=True, max_digits=5, decimal_places=2)
    tax_rate_amount = serializers.DecimalField(source='get_tax_rate_amount', read_only=True, max_digits=10, decimal_places=2)
    cess_rate = serializers.DecimalField(source='gstTaxRate.cess_rate', read_only=True, max_digits=5, decimal_places=2)
    cess_rate_amount = serializers.DecimalField(source='get_cess_rate_amount', read_only=True, max_digits=10, decimal_places=2)
    cgst = serializers.DecimalField(source='get_cgst', read_only=True, max_digits=5, decimal_places=2)
    cgst_amount = serializers.DecimalField(source='get_cgst_amount', read_only=True, max_digits=10, decimal_places=2)
    igst = serializers.DecimalField(source='gstTaxRate.rate', read_only=True, max_digits=5, decimal_places=2)
    igst_amount = serializers.DecimalField(source='get_igst_amount', read_only=True, max_digits=10, decimal_places=2)
    sgst = serializers.DecimalField(source='get_sgst', read_only=True, max_digits=5, decimal_places=2)
    sgst_amount = serializers.DecimalField(source='get_sgst_amount', read_only=True, max_digits=10, decimal_places=2)
    hsnCode = serializers.CharField(source='item.hsnCode', read_only=True)
    sacCode = serializers.CharField(source='service.sacCode', read_only=True)
    purchasePrice_with_tax = serializers.DecimalField(source='get_purchasePrice_without_tax', read_only=True, max_digits=5, decimal_places=2)
    purchasePrice_without_tax = serializers.DecimalField(source='get_purchasePrice_with_tax', read_only=True, max_digits=5, decimal_places=2)
    purchasePriceType = serializers.CharField(source='get_price_type', read_only=True)
    type = serializers.CharField(source='get_type', read_only=True)

    class Meta:
        model = ExpenseItem
        fields = [
            'id', 'expense', 'item', 'item_name', 'service', 'service_name',
            'quantity', 'discount', 'unit_price', 'amount', 'gstTaxRate',
            'tax_rate', 'tax_rate_amount', 'cess_rate', 'cess_rate_amount',
            'cgst', 'cgst_amount', 'sgst', 'sgst_amount', 'igst', 'igst_amount',
            'hsnCode', 'sacCode',
            'purchasePrice_with_tax', 'purchasePrice_without_tax','purchasePriceType', 'type', 'price_item'
        ]
        extra_kwargs = {
            'expense': {'required': False}
        }


    def validate(self, data):
        item = data.get('item')
        service = data.get('service')
        if not item and not service:
            raise serializers.ValidationError("Either item or service must be provided.")
        if item and service:
            raise serializers.ValidationError("Only one of item or service is allowed.")
        return data


class ExpenseSerializer(serializers.ModelSerializer):
    expense_items = ExpenseItemSerializer(many=True, required=False)
    total_amount = serializers.DecimalField(source='get_total_amount', read_only=True, max_digits=12, decimal_places=2)
    taxable_amount = serializers.DecimalField(source='get_taxable_amount', read_only=True, max_digits=12, decimal_places=2)

    class Meta:
        model = Expense
        fields = [
            'id', 'business', 'expense_no', 'original_invoice_no','date', 'party', 'category',
            'payment_method', 'notes', 'discount', 'total_amount', 'taxable_amount',
            'expense_items'
        ]
        read_only_fields = ['business', 'total_amount',
            'taxable_amount']

    def create(self, validated_data):
        items_data = validated_data.pop('expense_items', [])
        expense = Expense.objects.create(**validated_data)
        for item_data in items_data:
            item_data['expense'] = expense
            ExpenseItem.objects.create(**item_data)
        expense.save()
        return expense

    def update(self, instance, validated_data):
        items_data = validated_data.pop('expense_items', [])
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Clear and recreate items
        instance.expense_items.all().delete()
        for item_data in items_data:
            item_data['expense'] = instance
            ExpenseItem.objects.create(**item_data)
        return instance

