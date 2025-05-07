from datetime import date, timedelta
from django.db import transaction
from rest_framework import status

from .models import AutomatedInvoice
from sales.models import Invoice, InvoiceItem
from sales.serializers import InvoiceSerializer, InvoiceItemSerializer
from users.utils import get_current_business
from django.utils import timezone

def generate_invoice_no(business):
    today = timezone.now().strftime("%Y%m%d")  # Correct usage of timezone.now()
    count = Invoice.objects.filter(
        business=business,
        date__year=timezone.now().year,
        date__month=timezone.now().month,
        date__day=timezone.now().day
    ).count() + 1
    return f"AUTO-{today}-{count:03d}"

def generate_sales_invoice_from_automated(automated_invoice):
    invoice_no = automated_invoice.automated_invoice_no  # Or generate a new one if needed
    invoice = Invoice.objects.create(
        business=automated_invoice.business,
        party=automated_invoice.party,
        invoice_no=invoice_no,
        date=timezone.now().date(),
        payment_term=automated_invoice.payment_terms,
        discount=automated_invoice.discount,
        total_amount=automated_invoice.get_total_amount(),
        apply_tcs=automated_invoice.apply_tcs,
        tcs=automated_invoice.tcs if automated_invoice.apply_tcs else None,
        tcs_on=automated_invoice.tcs_on,
        notes=automated_invoice.notes,
        signature=automated_invoice.signature,
    )

    for item in automated_invoice.automatedinvoice_items.all():
        InvoiceItem.objects.create(
            invoice=invoice,
            item=item.item,
            service=item.service,
            quantity=item.quantity,
            discount=item.discount,
            gstTaxRate=item.gstTaxRate,
        )

    invoice.save()
    return invoice