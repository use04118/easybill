from rest_framework import serializers
from .models import AutomatedInvoice, AutomatedInvoiceItem
from inventory.models import Item, Service, GSTTaxRate
from sales.models import Tcs
from parties.models import Party
from users.models import Business  # adjust if needed
from django.db import transaction
from . utils import generate_sales_invoice_from_automated

class AutomatedInvoiceItemSerializer(serializers.ModelSerializer):
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
        model = AutomatedInvoiceItem
        fields = [
            'id', 'automatedinvoice', 'item', 'item_name', 'service', 'service_name', 
            'quantity', 'amount', 'price_item', 'available_stock', 'gstTaxRate', 
            'tax_rate', 'tax_rate_amount', 'cess_rate', 'cess_rate_amount' , 'cgst' , 'cgst_amount' ,'igst' , 'igst_amount' ,'sgst', 'sgst_amount', 'hsnCode' , 'sacCode',
            'salesPrice_with_tax', 'purchasePrice_with_tax', 'salesPrice_without_tax', 'purchasePrice_without_tax', 'salesPriceType','type','discount'
        ]
        extra_kwargs = {
            'automatedinvoice': {'required': False}  # This makes automated_invoice optional
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
        invoice_item = AutomatedInvoiceItem.objects.create(**validated_data)

        # Deduct stock if it's an item (not service)
        if item:
            item.closingStock -= validated_data['quantity']
            item.save()
        return invoice_item
    
    def update(self, instance, validated_data):
        """Update InvoiceItem and reverse stock if needed."""
        old_quantity = instance.quantity
        new_quantity = validated_data.get('quantity', old_quantity)
        item = instance.item

        # Reverse stock if item is being updated
        if item:
            item.closingStock += old_quantity  # Add back old stock
            item.save()

        # Deduct new stock if updated quantity is less
        if item and new_quantity > 0:
            if item.closingStock < new_quantity:
                raise serializers.ValidationError(f"Not enough stock for {item.itemName}. Available: {item.closingStock}")
            item.closingStock -= new_quantity
            item.save()

        # Update the InvoiceItem
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
    
    def delete(self, instance):
        print("Reverse stock when item is deleted.")
        item = instance.item
        if item:
            item.closingStock += instance.quantity
            item.save()
        instance.delete()

class AutomatedInvoiceSerializer(serializers.ModelSerializer):
    automatedinvoice_items = AutomatedInvoiceItemSerializer(many=True)
    total_amount = serializers.DecimalField(source='get_total_amount', read_only=True, max_digits=10, decimal_places=2)
    taxable_amount = serializers.DecimalField(source='get_taxable_amount', read_only=True, max_digits=10, decimal_places=2)
    balance_amount = serializers.DecimalField(source='get_total_amount', read_only=True, max_digits=10, decimal_places=2)  # You can change this if you implement actual balance logic
    tcs_on = serializers.ChoiceField(choices=AutomatedInvoice.TCS_ON_CHOICES, required=False)
    tcs_amount = serializers.DecimalField(source='get_tcs_amount', read_only=True, max_digits=10, decimal_places=2)
    status = serializers.CharField(read_only=True)

    class Meta:
        model = AutomatedInvoice
        fields = [
            'id', 'business', 'automated_invoice_no', 'start_date', 'end_date',
            'repeat_every', 'repeat_unit', 'party', 'payment_terms', 'discount',
            'apply_tcs','tcs_on','tcs', 'tcs_amount', 'notes', 'signature', 'status',
            'automatedinvoice_items', 'total_amount', 'taxable_amount', 'balance_amount'
        ]
        read_only_fields = [
            'business', 'total_amount', 'balance_amount',
            'taxable_amount', 'tcs_amount'  # ✅ Make sure they're not editable
        ]


    def create(self, validated_data):
        request = self.context.get('request')  # ✅ Safe check
        if not request or not hasattr(request, 'user'):
            raise serializers.ValidationError("Request context with authenticated user is required.")

        # Try to get the business associated with the user
        business = getattr(request.user, 'current_business', None) or \
                getattr(request.user, 'owned_businesses', None).first()  # Try fallbacks

        if not business:
            raise serializers.ValidationError("User does not belong to any business.")

        with transaction.atomic():
            invoice_items_data = validated_data.pop('automatedinvoice_items', [])
            validated_data['business'] = business

            invoice = AutomatedInvoice.objects.create(**validated_data)

            for item_data in invoice_items_data:
                item_data['automatedinvoice'] = invoice
                AutomatedInvoiceItem.objects.create(**item_data)

            invoice.save()

            # Generate sales invoice
            generate_sales_invoice_from_automated(invoice)

            return invoice

    
    def update(self, instance, validated_data):
        print("Update")
        # Extract the invoice_items from validated data (if present)
        invoice_items_data = validated_data.pop('automatedinvoice_items', [])
       
        # Step 1: Update invoice fields (main Invoice object)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()  # Save the main Invoice model after updating its fields
        
        # Step 2: Handle InvoiceItem updates/deletions
        existing_items = instance.automatedinvoice_items.all()
        existing_item_ids = [item.id for item in existing_items]
        updated_item_ids = [item_data.get('id') for item_data in invoice_items_data if item_data.get('id')]

        # Step 3: Delete removed items
        for item_id in set(existing_item_ids) - set(updated_item_ids):
            item_to_delete = instance.automatedinvoice_items.get(id=item_id)
            AutomatedInvoiceItemSerializer().delete(item_to_delete)

        # Step 4: Update or Create new items
        for item_data in invoice_items_data:
            item_id = item_data.get('id')
            if item_id:
                # Update existing item
                item_instance = instance.automatedinvoice_items.get(id=item_id)
                AutomatedInvoiceItemSerializer().update(item_instance, item_data)
            else:
                # Create new item
                # item_data['a' \
                item_data['automatedinvoice'] = instance  # Associate the new InvoiceItem with the current Invoice
                AutomatedInvoiceItem.objects.create(**item_data)

        # Step 5: Automatically recalculate balance after saving changes
        instance.save()  # This ensures the updated Invoice object reflects the changes

        return instance