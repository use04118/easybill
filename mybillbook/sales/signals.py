# mybillbook/sales/signals.py

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from .models import Invoice, PaymentIn,SalesReturn,CreditNote,PaymentInInvoice
from cash_and_bank.models import BankAccount, BankTransaction

# Define your bank payment methods
BANK_PAYMENT_METHODS = ['Bank Transfer', 'Card', 'Netbanking', 'UPI', 'Cheque']

@receiver(post_save, sender=Invoice)
def sync_bank_transaction_with_invoice(sender, instance, created, **kwargs):
    """
    Ensure that the BankTransaction reflects the current state of the Invoice.
    """
    # Remove transaction if no amount received or payment method is not cash/bank
    if not instance.amount_received or float(instance.amount_received) <= 0 or (
        instance.payment_method not in ['Cash'] + BANK_PAYMENT_METHODS
    ):
        BankTransaction.objects.filter(invoice=instance).delete()
        return

    # Determine the correct account
    if instance.payment_method == "Cash":
        account = BankAccount.objects.filter(
            business=instance.business, account_type="Cash"
        ).first()
    elif instance.payment_method in BANK_PAYMENT_METHODS:
        account = instance.bank_account
    else:
        account = None

    if not account:
        BankTransaction.objects.filter(invoice=instance).delete()
        return

    # Find existing transaction
    transaction = BankTransaction.objects.filter(invoice=instance).first()

    if transaction:
        # If account or amount changed, delete old transaction and create a new one
        if transaction.account != account or float(transaction.amount) != float(instance.amount_received):
            transaction.delete()
            BankTransaction.objects.create(
                business=instance.business,
                account=account,
                transaction_type="ADD",
                amount=instance.amount_received,
                date=instance.date,
                reference=f"Sales Invoice #{instance.invoice_no}",
                notes=f"Received for Sales Invoice #{instance.invoice_no}",
                invoice=instance
            )
        else:
            # Only update reference, notes, date if needed
            updated = False
            if transaction.reference != f"Sales Invoice #{instance.invoice_no}":
                transaction.reference = f"Sales Invoice #{instance.invoice_no}"
                updated = True
            if transaction.notes != f"Received for Sales Invoice #{instance.invoice_no}":
                transaction.notes = f"Received for Sales Invoice #{instance.invoice_no}"
                updated = True
            if transaction.date != instance.date:
                transaction.date = instance.date
                updated = True
            if updated:
                transaction.save()
    else:
        # Create new transaction
        BankTransaction.objects.create(
            business=instance.business,
            account=account,
            transaction_type="ADD",
            amount=instance.amount_received,
            date=instance.date,
            reference=f"Sales Invoice #{instance.invoice_no}",
            notes=f"Received for Sales Invoice #{instance.invoice_no}",
            invoice=instance
        )


@receiver(post_save, sender=PaymentIn)
def sync_bank_transaction_with_payment_in(sender, instance, created, **kwargs):
    # Remove transaction if no amount or no payment mode
    if not instance.amount or float(instance.amount) <= 0 or not instance.payment_mode:
        BankTransaction.objects.filter(payment_in=instance).delete()
        return

    # Determine the correct account
    if instance.payment_mode == "Cash":
        account = BankAccount.objects.filter(
            business=instance.business, account_type="Cash"
        ).first()
    elif instance.payment_mode in BANK_PAYMENT_METHODS:
        account = instance.bank_account
    else:
        account = None

    if not account:
        BankTransaction.objects.filter(payment_in=instance).delete()
        return

    # Find existing transaction
    transaction = BankTransaction.objects.filter(payment_in=instance).first()

    if transaction:
        # If account or amount changed, delete old transaction and create a new one
        if transaction.account != account or float(transaction.amount) != float(instance.amount):
            transaction.delete()
            BankTransaction.objects.create(
                business=instance.business,
                account=account,
                transaction_type="ADD",
                amount=instance.amount,
                date=instance.date,
                reference=f"Payment In #{instance.payment_in_number}",
                notes=f"Received from {instance.party} (Payment In)",
                payment_in=instance
            )
        else:
            # Only update reference, notes, date if needed
            updated = False
            if transaction.reference != f"Payment In #{instance.payment_in_number}":
                transaction.reference = f"Payment In #{instance.payment_in_number}"
                updated = True
            if transaction.notes != f"Received from {instance.party} (Payment In)":
                transaction.notes = f"Received from {instance.party} (Payment In)"
                updated = True
            if transaction.date != instance.date:
                transaction.date = instance.date
                updated = True
            if updated:
                transaction.save()
    else:
        # Create new transaction
        BankTransaction.objects.create(
            business=instance.business,
            account=account,
            transaction_type="ADD",
            amount=instance.amount,
            date=instance.date,
            reference=f"Payment In #{instance.payment_in_number}",
            notes=f"Received from {instance.party} (Payment In)",
            payment_in=instance
        )

@receiver(post_save, sender=SalesReturn)
def sync_bank_transaction_with_salesreturn(sender, instance, created, **kwargs):
    """
    Ensure that the BankTransaction reflects the current state of the SalesReturn.
    """
    # Remove transaction if no amount received or payment method is not cash/bank
    if not instance.amount_received or float(instance.amount_received) <= 0 or (
        instance.payment_method not in ['Cash'] + BANK_PAYMENT_METHODS
    ):
        BankTransaction.objects.filter(sales_return=instance).delete()
        return

    # Determine the correct account
    if instance.payment_method == "Cash":
        account = BankAccount.objects.filter(
            business=instance.business, account_type="Cash"
        ).first()
    elif instance.payment_method in BANK_PAYMENT_METHODS:
        account = instance.bank_account
    else:
        account = None

    if not account:
        BankTransaction.objects.filter(sales_return=instance).delete()
        return

    # Find existing transaction
    transaction = BankTransaction.objects.filter(sales_return=instance).first()

    if transaction:
        # If account or amount changed, delete old transaction and create a new one
        if transaction.account != account or float(transaction.amount) != float(instance.amount_received):
            transaction.delete()
            BankTransaction.objects.create(
                business=instance.business,
                account=account,
                transaction_type="ADD",
                amount=instance.amount_received,
                date=instance.date,
                reference=f"Sales Return #{instance.salesreturn_no}",
                notes=f"Received for Sales Return #{instance.salesreturn_no}",
                sales_return=instance
            )
        else:
            # Only update reference, notes, date if needed
            updated = False
            if transaction.reference != f"Sales Return #{instance.salesreturn_no}":
                transaction.reference = f"Sales Return #{instance.salesreturn_no}"
                updated = True
            if transaction.notes != f"Received for Sales Return #{instance.salesreturn_no}":
                transaction.notes = f"Received for Sales Return #{instance.salesreturn_no}"
                updated = True
            if transaction.date != instance.date:
                transaction.date = instance.date
                updated = True
            if updated:
                transaction.save()
    else:
        # Create new transaction
        BankTransaction.objects.create(
            business=instance.business,
            account=account,
            transaction_type="ADD",
            amount=instance.amount_received,
            date=instance.date,
            reference=f"Sales Return #{instance.salesreturn_no}",
            notes=f"Received for Sales Return #{instance.salesreturn_no}",
            sales_return=instance
        )

@receiver(post_save, sender=CreditNote)
def sync_bank_transaction_with_creditnote(sender, instance, created, **kwargs):
    """
    Ensure that the BankTransaction reflects the current state of the CreditNote.
    """
    # Remove transaction if no amount received or payment method is not cash/bank
    if not instance.amount_received or float(instance.amount_received) <= 0 or (
        instance.payment_method not in ['Cash'] + BANK_PAYMENT_METHODS
    ):
        BankTransaction.objects.filter(credit_note=instance).delete()
        return

    # Determine the correct account
    if instance.payment_method == "Cash":
        account = BankAccount.objects.filter(
            business=instance.business, account_type="Cash"
        ).first()
    elif instance.payment_method in BANK_PAYMENT_METHODS:
        account = instance.bank_account
    else:
        account = None

    if not account:
        BankTransaction.objects.filter(credit_note=instance).delete()
        return

    # Find existing transaction
    transaction = BankTransaction.objects.filter(credit_note=instance).first()

    if transaction:
        # If account or amount changed, delete old transaction and create a new one
        if transaction.account != account or float(transaction.amount) != float(instance.amount_received):
            transaction.delete()
            BankTransaction.objects.create(
                business=instance.business,
                account=account,
                transaction_type="ADD",
                amount=instance.amount_received,
                date=instance.date,
                reference=f"Credit Note #{instance.credit_note_no}",
                notes=f"Received for Credit Note #{instance.credit_note_no}",
                credit_note=instance
            )
        else:
            # Only update reference, notes, date if needed
            updated = False
            if transaction.reference != f"Credit Note #{instance.credit_note_no}":
                transaction.reference = f"Credit Note #{instance.credit_note_no}"
                updated = True
            if transaction.notes != f"Received for Credit Note #{instance.credit_note_no}":
                transaction.notes = f"Received for Credit Note #{instance.credit_note_no}"
                updated = True
            if transaction.date != instance.date:
                transaction.date = instance.date
                updated = True
            if updated:
                transaction.save()
    else:
        # Create new transaction
        BankTransaction.objects.create(
            business=instance.business,
            account=account,
            transaction_type="ADD",
            amount=instance.amount_received,
            date=instance.date,
            reference=f"Credit Note #{instance.credit_note_no}",
            notes=f"Received for Credit Note #{instance.credit_note_no}",
            credit_note=instance
        )


from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=PaymentInInvoice)
def update_party_balance_after_invoice_settlement(sender, instance, created, **kwargs):
    payment = instance.payment_in
    settled_invoices = payment.paymentininvoice_set.all()
    
    total_settled = sum([inv.settled_amount for inv in settled_invoices])
    print("3 total settled",total_settled)
    payment.adjust_party_balance(total_settled)
