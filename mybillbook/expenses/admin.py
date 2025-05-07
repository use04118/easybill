from django.contrib import admin

# Register your models here.
from .models import Expense,Item

admin.site.register(Expense)
admin.site.register(Item)