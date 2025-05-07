from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from .models import AuditTrail
from users.utils import get_current_business
from sales.models import Tcs, Tds
from django.utils import timezone

def get_voucher_no(instance):
    """Get the voucher number based on the model type"""
    # First check the model name to determine which field to use
    model_name = instance.__class__.__name__
    
    if model_name == 'SalesReturn':
        return instance.salesreturn_no
    elif model_name == 'PurchaseReturn':
        return instance.purchasereturn_no
    elif model_name == 'CreditNote':
        return instance.credit_note_no
    elif model_name == 'DebitNote':
        return instance.debitnote_no
    elif model_name == 'PaymentIn':
        return instance.payment_in_number
    elif model_name == 'PaymentOut':
        return instance.payment_out_number
    elif model_name == 'Invoice':
        return instance.invoice_no
    elif model_name == 'Purchase':
        return instance.purchase_no
    elif model_name == 'Quotation':
        return instance.quotation_no
    elif model_name == 'Proforma':
        return instance.proforma_no
    elif model_name == 'DeliveryChallan':
        return instance.delivery_challan_no
    elif model_name == 'PurchaseOrder':
        return instance.purchase_order_no
    
    # Fallback to checking individual fields if model name doesn't match
    if hasattr(instance, 'invoice_no'):
        return instance.invoice_no
    elif hasattr(instance, 'purchase_no'):
        return instance.purchase_no
    elif hasattr(instance, 'payment_in_number'):
        return instance.payment_in_number
    elif hasattr(instance, 'payment_out_number'):
        return instance.payment_out_number
    elif hasattr(instance, 'salesreturn_no'):
        return instance.salesreturn_no
    elif hasattr(instance, 'purchasereturn_no'):
        return instance.purchasereturn_no
    elif hasattr(instance, 'credit_note_no'):
        return instance.credit_note_no
    elif hasattr(instance, 'debit_note_no'):
        return instance.debit_note_no
    
    return str(instance.id)

@receiver(post_save)
def track_model_changes(sender, instance, created, **kwargs):
    """Track changes to models for audit trail"""
    # Skip if it's the AuditTrail model itself or User model
    if sender == AuditTrail or sender.__name__ == 'User':
        return
    
    # Skip if the model doesn't have a business field
    if not hasattr(instance, 'business'):
        return
    
    # Get the business
    business = instance.business
    
    # Get the model name
    model_name = sender.__name__
    
    print("instance -- ", instance)
    # Get the voucher number
    voucher_no = get_voucher_no(instance)
    
    # Create audit trail entry
    if created:
        action = f"Created {model_name}"
        old_values = None
        new_values = {k: str(v) for k, v in instance.__dict__.items() if not k.startswith('_')}
    else:
        action = f"Updated {model_name}"
        # Get the old values from the database
        old_instance = sender.objects.get(pk=instance.pk)
        old_values = {k: str(v) for k, v in old_instance.__dict__.items() if not k.startswith('_')}
        new_values = {k: str(v) for k, v in instance.__dict__.items() if not k.startswith('_')}
    
    if business is None:
        return
    
    AuditTrail.objects.create(
        business=business,
        user=getattr(instance, '_current_user', None),  # Get the user from the instance if set
        voucher_no=voucher_no,
        action=action,
        model_name=model_name,
        record_id=instance.id,
        old_values=old_values,
        new_values=new_values
    )

@receiver(post_delete)
def track_model_deletion(sender, instance, **kwargs):
    """Track model deletions for audit trail"""
    # Skip if it's the AuditTrail model itself
    if sender == AuditTrail:
        return
    
    # Skip if the model doesn't have a business field
    if not hasattr(instance, 'business'):
        return
    
    # Get the business
    business = instance.business
    
    # Get the model name
    model_name = sender.__name__
    print("instance -- ", instance)
    # Get the voucher number
    voucher_no = get_voucher_no(instance)
    
    # Create audit trail entry
    if business is None:
        return
    
    AuditTrail.objects.create(
        business=business,
        user=getattr(instance, '_current_user', None),  # Get the user from the instance if set
        voucher_no=voucher_no,
        action=f"Deleted {model_name}",
        model_name=model_name,
        record_id=instance.id,
        old_values={k: str(v) for k, v in instance.__dict__.items() if not k.startswith('_')},
        new_values=None
    )

@receiver(post_save, sender=Tcs)
def log_tcs_creation(sender, instance, created, **kwargs):
    if not created:
        return
    # SKIP if business is None
    if instance.business is None:
        return
    AuditTrail.objects.create(
        business=instance.business,
        user=getattr(instance, 'created_by', None),  # or however you track user
        action='Created TCS',
        model_name='Tcs',
        object_id=instance.id,
        object_repr=str(instance),
        changes=f"Created TCS: {instance.description}, Rate: {instance.rate}",
        timestamp=timezone.now()
    )

@receiver(post_save, sender=Tds)
def log_tds_creation(sender, instance, created, **kwargs):
    if not created:
        return
    # SKIP if business is None
    if instance.business is None:
        return
    
    AuditTrail.objects.create(
        business=instance.business,
        user=getattr(instance, 'created_by', None),  # or however you track user
        action='Created TDS',
        model_name='Tds',
        object_id=instance.id,
        object_repr=str(instance),
        changes=f"Created TDS: {instance.description}, Rate: {instance.rate}",
        timestamp=timezone.now()
    )