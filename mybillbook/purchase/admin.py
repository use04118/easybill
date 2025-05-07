from django.contrib import admin
#added manually
from .models import Purchase, PaymentOut, PurchaseReturn, DebitNote,PurchaseOrder, PurchaseItem, PurchaseReturnItem, DebitNoteItem

# Register your models here.
admin.site.register(Purchase)
admin.site.register(PurchaseItem)
admin.site.register(PaymentOut)
admin.site.register(PurchaseReturn)
admin.site.register(PurchaseReturnItem)
admin.site.register(DebitNote)
admin.site.register(DebitNoteItem)
admin.site.register(PurchaseOrder)