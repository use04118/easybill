from django.db import models
from datetime import datetime
from decimal import Decimal
from sales.models import Invoice, InvoiceItem
from django.db.models import JSONField  


class EWayBill(models.Model):
    TRANSPORT_MODES = [
        ('1', 'Road'),
        ('2', 'Rail'),
        ('3', 'Air'),
        ('4', 'Ship'),
    ]

    VEHICLE_TYPES = [
        ('O', 'ODC'),
        ('R', 'Regular'),
    ]

    status = models.CharField(max_length=30, choices=[
        ('Generated', 'Generated'),
        ('Cancelled', 'Cancelled'),
        ('Expired', 'Expired'),
        ('Updated', 'Updated'),
    ], default='Generated')

    invoice = models.OneToOneField(Invoice, on_delete=models.CASCADE, related_name='eway_bill')
    irn = models.CharField(max_length=64, unique=True)
    trans_id = models.CharField(max_length=15)
    trans_name = models.CharField(max_length=100)
    trans_mode = models.CharField(max_length=1, choices=TRANSPORT_MODES, default='1')
    distance = models.PositiveIntegerField(help_text="Distance between source and destination PIN codes", default=1)
    trans_doc_no = models.CharField(max_length=15)
    trans_doc_dt = models.CharField(max_length=10)  # Could use DateField if proper formatting is ensured
    veh_no = models.CharField(max_length=20)
    veh_type = models.CharField(max_length=1, choices=VEHICLE_TYPES)

    # Export Shipment Details
    exp_ship_addr1 = models.CharField(max_length=100)
    exp_ship_addr2 = models.CharField(max_length=100, blank=True, null=True)
    exp_ship_loc = models.CharField(max_length=100)
    exp_ship_pin = models.PositiveIntegerField()
    exp_ship_stcd = models.CharField(max_length=2)

    # Dispatch Details
    disp_name = models.CharField(max_length=100)
    disp_addr1 = models.CharField(max_length=100)
    disp_addr2 = models.CharField(max_length=100, blank=True, null=True)
    disp_loc = models.CharField(max_length=100)
    disp_pin = models.PositiveIntegerField()
    disp_stcd = models.CharField(max_length=2)

    generated_date = models.DateTimeField(blank=True, null=True)
    valid_upto = models.DateTimeField(blank=True, null=True)

    request_payload = models.JSONField(blank=True, null=True)
    response_payload = models.JSONField(blank=True, null=True)
    is_cancelled = models.BooleanField(default=False)
    cancel_reason = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_valid(self):
        return self.generated_date and self.valid_upto and self.valid_upto > datetime.now()

    def __str__(self):
        return f"E-Way Bill for Invoice {self.invoice.invoice_no or self.invoice.id} - {self.irn or 'Not Generated'}"
    
class EInvoice(models.Model):
    status = models.CharField(max_length=20, default='Pending', choices=[
        ('Pending', 'Pending'),
        ('Submitted', 'Submitted'),
        ('Rejected', 'Rejected'),
        ('Cancelled', 'Cancelled'),
    ])
    invoice = models.OneToOneField(Invoice, on_delete=models.CASCADE, related_name='e_invoice')
    # E-Invoice Core Fields
    irn = models.CharField(max_length=100, unique=True, null=True, blank=True, help_text="Invoice Reference Number from GST portal")
    raw_invoice = JSONField(blank=True, null=True, help_text="Generated JSON before NIC response")
    ack_no = models.CharField(max_length=50, null=True, blank=True, help_text="Acknowledgement Number from portal")
    ack_date = models.DateTimeField(null=True, blank=True, help_text="Acknowledgement DateTime")
    signed_invoice = models.TextField(null=True, blank=True, help_text="Signed e-invoice JSON or base64 content")
    signed_qr_code = models.TextField(null=True, blank=True, help_text="Base64 encoded QR code")
    qr_code_image = models.ImageField(upload_to='qr_codes/', null=True, blank=True, help_text="QR code image")
    # Invoice Details (Mirrored or Calculated from Invoice)
    invoice_type = models.CharField(max_length=20, default='B2B', choices=[('B2B', 'B2B'), ('B2C', 'B2C'), ('EXP', 'Export')])
    supply_type = models.CharField(max_length=20, default='Inter', choices=[('Inter', 'Inter State'), ('Intra', 'Intra State')])
    document_type = models.CharField(max_length=20, default='INV', choices=[('INV', 'Invoice'), ('CRN', 'Credit Note'), ('DBN', 'Debit Note')])
    # Party Information (can be fetched from the invoice or stored for redundancy/logging)
    seller_gstin = models.CharField(max_length=15)
    buyer_gstin = models.CharField(max_length=15)
    # Status & Response Tracking
    error_message = models.TextField(blank=True, null=True, help_text="Error or response from e-invoice API")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"E-Invoice for {self.invoice.invoice_no or 'Unknown'} - Status: {self.status}"
    
class GSTR1Reconciliation(models.Model):
    STATUS_CHOICES = [
        ('Matched', 'Matched'),
        ('Mismatched', 'Mismatched'),
        ('Missing in Portal', 'Missing in Portal'),
        ('Missing in System', 'Missing in System'),
    ]

    # Link to the Invoice model
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, null=True, blank=True, related_name='reconciliations')

    # GST Invoice details from the portal (EInvoice)
    gst_invoice_no = models.CharField(max_length=100, null=True, blank=True, help_text="Invoice number from GST portal")
    gst_invoice_date = models.DateField(null=True, blank=True, help_text="Invoice date from GST portal")
    gst_invoice_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Invoice value from GST portal")
    gst_gstin = models.CharField(max_length=15, null=True, blank=True, help_text="GSTIN of the buyer from GST portal")

    # Local invoice details from your system
    local_invoice_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Invoice value from system")
    local_gstin = models.CharField(max_length=15, null=True, blank=True, help_text="GSTIN of the buyer from system")
    
    # Reconciliation status and remarks
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Matched')
    remarks = models.TextField(null=True, blank=True, help_text="Any notes or reasons for mismatch")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"GSTR-1 Reconciliation - {self.invoice.invoice_number if self.invoice else 'Portal Only'} | Status: {self.status}"