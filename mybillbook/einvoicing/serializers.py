from rest_framework import serializers, viewsets
from sales.models import Invoice
from rest_framework import serializers
from django.db import transaction
from .models import EWayBill, EInvoice,GSTR1Reconciliation
from datetime import datetime

class EWayBillSerializer(serializers.ModelSerializer):
    is_valid = serializers.SerializerMethodField()

    class Meta:
        model = EWayBill
        fields = [
            'id','invoice','transporter_id','transporter_name','vehicle_number','mode','distance','status','ewb_number','generated_date','valid_upto','request_payload','response_payload','is_cancelled','cancel_reason','is_valid', 'created_at','updated_at',
        ]
        read_only_fields = [
            'status','ewb_number','generated_date','valid_upto','request_payload','response_payload','is_valid','created_at','updated_at',
        ]

    def get_is_valid(self, obj):
        return obj.is_valid()



def generate_eway_bill(invoice_id):
    invoice = Invoice.objects.get(id=invoice_id)

    # Construct payload (based on NIC/GSP API format)
    payload = {
        "supplyType": "Outward",
        "subSupplyType": 1,
        "docType": "INV",
        "docNo": invoice.invoice_no,
        "docDate": invoice.date.strftime("%d/%m/%Y"),
        "fromGstin": invoice.business.gstin,
        "fromAddr1": invoice.business.address,
        "fromPlace": invoice.business.city,
        "fromPincode": invoice.business.pincode,
        "fromStateCode": invoice.business.state_code,
        "toGstin": invoice.party.gstin,
        "toAddr1": invoice.party.address,
        "toPlace": invoice.party.city,
        "toPincode": invoice.party.pincode,
        "toStateCode": invoice.party.state_code,
        "totalValue": float(invoice.get_total_amount()),
        "transMode": "1",  # Road
        "transDistance": 50,
        "transporterId": "TRANS12345",
        "vehicleNo": "MH12AB1234",
    }

    # Here you’d encrypt + sign + send this payload to your GSP provider
    # Mock response for now:
    ewb_data = {
        "ewbNo": "181001323456",
        "ewayBillDate": "16/04/2025 13:23:00",
        "validUpto": "17/04/2025 23:59:00",
        "status": "Generated"
    }

    # Create and save EWayBill object
    EWayBill.objects.create(
        invoice=invoice,
        ewb_number=ewb_data["ewbNo"],
        generated_date=datetime.strptime(ewb_data["ewayBillDate"], "%d/%m/%Y %H:%M:%S"),
        valid_upto=datetime.strptime(ewb_data["validUpto"], "%d/%m/%Y %H:%M:%S"),
        status=ewb_data["status"],
        request_payload=payload,
        response_payload=ewb_data
    )

class EInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = EInvoice
        fields = '__all__'
        # Make `created_at` and `updated_at` read-only, they will be set automatically
        # read_only_fields = ('created_at', 'updated_at')
class GSTR1ReconciliationSerializer(serializers.ModelSerializer):
    # Include fields from the related Invoice model if needed
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)
    invoice_date = serializers.DateField(source='invoice.invoice_date', read_only=True)
    local_invoice_value = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    local_gstin = serializers.CharField(source='invoice.gstin', read_only=True)

    class Meta:
        model = GSTR1Reconciliation
        fields = [
            'id',
            'invoice_number',
            'invoice_date',
            'local_invoice_value',
            'local_gstin',
            'gst_invoice_no',
            'gst_invoice_date',
            'gst_invoice_value',
            'gst_gstin',
            'status',  # Make sure status is included in the response
            'remarks',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['status']  # This ensures status cannot be set by the user in input

    def validate(self, data):
        # You can add custom validation logic here if needed
        return data