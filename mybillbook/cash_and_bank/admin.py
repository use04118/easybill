from django.contrib import admin

# Register your models here.
from .models import BankAccount,BankTransaction

admin.site.register(BankTransaction)
admin.site.register(BankAccount)