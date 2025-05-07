from rest_framework import serializers, viewsets
from .models import Purchase, PaymentOut, PurchaseReturn, DebitNote, PurchaseOrder, PurchaseItem, DebitNoteItem, PurchaseReturnItem, PurchaseOrderItem,PaymentOutPurchase
# from sales.models import Invoice
from inventory.models import ItemCategory, GSTTaxRate
from decimal import Decimal
from sales.models import Tcs, Tds
from users.utils import get_current_business
from cash_and_bank.models import BankAccount
from cash_and_bank.serializers import BankAccountSerializer
BANK_PAYMENT_METHODS = ["UPI", "Card", "Netbanking", "Bank Transfer", "Cheque"]


class PurchaseItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.itemName', read_only=True)
    service_name = serializers.CharField(source='service.serviceName', read_only=True)
    available_stock = serializers.DecimalField(source='get_available_stock', read_only=True, max_digits=10, decimal_places=2)
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
    salesPrice_with_tax = serializers.DecimalField(source='get_salesPrice_without_tax', read_only=True, max_digits=5, decimal_places=2)
    purchasePrice_with_tax = serializers.DecimalField(source='get_purchasePrice_without_tax', read_only=True, max_digits=5, decimal_places=2)
    salesPrice_without_tax = serializers.DecimalField(source='get_salesPrice_with_tax', read_only=True, max_digits=5, decimal_places=2)
    purchasePrice_without_tax = serializers.DecimalField(source='get_purchasePrice_with_tax', read_only=True, max_digits=5, decimal_places=2)
    purchasePriceType = serializers.CharField(source='get_price_type', read_only=True)
    type = serializers.CharField(source='get_type', read_only=True)
    
    class Meta:
        model = PurchaseItem
        fields = ['id','purchase','item', 'item_name', 'quantity', 'unit_price', 'amount', 'price_item', 'available_stock','service', 'service_name','gstTaxRate', 
            'tax_rate', 'tax_rate_amount', 'cess_rate', 'cess_rate_amount' , 'cgst' , 'cgst_amount' , 'igst' , 'igst_amount', 'sgst', 'sgst_amount','hsnCode','sacCode','salesPrice_with_tax', 'purchasePrice_with_tax', 'salesPrice_without_tax', 'purchasePrice_without_tax', 'purchasePriceType','type','discount'
        ]
        extra_kwargs = {
            'purchase': {'required': False}  # 👈 This is the fix
        }


    def validate(self, data):
        """Ensure either item or service is provided, not both."""
        item = data.get('item')
        service = data.get('service')

        if not item and not service:
            raise serializers.ValidationError("Either 'item' or 'service' must be provided.")
        if item and service:
            raise serializers.ValidationError("You can only select either 'item' or 'service', not both.")
        if 'quantity' in data and data['quantity'] <= 0:
            raise serializers.ValidationError("Quantity must be a positive number.")

        # Ensure stock availability for items
        if item:
            if item.closingStock < data['quantity']:
                raise serializers.ValidationError(f"Not enough stock for {item.itemName}. Available: {item.closingStock}")
        return data
    
    
    def create(self, validated_data):
        """Create InvoiceItem and deduct stock."""
        item = validated_data.get('item')
        purchase_item = PurchaseItem.objects.create(**validated_data)

        # ✅ Deduct stock if it's an item (not service)
        if item:
            item.closingStock -= validated_data['quantity']
            item.save()

        return purchase_item
    
    
    def update(self, instance, validated_data):
        """Update InvoiceItem and reverse stock if needed."""
        old_quantity = instance.quantity
        new_quantity = validated_data.get('quantity', old_quantity)
        item = instance.item

        # ✅ Reverse stock if item is being updated
        if item:
            item.closingStock += old_quantity  # Add back old stock
            item.save()

        # ✅ Deduct new stock if updated quantity is less
        if item and new_quantity > 0:
            if item.closingStock < new_quantity:
                raise serializers.ValidationError(f"Not enough stock for {item.itemName}. Available: {item.closingStock}")
            item.closingStock -= new_quantity
            item.save()

        # ✅ Update the InvoiceItem
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
    
    def delete(self, instance):
        """Reverse stock when item is deleted."""
        item = instance.item
        if item:
            item.closingStock += instance.quantity
            item.save()
        instance.delete()

class PurchaseSerializer(serializers.ModelSerializer):
    purchase_items = PurchaseItemSerializer(many=True, required=False)
    total_amount = serializers.DecimalField(source='get_total_amount', read_only=True, max_digits=10, decimal_places=2)
    total_payable_amount = serializers.DecimalField(source='get_total_payable_amount', read_only=True, max_digits=10, decimal_places=2)
    balance_amount = serializers.DecimalField(source='get_balance_amount', read_only=True, max_digits=10, decimal_places=2)
    taxable_amount = serializers.DecimalField(source='get_taxable_amount', read_only=True, max_digits=10, decimal_places=2)
    status = serializers.CharField(read_only=True)
    tcs_on = serializers.ChoiceField(choices=Purchase.TCS_ON_CHOICES, required=False)
    tcs_amount = serializers.DecimalField(source='get_tcs_amount', read_only=True, max_digits=10, decimal_places=2)
    tds_amount = serializers.DecimalField(source='get_tds_amount', read_only=True, max_digits=10, decimal_places=2)  # ✅ New
    apply_tds = serializers.BooleanField(required=False)
    next_purchase_number = serializers.SerializerMethodField()
    bank_account = serializers.PrimaryKeyRelatedField(
        queryset=BankAccount.objects.all(),
        required=False,
        allow_null=True
    )
    
    
    class Meta:
        model = Purchase
        fields = [
            'business', 'id', 'purchase_no', 'date', 'party', 'status',
            'payment_term', 'due_date', 'amount_received', 'is_fully_paid',
            'payment_method', 'discount', 'total_amount', 'balance_amount',
            'purchase_items', 'notes', 'signature', 'taxable_amount',
            'apply_tcs', 'tcs', 'tcs_on', 'tcs_amount','apply_tds', 'tds', 'tds_amount', 'next_purchase_number','total_payable_amount','bank_account'
        ]
        read_only_fields = ['business', 'balance_amount', 'total_amount', 'total_payable_amount','tcs_amount', 'tds_amount', 'taxable_amount', 'next_purchase_number']

    def get_next_purchase_number(self, obj):
        request = self.context.get('request')
        if request and request.user:
            business = get_current_business(request.user)
            return Purchase.get_next_purchase_number(business)
        return None
    
    def validate(self, data):
        data = super().validate(data)
        
        # Validate bank account for non-cash payments
        payment_method = data.get('payment_method')
        if payment_method in BANK_PAYMENT_METHODS:
            bank_account = data.get('bank_account')
            if not bank_account:
                raise serializers.ValidationError({
                    "bank_account": "Bank account is required for non-cash payment methods"
                })
            
            # Verify bank account belongs to the business
            business = self.context['request'].user.current_business
            if bank_account.business != business:
                raise serializers.ValidationError({
                    "bank_account": "Invalid bank account"
                })
            
            # Verify it's a bank account (not cash)
            if bank_account.account_type != 'Bank':
                raise serializers.ValidationError({
                    "bank_account": "Selected account must be a bank account"
                })

        return data
    
    def create(self, validated_data):
        purchase_items_data = validated_data.pop('purchase_items', [])
        purchase = Purchase.objects.create(**validated_data)
        
        for item_data in purchase_items_data:
            PurchaseItem.objects.create(purchase=purchase, **item_data)
        purchase.save()
        return purchase

    def update(self, instance, validated_data):
        purchase_items_data = validated_data.pop('purchase_items', [])
        
        # Update purchase fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Delete existing items
        instance.purchase_items.all().delete()
        
        # Create new items
        for item_data in purchase_items_data:
            PurchaseItem.objects.create(purchase=instance, **item_data)
            
        instance.save()
        return instance

class PurchaseViewSet(viewsets.ModelViewSet):
    queryset = Purchase.objects.all()
    serializer_class = PurchaseSerializer


class PurchaseSettlementSerializer(serializers.Serializer):
    purchase = serializers.PrimaryKeyRelatedField(queryset=Purchase.objects.all())
    settled_amount = serializers.DecimalField(max_digits=10, decimal_places=2)

class PaymentOutSerializer(serializers.ModelSerializer):
    settled_purchase = PurchaseSettlementSerializer(many=True, write_only=True)
    settled_purchase_details = serializers.SerializerMethodField()
    next_payment_out_number = serializers.SerializerMethodField()
    bank_account = serializers.PrimaryKeyRelatedField(
        queryset=BankAccount.objects.all(),
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = PaymentOut
        fields = [
            'id', 'business', 'party', 'date', 'payment_mode', 'payment_out_number',
            'amount', 'notes', 'settled_purchase', 'settled_purchase_details','next_payment_out_number','bank_account'
        ]
        read_only_fields = ['business', 'settled_purchase_details','next_payment_out_number']

    def validate(self, data):
        data = super().validate(data)
        
        # Validate bank account for non-cash payments
        payment_method = data.get('payment_method')
        if payment_method in BANK_PAYMENT_METHODS:
            bank_account = data.get('bank_account')
            if not bank_account:
                raise serializers.ValidationError({
                    "bank_account": "Bank account is required for non-cash payment methods"
                })
            
            # Verify bank account belongs to the business
            business = self.context['request'].user.current_business
            if bank_account.business != business:
                raise serializers.ValidationError({
                    "bank_account": "Invalid bank account"
                })
            
            # Verify it's a bank account (not cash)
            if bank_account.account_type != 'Bank':
                raise serializers.ValidationError({
                    "bank_account": "Selected account must be a bank account"
                })

        return data

    def get_settled_purchase_details(self, obj):
        return [
            {
                "purchase_id": record.purchase.id,
                "purchase_number": record.purchase.purchase_no,
                "settled_amount": record.settled_amount,
            }
            for record in PaymentOutPurchase.objects.filter(payment_out=obj).select_related("purchase")
        ]

    def create(self, validated_data):
        settled_purchases_data = validated_data.pop('settled_purchase', [])
        payment_out = PaymentOut.objects.create(**validated_data)

        from .utils import apply_payment_to_purchase
        apply_payment_to_purchase(payment_out, settled_purchases_data)

        return payment_out

    def get_next_payment_out_number(self, obj):
        request = self.context.get('request')
        if request and request.user:
            business = get_current_business(request.user)
            return PaymentOut.get_next_payment_out_number(business)
        return None


class PurchaseReturnItemSerializer(serializers.ModelSerializer):
    # Assuming 'item' and 'service' are ForeignKeys to 'Item' and 'Service' models
    item_name = serializers.CharField(source='item.itemName', read_only=True)
    service_name = serializers.CharField(source='service.serviceName', read_only=True)
    available_stock = serializers.DecimalField(source='get_available_stock', read_only=True, max_digits=10, decimal_places=2)
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
    salesPrice_with_tax = serializers.DecimalField(source='get_salesPrice_without_tax', read_only=True, max_digits=5, decimal_places=2)
    purchasePrice_with_tax = serializers.DecimalField(source='get_purchasePrice_without_tax', read_only=True, max_digits=5, decimal_places=2)
    salesPrice_without_tax = serializers.DecimalField(source='get_salesPrice_with_tax', read_only=True, max_digits=5, decimal_places=2)
    purchasePrice_without_tax = serializers.DecimalField(source='get_purchasePrice_with_tax', read_only=True, max_digits=5, decimal_places=2)
    salesPriceType = serializers.CharField(source='get_price_type', read_only=True)
    type = serializers.CharField(source='get_type', read_only=True)
    

    class Meta:
        model = PurchaseReturnItem
        fields = ['id', 'purchasereturn','item', 'item_name', 'quantity', 'unit_price', 'amount','price_item', 'available_stock', 'service', 'service_name', 'gstTaxRate', 
            'tax_rate', 'tax_rate_amount', 'cess_rate', 'cess_rate_amount' , 'cgst' , 'cgst_amount', 'igst' , 'igst_amount' , 'sgst', 'sgst_amount', 'hsnCode' , 'sacCode','salesPrice_with_tax', 'purchasePrice_with_tax', 'salesPrice_without_tax', 'purchasePrice_without_tax', 'salesPriceType','type','discount'
        ]
        extra_kwargs = {
            'purchasereturn': {'required': False}  # 👈 This is the fix
        }

    # def get_available_stock(self, obj):
    #     """Return available stock for the item, or None if it's a service."""
    #     if obj.service:
    #         return None  # Services don't have stock
    #     item = obj.item
    #     return item.closingStock if item else None

    def validate(self, data):
        """Ensure either item or service is provided, not both."""
        item = data.get('item')
        service = data.get('service')

        if not item and not service:
            raise serializers.ValidationError("Either 'item' or 'service' must be provided.")
        if item and service:
            raise serializers.ValidationError("You can only select either 'item' or 'service', not both.")
        if 'quantity' in data and data['quantity'] <= 0:
            raise serializers.ValidationError("Quantity must be a positive number.")

        # Ensure stock availability for items
        if item:
            if item.closingStock < data['quantity']:
                raise serializers.ValidationError(f"Not enough stock for {item.itemName}. Available: {item.closingStock}")
        return data
    
    def create(self, validated_data):
        """Create InvoiceItem and deduct stock."""
        item = validated_data.get('item')
        invoice_item = PurchaseReturnItem.objects.create(**validated_data)

        # ✅ Deduct stock if it's an item (not service)
        if item:
            item.closingStock += validated_data['quantity']
            item.save()
        return invoice_item
    
    def update(self, instance, validated_data):
        """Update InvoiceItem and reverse stock if needed."""
        old_quantity = instance.quantity
        new_quantity = validated_data.get('quantity', old_quantity)
        item = instance.item

        # ✅ Reverse stock if item is being updated
        if item:
            item.closingStock += old_quantity  # Add back old stock
            item.save()

        # ✅ Deduct new stock if updated quantity is less
        if item and new_quantity > 0:
            if item.closingStock < new_quantity:
                raise serializers.ValidationError(f"Not enough stock for {item.itemName}. Available: {item.closingStock}")
            item.closingStock -= new_quantity
            item.save()

        # ✅ Update the InvoiceItem
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
    
    def delete(self, instance):
        """Reverse stock when item is deleted."""
        item = instance.item
        if item:
            item.closingStock -= instance.quantity
            item.save()
        instance.delete()

class PurchaseReturnSerializer(serializers.ModelSerializer):
    purchasereturn_items = PurchaseReturnItemSerializer(many=True)
    total_amount = serializers.DecimalField(source='get_total_amount', read_only=True, max_digits=10, decimal_places=2)
    total_payable_amount = serializers.DecimalField(source='get_total_payable_amount', read_only=True, max_digits=10, decimal_places=2)
    balance_amount = serializers.DecimalField(source='get_balance_amount', read_only=True, max_digits=10, decimal_places=2)
    taxable_amount = serializers.DecimalField(source='get_taxable_amount', read_only=True, max_digits=10, decimal_places=2)
    status = serializers.CharField(read_only=True)
    tcs_on = serializers.ChoiceField(choices=Purchase.TCS_ON_CHOICES, required=False)
    tcs_amount = serializers.DecimalField(source='get_tcs_amount', read_only=True, max_digits=10, decimal_places=2)
    tds_amount = serializers.DecimalField(source='get_tds_amount', read_only=True, max_digits=10, decimal_places=2)  # ✅ New
    apply_tds = serializers.BooleanField(required=False)
    next_purchase_return_number = serializers.SerializerMethodField()
    bank_account = serializers.PrimaryKeyRelatedField(
        queryset=BankAccount.objects.all(),
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = PurchaseReturn
        fields = ['business', 'id', 'purchasereturn_no', 'date', 'party', 'status',
             'amount_received', 'is_fully_paid',
            'payment_method', 'discount', 'total_amount', 'balance_amount',
            'purchasereturn_items', 'notes', 'signature', 'taxable_amount','purchase_id','purchase_no',
            'apply_tcs', 'tcs', 'tcs_on', 'tcs_amount','apply_tds', 'tds', 'tds_amount', 'next_purchase_return_number','total_payable_amount','bank_account']
        
        read_only_fields = ['business', 'balance_amount', 'total_amount', 'total_payable_amount','tcs_amount', 'tds_amount', 'taxable_amount','next_purchase_return_number']
        
    def get_next_purchase_return_number(self, obj):
        request = self.context.get('request')
        if request and request.user:
            business = get_current_business(request.user)
            return PurchaseReturn.get_next_purchase_return_number(business)
        return None
    
    def get_balance_amount(self, obj):
        total_amount = obj.get_total_amount()  # Get total amount before payment
        amount_received = Decimal(obj.amount_received)  # Get the amount received so far
        return total_amount - amount_received  # Remaining balance
    
    def validate(self, data):
        data = super().validate(data)
        
        # Validate bank account for non-cash payments
        payment_method = data.get('payment_method')
        if payment_method in BANK_PAYMENT_METHODS:
            bank_account = data.get('bank_account')
            if not bank_account:
                raise serializers.ValidationError({
                    "bank_account": "Bank account is required for non-cash payment methods"
                })
            
            # Verify bank account belongs to the business
            business = self.context['request'].user.current_business
            if bank_account.business != business:
                raise serializers.ValidationError({
                    "bank_account": "Invalid bank account"
                })
            
            # Verify it's a bank account (not cash)
            if bank_account.account_type != 'Bank':
                raise serializers.ValidationError({
                    "bank_account": "Selected account must be a bank account"
                })

        return data

    def create(self, validated_data):
        # Handle creation of the purchase return and items
        purchase_items_data = validated_data.pop('purchasereturn_items', [])
        purchase = PurchaseReturn.objects.create(**validated_data)

        for item_data in purchase_items_data:
            item_data['purchasereturn'] = purchase
            PurchaseReturnItem.objects.create(**item_data)

        # Save the purchase to calculate total amount and balance
        purchase.save()
        return purchase

    def update(self, instance, validated_data):
        # Handle updating the purchase return and items
        purchase_items_data = validated_data.pop('purchasereturn_items', [])

        # Update the main purchase return fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Handle invoice item updates or deletions
        existing_items = instance.purchasereturn_items.all()
        existing_item_ids = [item.id for item in existing_items]
        updated_item_ids = [item_data.get('id') for item_data in purchase_items_data if item_data.get('id')]

        # Delete removed items
        for item_id in set(existing_item_ids) - set(updated_item_ids):
            item_to_delete = instance.purchasereturn_items.get(id=item_id)
            PurchaseReturnItemSerializer().delete(item_to_delete)

        # Update or create new items
        for item_data in purchase_items_data:
            item_id = item_data.get('id')
            if item_id:
                item_instance = instance.purchasereturn_items.get(id=item_id)
                PurchaseReturnItemSerializer().update(item_instance, item_data)
            else:
                item_data['purchasereturn'] = instance
                PurchaseReturnItem.objects.create(**item_data)

        # Recalculate the balance after updating the items
        instance.save()
        return instance

class PurchaseReturnViewSet(viewsets.ModelViewSet):
    queryset=PurchaseReturn.objects.all()
    serializer_class=PurchaseReturnSerializer


class DebitNoteItemSerializer(serializers.ModelSerializer):
    # Assuming 'item' and 'service' are ForeignKeys to 'Item' and 'Service' models
    item_name = serializers.CharField(source='item.itemName', read_only=True)
    service_name = serializers.CharField(source='service.serviceName', read_only=True)
    available_stock = serializers.DecimalField(source='get_available_stock', read_only=True, max_digits=10, decimal_places=2)
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
    salesPrice_with_tax = serializers.DecimalField(source='get_salesPrice_without_tax', read_only=True, max_digits=5, decimal_places=2)
    purchasePrice_with_tax = serializers.DecimalField(source='get_purchasePrice_without_tax', read_only=True, max_digits=5, decimal_places=2)
    salesPrice_without_tax = serializers.DecimalField(source='get_salesPrice_with_tax', read_only=True, max_digits=5, decimal_places=2)
    purchasePrice_without_tax = serializers.DecimalField(source='get_purchasePrice_with_tax', read_only=True, max_digits=5, decimal_places=2)
    salesPriceType = serializers.CharField(source='get_price_type', read_only=True)
    type = serializers.CharField(source='get_type', read_only=True)
    

    class Meta:
        model = DebitNoteItem
        fields = ['id','debitnote','item', 'item_name', 'quantity', 'unit_price', 'amount', 'price_item', 'available_stock', 'service', 'service_name','gstTaxRate', 'tax_rate', 'tax_rate_amount', 'cess_rate', 'cess_rate_amount' , 'cgst' , 'cgst_amount' , 'igst' , 'igst_amount','sgst', 'sgst_amount','hsnCode','sacCode','salesPrice_with_tax','salesPrice_without_tax','purchasePrice_without_tax','purchasePrice_with_tax','salesPriceType','type','discount']
        
        extra_kwargs = {
            'debitnote': {'required': False}  # 👈 This is the fix
        }

    def get_available_stock(self, obj):
        """Return available stock for the item, or None if it's a service."""
        if obj.service:
            return None  # Services don't have stock
        item = obj.item
        return item.closingStock if item else None

    def validate(self, data):
        """Ensure either item or service is provided, not both."""
        item = data.get('item')
        service = data.get('service')

        if not item and not service:
            raise serializers.ValidationError("Either 'item' or 'service' must be provided.")
        if item and service:
            raise serializers.ValidationError("You can only select either 'item' or 'service', not both.")
        if 'quantity' in data and data['quantity'] <= 0:
            raise serializers.ValidationError("Quantity must be a positive number.")

        # Ensure stock availability for items
        if item:
            if item.closingStock < data['quantity']:
                raise serializers.ValidationError(f"Not enough stock for {item.itemName}. Available: {item.closingStock}")
        return data
    
    def create(self, validated_data):
        # Handle stock adjustment or any other logic
        item = validated_data.get('item')
        debitnote_item = DebitNoteItem.objects.create(**validated_data)
        if item:
            item.closingStock += validated_data['quantity']
            item.save()
        return debitnote_item
    
    
    def update(self, instance, validated_data):
        """Update InvoiceItem and reverse stock if needed."""
        old_quantity = instance.quantity
        new_quantity = validated_data.get('quantity', old_quantity)
        item = instance.item

        # ✅ Reverse stock if item is being updated
        if item:
            item.closingStock += old_quantity  # Add back old stock
            item.save()

        # ✅ Deduct new stock if updated quantity is less
        if item and new_quantity > 0:
            if item.closingStock < new_quantity:
                raise serializers.ValidationError(f"Not enough stock for {item.itemName}. Available: {item.closingStock}")
            item.closingStock -= new_quantity
            item.save()

        # ✅ Update the InvoiceItem
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
    
    def delete(self, instance):
        """Reverse stock when item is deleted."""
        item = instance.item
        if item:
            item.closingStock -= instance.quantity
            item.save()
        instance.delete()
    
class DebitNoteSerializer(serializers.ModelSerializer):
    debitnote_items = DebitNoteItemSerializer(many=True, required=False)
    total_amount = serializers.DecimalField(source='get_total_amount', read_only=True, max_digits=10, decimal_places=2)
    taxable_amount = serializers.DecimalField(source='get_taxable_amount', read_only=True, max_digits=10, decimal_places=2)
    balance_amount = serializers.DecimalField(source='get_balance_amount', read_only=True, max_digits=10, decimal_places=2)
    status = serializers.CharField(read_only=True)
    tcs_on = serializers.ChoiceField(choices=DebitNote.TCS_ON_CHOICES, required=False)
    tcs_amount = serializers.DecimalField(source='get_tcs_amount', read_only=True, max_digits=10, decimal_places=2)
    tds_amount = serializers.DecimalField(source='get_tds_amount', read_only=True, max_digits=10, decimal_places=2)
    total_payable_amount = serializers.DecimalField(source='get_total_payable_amount', read_only=True, max_digits=10, decimal_places=2)
    next_purchase_debit_number = serializers.SerializerMethodField()
    bank_account = serializers.PrimaryKeyRelatedField(
        queryset=BankAccount.objects.all(),
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = DebitNote
        fields = ['business','id', 'debitnote_no', 'date', 'party', 'status', 'is_fully_paid', 'payment_method',
                  'total_amount', 'balance_amount', 'discount', 'debitnote_items',
                  'notes', 'signature', 'taxable_amount','purchasereturn_no' , 'purchasereturn_id',
                  'tcs_amount', 'apply_tcs', 'tcs', 'tcs_on',
                  'tds_amount', 'apply_tds', 'tds','total_payable_amount','next_purchase_debit_number','bank_account']
        
        read_only_fields = ['business', 'total_amount', 'balance_amount',
            'taxable_amount', 'tcs_amount', 'tds_amount','total_payable_amount','next_purchase_debit_number']
        
    def get_balance_amount(self, obj):
        total_amount = obj.get_total_amount()
        amount_received = Decimal(obj.amount_received)
        return total_amount - amount_received
    
    def validate(self, data):
        data = super().validate(data)
        
        # Validate bank account for non-cash payments
        payment_method = data.get('payment_method')
        if payment_method in BANK_PAYMENT_METHODS:
            bank_account = data.get('bank_account')
            if not bank_account:
                raise serializers.ValidationError({
                    "bank_account": "Bank account is required for non-cash payment methods"
                })
            
            # Verify bank account belongs to the business
            business = self.context['request'].user.current_business
            if bank_account.business != business:
                raise serializers.ValidationError({
                    "bank_account": "Invalid bank account"
                })
            
            # Verify it's a bank account (not cash)
            if bank_account.account_type != 'Bank':
                raise serializers.ValidationError({
                    "bank_account": "Selected account must be a bank account"
                })

        return data

    def get_next_purchase_debit_number(self, obj):
        request = self.context.get('request')
        if request and request.user:
            business = get_current_business(request.user)
            return DebitNote.get_next_purchase_debit_number(business)
        return None
    
    def create(self, validated_data):
        print("create")
        invoice_items_data = validated_data.pop('debitnote_items', [])   
        purchase = DebitNote.objects.create(**validated_data)

        # ✅ Create each InvoiceItem without validation errors
        for item_data in invoice_items_data:
            item_data['debitnote'] = purchase  # Inject purchase here after creation
            DebitNoteItem.objects.create(**item_data)

        # ✅ The save() method in Invoice will automatically update balance
        purchase.save()
        return purchase

    def update(self, instance, validated_data):
        print("Update")
        # Extract the invoice_items from validated data (if present)
        invoice_items_data = validated_data.pop('debitnote_items', [])
       
        # Step 1: Update invoice fields (main Invoice object)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()  # Save the main Invoice model after updating its fields
        
        # Step 2: Handle InvoiceItem updates/deletions
        existing_items = instance.debitnote_items.all()
        existing_item_ids = [item.id for item in existing_items]
        updated_item_ids = [item_data.get('id') for item_data in invoice_items_data if item_data.get('id')]

        # Step 3: Delete removed items
        for item_id in set(existing_item_ids) - set(updated_item_ids):
            item_to_delete = instance.debitnote_items.get(id=item_id)
            DebitNoteItemSerializer().delete(item_to_delete)

        # Step 4: Update or Create new items
        for item_data in invoice_items_data:
            item_id = item_data.get('id')
            if item_id:
                # Update existing item
                item_instance = instance.debitnote_items.get(id=item_id)
                DebitNoteItemSerializer().update(item_instance, item_data)
            else:
                # Create new item
                item_data['debitnote'] = instance  # Associate the new InvoiceItem with the current Invoice
                DebitNoteItem.objects.create(**item_data)

        # Step 5: Automatically recalculate balance after saving changes
        instance.save()  # This ensures the updated Invoice object reflects the changes
        return instance

class DebitNoteViewSet(viewsets.ModelViewSet):
    queryset=DebitNote.objects.all()
    serializer_class=DebitNoteSerializer
        

class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.itemName', read_only=True)
    service_name = serializers.CharField(source='service.serviceName', read_only=True)
    available_stock = serializers.DecimalField(source='get_available_stock', read_only=True, max_digits=10, decimal_places=2)
    price_item = serializers.DecimalField(source='get_price_item', read_only=True, max_digits=10, decimal_places=2)
    amount = serializers.DecimalField(source='get_amount', read_only=True, max_digits=10, decimal_places=4)
    gstTaxRate = serializers.PrimaryKeyRelatedField(queryset=GSTTaxRate.objects.all(), required=False)  # ForeignKey field
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
    salesPrice_with_tax = serializers.DecimalField(source='get_salesPrice_without_tax', read_only=True, max_digits=5, decimal_places=2)
    purchasePrice_with_tax = serializers.DecimalField(source='get_purchasePrice_without_tax', read_only=True, max_digits=5, decimal_places=2)
    salesPrice_without_tax = serializers.DecimalField(source='get_salesPrice_with_tax', read_only=True, max_digits=5, decimal_places=2)
    purchasePrice_without_tax = serializers.DecimalField(source='get_purchasePrice_with_tax', read_only=True, max_digits=5, decimal_places=2)
    salesPriceType = serializers.CharField(source='get_price_type', read_only=True)
    type = serializers.CharField(source='get_type', read_only=True)
   

    class Meta:
        model = PurchaseOrderItem
        fields = ['id','purchaseorder','item', 'item_name', 'quantity', 'unit_price', 'amount', 'price_item','available_stock','gstTaxRate', 'service', 'service_name','tax_rate', 'tax_rate_amount', 'cess_rate', 'cess_rate_amount' , 'cgst' , 'cgst_amount' , 'igst' , 'igst_amount', 'sgst', 'sgst_amount','hsnCode','sacCode','salesPrice_with_tax', 'purchasePrice_with_tax', 'salesPrice_without_tax', 'purchasePrice_without_tax', 'salesPriceType','type','discount'
        ]
        extra_kwargs = {
            'purchaseorder': {'required': False}  # 👈 This is the fix
        }

    # def get_available_stock(self, obj):
    #     """Return available stock for the item, or None if it's a service."""
    #     if obj.service:
    #         return None  # Services don't have stock
    #     item = obj.item
    #     return item.closingStock if item else None


    def validate(self, data):
        """Ensure either item or service is provided, not both."""
        item = data.get('item')
        service = data.get('service')

        if not item and not service:
            raise serializers.ValidationError("Either 'item' or 'service' must be provided.")
        if item and service:
            raise serializers.ValidationError("You can only select either 'item' or 'service', not both.")
        if 'quantity' in data and data['quantity'] <= 0:
            raise serializers.ValidationError("Quantity must be a positive number.")

        # Ensure stock availability for items
        if item:
            if item.closingStock < data['quantity']:
                raise serializers.ValidationError(f"Not enough stock for {item.itemName}. Available: {item.closingStock}")
        return data
    
    def create(self, validated_data):
        """Create InvoiceItem and deduct stock."""
        item = validated_data.get('item')
        purchase_item = PurchaseOrderItem.objects.create(**validated_data)

        # ✅ Deduct stock if it's an item (not service)
        if item:
            item.closingStock += validated_data['quantity']
            item.save()

        return purchase_item
    
    def update(self, instance, validated_data):
        """Update InvoiceItem and reverse stock if needed."""
        old_quantity = instance.quantity
        new_quantity = validated_data.get('quantity', old_quantity)
        item = instance.item

        # ✅ Reverse stock if item is being updated
        if item:
            item.closingStock += old_quantity  # Add back old stock
            item.save()

        # ✅ Deduct new stock if updated quantity is less
        if item and new_quantity > 0:
            if item.closingStock < new_quantity:
                raise serializers.ValidationError(f"Not enough stock for {item.itemName}. Available: {item.closingStock}")
            item.closingStock -= new_quantity
            item.save()

        # ✅ Update the InvoiceItem
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
    
    def delete(self, instance):
        print("""Reverse stock when item is deleted.""")
        item = instance.item
        if item:
            item.closingStock += instance.quantity
            item.save()
        instance.delete()
    
class PurchaseOrderSerializer(serializers.ModelSerializer):
    purchaseorder_items = PurchaseOrderItemSerializer(many=True)
    total_amount = serializers.DecimalField(source='get_total_amount',read_only=True, max_digits=10, decimal_places=2)
    taxable_amount = serializers.DecimalField(source='get_taxable_amount', read_only=True, max_digits=10, decimal_places=2)
    balance_amount = serializers.DecimalField(source='get_total_amount', read_only=True, max_digits=10, decimal_places=2)
    status = serializers.CharField(read_only=True)
    next_purchase_order_number = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrder
        fields = ['business','id','purchase_order_no', 'date', 'party', 'status', 'payment_term', 'due_date', 'purchaseorder_items', 'discount', 'balance_amount','total_amount','notes' , 'signature' ,'taxable_amount','next_purchase_order_number']
        read_only_fields = ['business']

    def get_balance_amount(self, obj):
        # Ensure obj is the model instance, not a dictionary
            total_amount = obj.get_total_amount()
            amount_received = Decimal(obj.amount_received) if obj.amount_received else Decimal(0)
            return total_amount - amount_received
    
    def get_next_purchase_order_number(self, obj):
        request = self.context.get('request')
        if request and request.user:
            business = get_current_business(request.user)
            return PurchaseOrder.get_next_purchase_order_number(business)
        return None

    def create(self, validated_data):
        purchaseorder_items_data = validated_data.pop('purchaseorder_items')
        purchaseorder = PurchaseOrder.objects.create(**validated_data)

        # Create PurchaseOrderItems and update stock for items
        for item_data in purchaseorder_items_data:
            item_data['purchaseorder'] = purchaseorder  # Set the foreign key to the created purchase order
            PurchaseOrderItem.objects.create(**item_data)
            
        return purchaseorder
    

    def update(self, instance, validated_data):
        print("Update")
        # Extract the invoice_items from validated data (if present)
        invoice_items_data = validated_data.pop('purchaseorder_items', [])
       
        # Step 1: Update invoice fields (main Invoice object)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()  # Save the main Invoice model after updating its fields
        
        # Step 2: Handle InvoiceItem updates/deletions
        existing_items = instance.purchaseorder_items.all()
        existing_item_ids = [item.id for item in existing_items]
        updated_item_ids = [item_data.get('id') for item_data in invoice_items_data if item_data.get('id')]

        # Step 3: Delete removed items
        for item_id in set(existing_item_ids) - set(updated_item_ids):
            item_to_delete = instance.purchaseorder_items.get(id=item_id)
            PurchaseOrderItemSerializer().delete(item_to_delete)

        # Step 4: Update or Create new items
        for item_data in invoice_items_data:
            item_id = item_data.get('id')
            if item_id:
                # Update existing item
                item_instance = instance.purchaseorder_items.get(id=item_id)
                PurchaseOrderItemSerializer().update(item_instance, item_data)
            else:
                # Create new item
                item_data['purchaseorder'] = instance  # Associate the new InvoiceItem with the current Invoice
                PurchaseOrderItem.objects.create(**item_data)

        # Step 5: Automatically recalculate balance after saving changes
        instance.save()  # This ensures the updated Invoice object reflects the changes

        return instance 
    
class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset=PurchaseOrder.objects.all()
    serializer_class=PurchaseOrderSerializer

