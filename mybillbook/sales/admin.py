from django.contrib import admin
#added manually
from .models import Invoice, Quotation,PaymentIn,PaymentInInvoice, SalesReturn, CreditNote, DeliveryChallan, Proforma, InvoiceItem, QuotationItem,SalesReturnItem, DeliveryChallanItem, CreditNoteItem, ProformaItem

# Register your models here.

admin.site.register(Invoice)
admin.site.register(Quotation)
admin.site.register(PaymentIn)
admin.site.register(PaymentInInvoice)
admin.site.register(SalesReturn)
admin.site.register(CreditNote)
admin.site.register(DeliveryChallan)
admin.site.register(Proforma)
admin.site.register(InvoiceItem)
admin.site.register(QuotationItem)
admin.site.register(DeliveryChallanItem)
admin.site.register(SalesReturnItem)
admin.site.register(CreditNoteItem)
admin.site.register(ProformaItem)