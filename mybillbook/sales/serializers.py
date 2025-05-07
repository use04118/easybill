from rest_framework import serializers, viewsets
from .models import Invoice, Quotation, SalesReturn, PaymentIn, CreditNote, DeliveryChallan, Proforma, InvoiceItem,QuotationItem,SalesReturnItem, DeliveryChallanItem, CreditNoteItem, ProformaItem,PaymentInInvoice
from inventory.models import Item, Service,GSTTaxRate # Your Item model,
from inventory.serializers import ItemSerializer
from rest_framework import serializers
from django.db import transaction
from .models import Invoice, InvoiceItem
from decimal import Decimal 
from django.db import transaction
from .models import Tcs, Tds
from users.utils import get_current_business
from cash_and_bank.models import BankAccount
from cash_and_bank.serializers import BankAccountSerializer
BANK_PAYMENT_METHODS = ["UPI", "Card", "Netbanking", "Bank Transfer", "Cheque"]

class TcsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tcs
        fields = ['id', 'rate', 'section', 'description', 'condition', 'business']
        read_only_fields = ['business']


class TdsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tds
        fields = ['id', 'rate', 'section', 'description', 'business']
        read_only_fields = ['business']


class InvoiceItemSerializer(serializers.ModelSerializer):
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
        model = InvoiceItem
        fields = [
            'id', 'invoice', 'item', 'item_name', 'service', 'service_name', 
            'quantity', 'unit_price', 'amount', 'price_item', 'available_stock', 'gstTaxRate', 'discount',
            'tax_rate', 'tax_rate_amount', 'cess_rate', 'cess_rate_amount' , 'igst' , 'igst_amount' , 'cgst' , 'cgst_amount' , 'sgst', 'sgst_amount', 'hsnCode' , 'sacCode',
            'salesPrice_with_tax', 'purchasePrice_with_tax', 'salesPrice_without_tax', 'purchasePrice_without_tax', 'salesPriceType','type'
        ]
        extra_kwargs = {
            'invoice': {'required': False}  # 👈 This is the fix
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
        invoice_item = InvoiceItem.objects.create(**validated_data)

        # ✅ Deduct stock if it's an item (not service)
        if item:
            item.closingStock -= validated_data['quantity']
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
        print("""Reverse stock when item is deleted.""")
        item = instance.item
        if item:
            item.closingStock += instance.quantity
            item.save()
        instance.delete()

class InvoiceSerializer(serializers.ModelSerializer):
    invoice_items = InvoiceItemSerializer(many=True, required=False)
    total_amount = serializers.DecimalField(source='get_total_amount', read_only=True, max_digits=10, decimal_places=2)
    balance_amount = serializers.DecimalField(source='get_balance_amount', read_only=True, max_digits=10, decimal_places=2)
    taxable_amount = serializers.DecimalField(source='get_taxable_amount', read_only=True, max_digits=10, decimal_places=2)
    tcs_on = serializers.ChoiceField(choices=Invoice.TCS_ON_CHOICES, required=False)
    tcs_amount = serializers.DecimalField(source='get_tcs_amount', read_only=True, max_digits=10, decimal_places=2)
    status = serializers.CharField(read_only=True)
    next_invoice_number = serializers.SerializerMethodField()
    bank_account = serializers.PrimaryKeyRelatedField(
        queryset=BankAccount.objects.all(),
        required=False,
        allow_null=True
    )

    class Meta:
        model = Invoice
        fields = [
            'business', 'id', 'invoice_no', 'date', 'party', 'status',
            'payment_term', 'due_date', 'amount_received', 'is_fully_paid',
            'payment_method', 'discount', 'total_amount', 'balance_amount',
            'invoice_items', 'notes', 'signature', 'taxable_amount',
            'apply_tcs', 'tcs', 'tcs_on', 'tcs_amount', 'next_invoice_number',
            'bank_account'
        ]
        read_only_fields = [
            'business', 'total_amount', 'balance_amount',
            'taxable_amount', 'tcs_amount', 'next_invoice_number'
        ]

    def get_next_invoice_number(self, obj):
        request = self.context.get('request')
        if request and request.user:
            business = get_current_business(request.user)
            return Invoice.get_next_invoice_number(business)
        return None

    def get_balance_amount(self, obj):
        # Ensure that both operands are of the same type (Decimal)
        total_amount = obj.get_total_amount()
        amount_received = Decimal(obj.amount_received)  # Convert amount_received to Decimal

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

    def create(self, validated_data):
        print("create")
        invoice_items_data = validated_data.pop('invoice_items', [])
            
        invoice = Invoice.objects.create(**validated_data)

        # ✅ Create each InvoiceItem without validation errors
        for item_data in invoice_items_data:
            item_data['invoice'] = invoice  # Inject invoice here after creation
            InvoiceItem.objects.create(**item_data)

        # ✅ The save() method in Invoice will automatically update balance
        invoice.save()
        return invoice

    def update(self, instance, validated_data):
        print("Update")
        # Extract the invoice_items from validated data (if present)
        invoice_items_data = validated_data.pop('invoice_items', [])
       
        # Step 1: Update invoice fields (main Invoice object)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()  # Save the main Invoice model after updating its fields
        
        # Step 2: Handle InvoiceItem updates/deletions
        existing_items = instance.invoice_items.all()
        existing_item_ids = [item.id for item in existing_items]
        updated_item_ids = [item_data.get('id') for item_data in invoice_items_data if item_data.get('id')]

        # Step 3: Delete removed items
        for item_id in set(existing_item_ids) - set(updated_item_ids):
            item_to_delete = instance.invoice_items.get(id=item_id)
            InvoiceItemSerializer().delete(item_to_delete)

        # Step 4: Update or Create new items
        for item_data in invoice_items_data:
            item_id = item_data.get('id')
            if item_id:
                # Update existing item
                item_instance = instance.invoice_items.get(id=item_id)
                InvoiceItemSerializer().update(item_instance, item_data)
            else:
                # Create new item
                item_data['invoice'] = instance  # Associate the new InvoiceItem with the current Invoice
                InvoiceItem.objects.create(**item_data)

        # Step 5: Automatically recalculate balance after saving changes
        instance.save()  # This ensures the updated Invoice object reflects the changes

        return instance

class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer


class QuotationItemSerializer(serializers.ModelSerializer):
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
        model = QuotationItem
        fields = [
            'id', 'quotation', 'item', 'item_name', 'service', 'service_name', 
            'quantity', 'unit_price', 'amount', 'price_item', 'available_stock', 'gstTaxRate', 
            'tax_rate', 'tax_rate_amount', 'cess_rate', 'cess_rate_amount' , 'cgst' , 'cgst_amount' ,'igst' , 'igst_amount' ,'sgst', 'sgst_amount', 'hsnCode' , 'sacCode',
            'salesPrice_with_tax', 'purchasePrice_with_tax', 'salesPrice_without_tax', 'purchasePrice_without_tax', 'salesPriceType','type','discount'
        ]
        extra_kwargs = {
            'quotation': {'required': False}  # 👈 This is the fix
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
        invoice_item = QuotationItem.objects.create(**validated_data)

        # ✅ Deduct stock if it's an item (not service)
        if item:
            item.closingStock -= validated_data['quantity']
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
        print("""Reverse stock when item is deleted.""")
        item = instance.item
        if item:
            item.closingStock += instance.quantity
            item.save()
        instance.delete()

class QuotationSerializer(serializers.ModelSerializer):
    quotation_items = QuotationItemSerializer(many=True)
    total_amount = serializers.DecimalField(source='get_total_amount', read_only=True, max_digits=10, decimal_places=2)
    taxable_amount = serializers.DecimalField(source='get_taxable_amount', read_only=True, max_digits=10, decimal_places=2)
    balance_amount = serializers.DecimalField(source='get_total_amount', read_only=True, max_digits=10, decimal_places=2)
    status = serializers.CharField(read_only=True)
    next_quotation_number = serializers.SerializerMethodField()

    class Meta:
        model = Quotation
        fields = fields = [
            'business','id', 'quotation_no', 'date', 'party', 'status', 
            'payment_term', 'due_date', 'discount', 'total_amount', 'balance_amount', 'quotation_items', 'notes' , 'signature' , 'taxable_amount','next_quotation_number'
        ]
        read_only_fields = ['business','next_quotation_number']

    
    def get_next_quotation_number(self, obj):
        request = self.context.get('request')
        if request and request.user:
            business = get_current_business(request.user)
            return Quotation.get_next_quotation_number(business)
        return None

    def create(self, validated_data):
        print("create")
        invoice_items_data = validated_data.pop('quotation_items', [])
            
        invoice = Quotation.objects.create(**validated_data)

        # ✅ Create each InvoiceItem without validation errors
        for item_data in invoice_items_data:
            item_data['quotation'] = invoice  # Inject invoice here after creation
            QuotationItem.objects.create(**item_data)

        # ✅ The save() method in Invoice will automatically update balance
        invoice.save()
        return invoice

    def update(self, instance, validated_data):
        print("Update")
        # Extract the invoice_items from validated data (if present)
        invoice_items_data = validated_data.pop('quotation_items', [])
       
        # Step 1: Update invoice fields (main Invoice object)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()  # Save the main Invoice model after updating its fields
        
        # Step 2: Handle InvoiceItem updates/deletions
        existing_items = instance.quotation_items.all()
        existing_item_ids = [item.id for item in existing_items]
        updated_item_ids = [item_data.get('id') for item_data in invoice_items_data if item_data.get('id')]

        # Step 3: Delete removed items
        for item_id in set(existing_item_ids) - set(updated_item_ids):
            item_to_delete = instance.quotation_items.get(id=item_id)
            QuotationItemSerializer().delete(item_to_delete)

        # Step 4: Update or Create new items
        for item_data in invoice_items_data:
            item_id = item_data.get('id')
            if item_id:
                # Update existing item
                item_instance = instance.quotation_items.get(id=item_id)
                QuotationItemSerializer().update(item_instance, item_data)
            else:
                # Create new item
                item_data['quotation'] = instance  # Associate the new InvoiceItem with the current Invoice
                QuotationItem.objects.create(**item_data)

        # Step 5: Automatically recalculate balance after saving changes
        instance.save()  # This ensures the updated Invoice object reflects the changes

        return instance  
    
class QuotationViewSet(viewsets.ModelViewSet):
    queryset=Quotation.objects.all()
    serializer_class=QuotationSerializer


class SalesReturnItemSerializer(serializers.ModelSerializer):
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
        model = SalesReturnItem
        fields = [
            'id', 'salesreturn', 'item', 'item_name', 'service', 'service_name', 
            'quantity', 'unit_price', 'amount', 'price_item', 'available_stock', 'gstTaxRate', 
            'tax_rate', 'tax_rate_amount', 'cess_rate', 'cess_rate_amount' , 'cgst' , 'cgst_amount' ,'igst' , 'igst_amount','sgst', 'sgst_amount', 'hsnCode' , 'sacCode',
        'salesPrice_with_tax', 'purchasePrice_with_tax', 'salesPrice_without_tax', 'purchasePrice_without_tax', 'salesPriceType','type','discount'
       ]
        extra_kwargs = {
            'salesreturn': {'required': False}  # 👈 This is the fix
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
        invoice_item = SalesReturnItem.objects.create(**validated_data)

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
            item.closingStock += new_quantity
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

class SalesReturnSerializer(serializers.ModelSerializer):
    salesreturn_items = SalesReturnItemSerializer(many=True, required=False)
    total_amount = serializers.DecimalField(source='get_total_amount', read_only=True, max_digits=10, decimal_places=2)
    taxable_amount = serializers.DecimalField(source='get_taxable_amount', read_only=True, max_digits=10, decimal_places=2)
    balance_amount = serializers.DecimalField(source='get_balance_amount', read_only=True, max_digits=10, decimal_places=2)
    tcs_on = serializers.ChoiceField(choices=Invoice.TCS_ON_CHOICES, required=False)
    tcs_amount = serializers.DecimalField(source='get_tcs_amount', read_only=True, max_digits=10, decimal_places=2)
    status = serializers.CharField(read_only=True)
    next_salesreturn_number = serializers.SerializerMethodField()
    bank_account = serializers.PrimaryKeyRelatedField(
        queryset=BankAccount.objects.all(),
        required=False,
        allow_null=True
    )


    class Meta:
        model = SalesReturn
        fields = [
            'business','id', 'salesreturn_no', 'date', 'party', 'status', 
            'amount_received', 'is_fully_paid','invoice_no','invoice_id',
            'payment_method', 'discount', 'total_amount', 'balance_amount', 'salesreturn_items', 'notes' , 'signature' ,'taxable_amount',
            'apply_tcs', 'tcs', 'tcs_on', 'tcs_amount','next_salesreturn_number','bank_account'
        ]
        read_only_fields = ['business', 'total_amount', 'balance_amount',
            'taxable_amount', 'tcs_amount','next_salesreturn_number' ]
    
    def get_next_salesreturn_number(self, obj):
        request = self.context.get('request')
        if request and request.user:
            business = get_current_business(request.user)
            return SalesReturn.get_next_salesreturn_number(business)
        return None
    
    
    def get_balance_amount(self, obj):
        # Ensure that both operands are of the same type (Decimal)
        total_amount = obj.get_total_amount()
        amount_received = Decimal(obj.amount_received)  # Convert amount_received to Decimal

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

    def create(self, validated_data):
        print("create")
        invoice_items_data = validated_data.pop('salesreturn_items', [])
            
        invoice = SalesReturn.objects.create(**validated_data)

        # ✅ Create each InvoiceItem without validation errors
        for item_data in invoice_items_data:
            item_data['salesreturn'] = invoice  # Inject invoice here after creation
            SalesReturnItem.objects.create(**item_data)


        # ✅ The save() method in Invoice will automatically update balance
        invoice.save()
        return invoice

    def update(self, instance, validated_data):
        invoice_items_data = validated_data.pop('salesreturn_items', [])

        # ✅ Step 1: Update invoice fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # ✅ Step 2: Handle InvoiceItem update/delete
        existing_items = instance.salesreturn_items.all()
        existing_item_ids = [item.id for item in existing_items]
        updated_item_ids = [item_data.get('id') for item_data in invoice_items_data if item_data.get('id')]

        # ✅ Step 3: Delete removed items
        for item_id in set(existing_item_ids) - set(updated_item_ids):
            item_to_delete = instance.salesreturn_items.get(id=item_id)
            SalesReturnItemSerializer().delete(item_to_delete)

        # ✅ Step 4: Update or Create new items
        for item_data in invoice_items_data:
            item_id = item_data.get('id')
            if item_id:
                # Update existing item
                item_instance = instance.salesreturn_items.get(id=item_id)
                SalesReturnItemSerializer().update(item_instance, item_data)
            else:
                # Create new item
                item_data['salesreturn'] = instance
                SalesReturnItem.objects.create(**item_data)

        # ✅ Step 5: Automatically recalculate balance
        instance.save()
        return instance

class SalesReturnViewSet(viewsets.ModelViewSet):
    queryset=SalesReturn.objects.all()
    serializer_class=SalesReturnSerializer


class InvoiceSettlementSerializer(serializers.Serializer):
    invoice = serializers.PrimaryKeyRelatedField(queryset=Invoice.objects.all())
    settled_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    apply_tds = serializers.BooleanField(default=False)
    tds_rate = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)

    def validate(self, data):
        if data['apply_tds'] and data.get('tds_rate') is None:
            raise serializers.ValidationError("TDS rate must be provided if apply_tds is True.")
        return data


class PaymentInSerializer(serializers.ModelSerializer):
    settled_invoices = InvoiceSettlementSerializer(many=True, write_only=True)
    settled_invoice_details = serializers.SerializerMethodField()
    next_payment_in_number = serializers.SerializerMethodField()
    bank_account = serializers.PrimaryKeyRelatedField(
        queryset=BankAccount.objects.all(),
        required=False,
        allow_null=True
    )
    class Meta:
        model = PaymentIn
        fields = [
            'id', 'business', 'party', 'date', 'payment_mode', 'payment_in_number',
            'amount', 'notes', 'settled_invoices', 'settled_invoice_details','next_payment_in_number',
            'bank_account'
        ]
        read_only_fields = ['business', 'settled_invoice_details','next_payment_in_number']


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
    def get_settled_invoice_details(self, obj):
        return [
            {
                "invoice_id": record.invoice.id,
                "invoice_number": record.invoice.invoice_no,
                "settled_amount": record.settled_amount,
                "tds_applied": record.apply_tds,
                "tds_rate": record.tds_rate,
                "tds_amount": record.tds_amount
            }
            for record in PaymentInInvoice.objects.filter(payment_in=obj).select_related("invoice")
        ]

    def create(self, validated_data):
        settled_invoices_data = validated_data.pop('settled_invoices', [])
        payment_in = PaymentIn.objects.create(**validated_data)

        from .utils import apply_payment_to_invoices
        apply_payment_to_invoices(payment_in, settled_invoices_data)

        return payment_in
    
    def get_next_payment_in_number(self, obj):
        request = self.context.get('request')
        if request and request.user:
            business = get_current_business(request.user)
            return PaymentIn.get_next_payment_in_number(business)
        return None
    


class CreditNoteItemSerializer(serializers.ModelSerializer):
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
        model = CreditNoteItem
        fields = ['id','creditnote','item', 'item_name', 'quantity', 'unit_price', 'amount','price_item', 'available_stock', 'service', 'service_name','gstTaxRate', 'tax_rate', 'tax_rate_amount', 'cess_rate', 'cess_rate_amount' , 'cgst' , 'cgst_amount','igst' , 'igst_amount' , 'sgst', 'sgst_amount','hsnCode','sacCode','salesPrice_with_tax', 'purchasePrice_with_tax', 'salesPrice_without_tax', 'purchasePrice_without_tax', 'salesPriceType','type','discount'
       ]
        extra_kwargs = {
            'creditnote': {'required': False}  # 👈 This is the fix
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
        invoice_item = CreditNoteItem.objects.create(**validated_data)

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
            item.closingStock += new_quantity
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

class CreditNoteSerializer(serializers.ModelSerializer):
    creditnote_items = CreditNoteItemSerializer(many=True)
    total_amount = serializers.DecimalField(source='get_total_amount', read_only=True, max_digits=10, decimal_places=2)
    balance_amount = serializers.DecimalField(source='get_balance_amount', read_only=True, max_digits=10, decimal_places=2)
    taxable_amount = serializers.DecimalField(source='get_taxable_amount', read_only=True, max_digits=10, decimal_places=2)
    tcs_on = serializers.ChoiceField(choices=Invoice.TCS_ON_CHOICES, required=False)
    tcs_amount = serializers.DecimalField(source='get_tcs_amount', read_only=True, max_digits=10, decimal_places=2)
    status = serializers.CharField(read_only=True)
    next_creditnote_number = serializers.SerializerMethodField()
    bank_account = serializers.PrimaryKeyRelatedField(
        queryset=BankAccount.objects.all(),
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = CreditNote
        fields = ['business','id','credit_note_no', 'date', 'party', 'status', 'amount_received',
                  'is_fully_paid','payment_method', 'total_amount', 'balance_amount','creditnote_items','discount', 
                  'notes' , 'signature' , 'taxable_amount',
            'apply_tcs', 'tcs', 'tcs_on', 'tcs_amount' ,'salesreturn_no' , 'salesreturn_id','next_creditnote_number','bank_account']
        
        read_only_fields = ['business', 'total_amount', 'balance_amount',
            'taxable_amount', 'tcs_amount' ,'next_creditnote_number']
        
    def get_next_creditnote_number(self, obj):
        request = self.context.get('request')
        if request and request.user:
            business = get_current_business(request.user)
            return CreditNote.get_next_creditnote_number(business)
        return None


    def get_balance_amount(self, obj):
        # Ensure that both operands are of the same type (Decimal)
        total_amount = obj.get_total_amount()
        amount_received = Decimal(obj.amount_received)  # Convert amount_received to Decimal

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

        
    def create(self, validated_data):
        invoice_items_data = validated_data.pop('creditnote_items')
        invoice = CreditNote.objects.create(**validated_data)

        # Create invoice items and associate them with the invoice
        for item_data in invoice_items_data:
            item_data['creditnote'] = invoice  # Set the foreign key to the created invoice
            CreditNoteItem.objects.create(**item_data)

        invoice.save()
        return invoice

    def update(self, instance, validated_data):
        invoice_items_data = validated_data.pop('creditnote_items', [])


        # ✅ Step 1: Update invoice fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # ✅ Step 2: Handle InvoiceItem update/delete
        existing_items = instance.creditnote_items.all()
        existing_item_ids = [item.id for item in existing_items]
        updated_item_ids = [item_data.get('id') for item_data in invoice_items_data if item_data.get('id')]

        # ✅ Step 3: Delete removed items
        for item_id in set(existing_item_ids) - set(updated_item_ids):
            item_to_delete = instance.creditnote_items.get(id=item_id)
            CreditNoteItemSerializer().delete(item_to_delete)

        # ✅ Step 4: Update or Create new items
        for item_data in invoice_items_data:
            item_id = item_data.get('id')
            if item_id:
                # Update existing item
                item_instance = instance.creditnote_items.get(id=item_id)
                CreditNoteItemSerializer().update(item_instance, item_data)
            else:
                # Create new item
                item_data['creditnote'] = instance
                CreditNoteItem.objects.create(**item_data)

        # ✅ Step 5: Automatically recalculate balance
        instance.save()
        return instance

class CreditNoteViewSet(viewsets.ModelViewSet):
    queryset=CreditNote.objects.all()
    serializer_class=CreditNoteSerializer


class DeliveryChallanItemSerializer(serializers.ModelSerializer):
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
        model = DeliveryChallanItem
        fields = [ 'id','deliverychallan','item', 'item_name', 'unit_price', 'quantity', 'amount', 'price_item','available_stock','gstTaxRate' ,'service', 'service_name','tax_rate', 'tax_rate_amount', 'cess_rate', 'cess_rate_amount' , 'cgst' , 'cgst_amount' ,'igst' , 'igst_amount' ,'sgst', 'sgst_amount','hsnCode','sacCode','salesPrice_with_tax', 'purchasePrice_with_tax', 'salesPrice_without_tax', 'purchasePrice_without_tax', 'salesPriceType','type','discount'
        ]
        
        extra_kwargs = {
            'deliverychallan': {'required': False}  # 👈 This is the fix
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
        invoice_item = DeliveryChallanItem.objects.create(**validated_data)

        # ✅ Deduct stock if it's an item (not service)
        if item:
            item.closingStock -= validated_data['quantity']
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
        print("""Reverse stock when item is deleted.""")
        item = instance.item
        if item:
            item.closingStock += instance.quantity
            item.save()
        instance.delete()
        
class DeliveryChallanSerializer(serializers.ModelSerializer):
    deliverychallan_items = DeliveryChallanItemSerializer(many=True)
    total_amount = serializers.DecimalField(source='get_total_amount', read_only=True, max_digits=10, decimal_places=2)
    taxable_amount = serializers.DecimalField(source='get_taxable_amount', read_only=True, max_digits=10, decimal_places=2)
    balance_amount = serializers.DecimalField(source='get_total_amount', read_only=True, max_digits=10, decimal_places=2)
    status = serializers.CharField(read_only=True)
    next_deliverychallan_number = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryChallan
        fields = ['business','id','delivery_challan_no', 'date', 'party', 'status',  
                  'deliverychallan_items','discount', 'total_amount',
                  'balance_amount','notes' , 'signature' ,'taxable_amount','next_deliverychallan_number']
        read_only_fields = ['business','next_deliverychallan_number']

    def get_next_deliverychallan_number(self, obj):
        request = self.context.get('request')
        if request and request.user:
            business = get_current_business(request.user)
            return DeliveryChallan.get_next_deliverychallan_number(business)
        return None


    def get_balance_amount(self, obj):
        # Ensure obj is the model instance, not a dictionary
            total_amount = obj.get_total_amount()
            amount_received = Decimal(obj.amount_received) if obj.amount_received else Decimal(0)
            return total_amount - amount_received

    def create(self, validated_data):
        deliverychallan_items_data = validated_data.pop('deliverychallan_items')
        deliverychallan = DeliveryChallan.objects.create(**validated_data)

        for item_data in deliverychallan_items_data:
            item_data['deliverychallan'] = deliverychallan
            DeliveryChallanItem.objects.create(**item_data)

        return deliverychallan
    
    def update(self, instance, validated_data):
        print("Update")
        # Extract the invoice_items from validated data (if present)
        invoice_items_data = validated_data.pop('deliverychallan_items', [])
       
        # Step 1: Update invoice fields (main Invoice object)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()  # Save the main Invoice model after updating its fields
        
        # Step 2: Handle InvoiceItem updates/deletions
        existing_items = instance.deliverychallan_items.all()
        existing_item_ids = [item.id for item in existing_items]
        updated_item_ids = [item_data.get('id') for item_data in invoice_items_data if item_data.get('id')]

        # Step 3: Delete removed items
        for item_id in set(existing_item_ids) - set(updated_item_ids):
            item_to_delete = instance.deliverychallan_items.get(id=item_id)
            DeliveryChallanItemSerializer().delete(item_to_delete)

        # Step 4: Update or Create new items
        for item_data in invoice_items_data:
            item_id = item_data.get('id')
            if item_id:
                # Update existing item
                item_instance = instance.deliverychallan_items.get(id=item_id)
                DeliveryChallanItemSerializer().update(item_instance, item_data)
            else:
                # Create new item
                item_data['deliverychallan'] = instance  # Associate the new InvoiceItem with the current Invoice
                DeliveryChallanItem.objects.create(**item_data)

        # Step 5: Automatically recalculate balance after saving changes
        instance.save()  # This ensures the updated Invoice object reflects the changes

        return instance  
  
class DeliveryChallanViewSet(viewsets.ModelViewSet):
    queryset=DeliveryChallan.objects.all()
    serializer_class=DeliveryChallanSerializer


class ProformaItemSerializer(serializers.ModelSerializer):
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
        model = ProformaItem
        fields = [ 'id','proforma','item', 'item_name', 'quantity', 'unit_price', 'amount', 'price_item','available_stock','gstTaxRate', 'service', 'service_name','tax_rate', 'tax_rate_amount', 'cess_rate', 'cess_rate_amount' , 'cgst' , 'cgst_amount' ,'igst' , 'igst_amount', 'sgst', 'sgst_amount','hsnCode','sacCode','salesPrice_with_tax', 'purchasePrice_with_tax', 'salesPrice_without_tax', 'purchasePrice_without_tax', 'salesPriceType','type','discount'
        ]
        
        extra_kwargs = {
            'proforma': {'required': False}  # 👈 This is the fix
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
        invoice_item = DeliveryChallanItem.objects.create(**validated_data)

        # ✅ Deduct stock if it's an item (not service)
        if item:
            item.closingStock -= validated_data['quantity']
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
        print("""Reverse stock when item is deleted.""")
        item = instance.item
        if item:
            item.closingStock += instance.quantity
            item.save()
        instance.delete()
    
class ProformaSerializer(serializers.ModelSerializer):
    proforma_items = ProformaItemSerializer(many=True)
    total_amount = serializers.DecimalField(source='get_total_amount',read_only=True, max_digits=10, decimal_places=2)
    taxable_amount = serializers.DecimalField(source='get_taxable_amount', read_only=True, max_digits=10, decimal_places=2)
    balance_amount = serializers.DecimalField(source='get_total_amount', read_only=True, max_digits=10, decimal_places=2)
    status = serializers.CharField(read_only=True)
    next_proforma_number = serializers.SerializerMethodField()

    class Meta:
        model = Proforma
        fields = ['business','id','proforma_no', 'date', 'party', 'status', 'payment_term', 
                  'due_date', 'proforma_items', 'discount', 'total_amount', 'balance_amount','notes' , 'signature' ,'taxable_amount','next_proforma_number']
        read_only_fields = ['business','next_proforma_number']

    def get_next_proforma_number(self, obj):
        request = self.context.get('request')
        if request and request.user:
            business = get_current_business(request.user)
            return Proforma.get_next_proforma_number(business)
        return None


    def create(self, validated_data):
        proforma_items_data = validated_data.pop('proforma_items')
        proforma = Proforma.objects.create(**validated_data)

        for item_data in proforma_items_data:
            item_data['proforma'] = proforma
            ProformaItem.objects.create(**item_data)

        return proforma
    
    def update(self, instance, validated_data):
        print("Update")
        # Extract the invoice_items from validated data (if present)
        invoice_items_data = validated_data.pop('proforma_items', [])
       
        # Step 1: Update invoice fields (main Invoice object)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()  # Save the main Invoice model after updating its fields
        
        # Step 2: Handle InvoiceItem updates/deletions
        existing_items = instance.proforma_items.all()
        existing_item_ids = [item.id for item in existing_items]
        updated_item_ids = [item_data.get('id') for item_data in invoice_items_data if item_data.get('id')]

        # Step 3: Delete removed items
        for item_id in set(existing_item_ids) - set(updated_item_ids):
            item_to_delete = instance.proforma_items.get(id=item_id)
            ProformaItemSerializer().delete(item_to_delete)

        # Step 4: Update or Create new items
        for item_data in invoice_items_data:
            item_id = item_data.get('id')
            if item_id:
                # Update existing item
                item_instance = instance.proforma_items.get(id=item_id)
                ProformaItemSerializer().update(item_instance, item_data)
            else:
                # Create new item
                item_data['proforma'] = instance  # Associate the new InvoiceItem with the current Invoice
                ProformaItem.objects.create(**item_data)

        # Step 5: Automatically recalculate balance after saving changes
        instance.save()  # This ensures the updated Invoice object reflects the changes

        return instance 
  
class ProformaViewSet(viewsets.ModelViewSet):
    queryset=Proforma.objects.all()
    serializer_class=ProformaSerializer