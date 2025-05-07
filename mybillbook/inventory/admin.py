from django.contrib import admin
from .models import Item, ItemCategory, MeasuringUnit, GSTTaxRate, Service

admin.site.register(Item)
admin.site.register(ItemCategory)
admin.site.register(MeasuringUnit)
admin.site.register(GSTTaxRate)
admin.site.register(Service)
