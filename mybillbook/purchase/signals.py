# mybillbook/sales/signals.py

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from .models import Purchase, PaymentOut,PurchaseReturn,DebitNote
from cash_and_bank.models import BankAccount, BankTransaction

# Define your bank payment methods
BANK_PAYMENT_METHODS = ['Bank Transfer', 'Card', 'Netbanking', 'UPI', 'Cheque']

@receiver(post_save, sender=Purchase)
def sync_bank_transaction_with_purchase(sender, instance, created, **kwargs):
    """
    Ensure that the BankTransaction reflects the current state of the Purchase.
    """
    # Remove transaction if no amount received or payment method is not cash/bank
    if not instance.amount_received or float(instance.amount_received) <= 0 or (
        instance.payment_method not in ['Cash'] + BANK_PAYMENT_METHODS
    ):
        BankTransaction.objects.filter(purchase=instance).delete()
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
        BankTransaction.objects.filter(purchase=instance).delete()
        return

    # Find existing transaction
    transaction = BankTransaction.objects.filter(purchase=instance).first()

    if transaction:
        # If account or amount changed, delete old transaction and create a new one
        if transaction.account != account or float(transaction.amount) != float(instance.amount_received):
            transaction.delete()
            BankTransaction.objects.create(
                business=instance.business,
                account=account,
                transaction_type="REDUCE",
                amount=instance.amount_received,
                date=instance.date,
                reference=f"Purchase #{instance.purchase_no}",
                notes=f"Received for Purchase #{instance.purchase_no}",
                purchase=instance
            )
        else:
            # Only update reference, notes, date if needed
            updated = False
            if transaction.reference != f"Purchase #{instance.purchase_no}":
                transaction.reference = f"Purchase #{instance.purchase_no}"
                updated = True
            if transaction.notes != f"Received for Purchase #{instance.purchase_no}":
                transaction.notes = f"Received for Purchase #{instance.purchase_no}"
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
            transaction_type="REDUCE",
            amount=instance.amount_received,
            date=instance.date,
            reference=f"Purchase #{instance.purchase_no}",
            notes=f"Received for Purchase #{instance.purchase_no}",
            purchase=instance
        )


@receiver(post_save, sender=PaymentOut)
def sync_bank_transaction_with_payment_out(sender, instance, created, **kwargs):
    # Remove transaction if no amount or no payment mode
    if not instance.amount or float(instance.amount) <= 0 or not instance.payment_mode:
        BankTransaction.objects.filter(payment_out=instance).delete()
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
        BankTransaction.objects.filter(payment_out=instance).delete()
        return

    # Find existing transaction
    transaction = BankTransaction.objects.filter(payment_out=instance).first()

    if transaction:
        # If account or amount changed, delete old transaction and create a new one
        if transaction.account != account or float(transaction.amount) != float(instance.amount):
            transaction.delete()
            BankTransaction.objects.create(
                business=instance.business,
                account=account,
                transaction_type="REDUCE",
                amount=instance.amount,
                date=instance.date,
                reference=f"Payment Out #{instance.payment_out_number}",
                notes=f"Received from {instance.party} (Payment Out)",
                payment_out=instance
            )
        else:
            # Only update reference, notes, date if needed
            updated = False
            if transaction.reference != f"Payment Out #{instance.payment_out_number}":
                transaction.reference = f"Payment Out #{instance.payment_out_number}"
                updated = True
            if transaction.notes != f"Received from {instance.party} (Payment Out)":
                transaction.notes = f"Received from {instance.party} (Payment Out)"
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
            transaction_type="REDUCE",
            amount=instance.amount,
            date=instance.date,
            reference=f"Payment Out #{instance.payment_out_number}",
            notes=f"Received from {instance.party} (Payment Out)",
            payment_out=instance
        )

@receiver(post_save, sender=PurchaseReturn)
def sync_bank_transaction_with_purchasereturn(sender, instance, created, **kwargs):
    """
    Ensure that the BankTransaction reflects the current state of the PurchaseReturn.
    """
    # Remove transaction if no amount received or payment method is not cash/bank
    if not instance.amount_received or float(instance.amount_received) <= 0 or (
        instance.payment_method not in ['Cash'] + BANK_PAYMENT_METHODS
    ):
        BankTransaction.objects.filter(purchase_return=instance).delete()
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
        BankTransaction.objects.filter(purchase_return=instance).delete()
        return

    # Find existing transaction
    transaction = BankTransaction.objects.filter(purchase_return=instance).first()

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
                reference=f"Purchase Return #{instance.purchasereturn_no}",
                notes=f"Received for Purchase Return #{instance.purchasereturn_no}",
                purchase_return=instance
            )
        else:
            # Only update reference, notes, date if needed
            updated = False
            if transaction.reference != f"Purchase Return #{instance.purchasereturn_no}":
                transaction.reference = f"Purchase Return #{instance.purchasereturn_no}"
                updated = True
            if transaction.notes != f"Received for Purchase Return #{instance.purchasereturn_no}":
                transaction.notes = f"Received for Purchase Return #{instance.purchasereturn_no}"
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
            reference=f"Purchase Return #{instance.purchasereturn_no}",
            notes=f"Received for Purchase Return #{instance.purchasereturn_no}",
            purchase_return=instance
        )

@receiver(post_save, sender=DebitNote)
def sync_bank_transaction_with_debitnote(sender, instance, created, **kwargs):
    """
    Ensure that the BankTransaction reflects the current state of the DebitNote.
    """
    # Remove transaction if no amount received or payment method is not cash/bank
    if not instance.amount_received or float(instance.amount_received) <= 0 or (
        instance.payment_method not in ['Cash'] + BANK_PAYMENT_METHODS
    ):
        BankTransaction.objects.filter(debit_note=instance).delete()
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
        BankTransaction.objects.filter(debit_note=instance).delete()
        return

    # Find existing transaction
    transaction = BankTransaction.objects.filter(debit_note=instance).first()

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
                reference=f"Debit Note #{instance.debitnote_no}",
                notes=f"Received for Debit Note #{instance.debitnote_no}",
                debit_note=instance
            )
        else:
            # Only update reference, notes, date if needed
            updated = False
            if transaction.reference != f"Debit Note #{instance.debitnote_no}":
                transaction.reference = f"Debit Note #{instance.debitnote_no}"
                updated = True
            if transaction.notes != f"Received for Debit Note #{instance.debitnote_no}":
                transaction.notes = f"Received for Debit Note #{instance.debitnote_no}"
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
            reference=f"Debit Note #{instance.debitnote_no}",
            notes=f"Received for Debit Note #{instance.debitnote_no}",
            debit_note=instance
        )
