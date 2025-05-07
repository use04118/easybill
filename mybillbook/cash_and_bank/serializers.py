from rest_framework import serializers
from .models import BankAccount, BankTransaction
from django.utils import timezone
from sales.models import Invoice, PaymentIn, SalesReturn, CreditNote
from purchase.models import Purchase, PaymentOut, PurchaseReturn, DebitNote
from rest_framework.response import Response

class BankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = '__all__'
        read_only_fields = ['business','current_balance']

    def validate(self, data):
        if data.get('account_type') == 'Bank':
            if not data.get('bank_account_number'):
                raise serializers.ValidationError("Bank account number is required for bank accounts")
            if not data.get('ifsc_code'):
                raise serializers.ValidationError("IFSC code is required for bank accounts")
        return data

class BankTransactionSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.account_name', read_only=True)
    account_type = serializers.CharField(source='account.account_type', read_only=True)
    invoice_no = serializers.CharField(source='invoice.invoice_no', read_only=True)
    payment_in_no = serializers.CharField(source='payment_in.payment_in_number', read_only=True)
    sales_return_no = serializers.CharField(source='sales_return.salesreturn_no', read_only=True)
    credit_note_no = serializers.CharField(source='credit_note.credit_note_no', read_only=True)
    purchase_no = serializers.CharField(source='purchase.purchase_no', read_only=True)
    payment_out_no = serializers.CharField(source='payment_out.payment_out_number', read_only=True)
    purchase_return_no = serializers.CharField(source='purchase_return.purchase_return_no', read_only=True)
    debit_note_no = serializers.CharField(source='debit_note.debit_note_no', read_only=True)
    txnNo = serializers.SerializerMethodField()
    party = serializers.SerializerMethodField()
    mode = serializers.SerializerMethodField()
    paid = serializers.SerializerMethodField()
    received = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()

    class Meta:
        model = BankTransaction
        fields = [
            'id', 'business', 'account', 'transaction_type', 'amount', 'date', 'reference', 'notes',
            'invoice', 'payment_in', 'sales_return', 'credit_note',
            'purchase', 'payment_out', 'purchase_return', 'debit_note',
            'created_at', 'updated_at',
            'account_name', 'account_type',
            'invoice_no', 'payment_in_no', 'sales_return_no', 'credit_note_no',
            'purchase_no', 'payment_out_no', 'purchase_return_no', 'debit_note_no',
            'txnNo', 'party', 'mode', 'paid', 'received', 'balance'
        ]
        read_only_fields = ['business']

    def validate(self, data):
        # Validate transaction date is not in future
        if data.get('date') and data['date'] > timezone.now().date():
            raise serializers.ValidationError("Transaction date cannot be in the future")

        # Validate amount is positive
        if data.get('amount') and data['amount'] <= 0:
            raise serializers.ValidationError("Amount must be greater than zero")

        # Validate reference for transfer transactions
        if data.get('transaction_type') in ['TRANSFER_IN', 'TRANSFER_OUT'] and not data.get('reference'):
            raise serializers.ValidationError("Reference is required for transfer transactions")

        return data

    def validate_account(self, value):
        # Ensure account belongs to user's business
        business = getattr(self.context['request'].user, 'current_business', None)
        if not business:
            raise Response({'error': 'No current business selected for user.'}, status=400)
        if value.business != business:
            raise serializers.ValidationError("Account does not belong to your business")
        return value

    def validate_related_transaction(self, value, transaction_type):
        business = getattr(self.context['request'].user, 'current_business', None)
        if not business:
            raise Response({'error': 'No current business selected for user.'}, status=400)
        if value and value.business != business:
            raise serializers.ValidationError(f"{transaction_type} does not belong to your business")
        return value

    def validate_invoice(self, value):
        return self.validate_related_transaction(value, 'Invoice')

    def validate_payment_in(self, value):
        return self.validate_related_transaction(value, 'PaymentIn')

    def validate_sales_return(self, value):
        return self.validate_related_transaction(value, 'SalesReturn')

    def validate_credit_note(self, value):
        return self.validate_related_transaction(value, 'CreditNote')

    def validate_purchase(self, value):
        return self.validate_related_transaction(value, 'Purchase')

    def validate_payment_out(self, value):
        return self.validate_related_transaction(value, 'PaymentOut')

    def validate_purchase_return(self, value):
        return self.validate_related_transaction(value, 'PurchaseReturn')

    def validate_debit_note(self, value):
        return self.validate_related_transaction(value, 'DebitNote')

    def get_txnNo(self, obj):
        return obj.reference or str(obj.id)

    def get_party(self, obj):
        related = obj.get_related_transaction()
        if related and hasattr(related, 'party'):
            return getattr(related.party, 'name', None)
        return None

    def get_mode(self, obj):
        return obj.account.account_type

    def get_paid(self, obj):
        return float(obj.amount) if obj.is_debit else None

    def get_received(self, obj):
        return float(obj.amount) if obj.is_credit else None

    def get_balance(self, obj):
        """Calculate running balance up to this transaction"""
        # Get all transactions for this account up to this transaction's date and created_at
        transactions = BankTransaction.objects.filter(
            account=obj.account,
            date__lte=obj.date,
            created_at__lte=obj.created_at
        ).order_by('date', 'created_at')
        
        running_balance = obj.account.opening_balance
        for txn in transactions:
            if txn.transaction_type in ['ADD', 'TRANSFER_IN', 'PAYMENT_IN', 'PURCHASE_RETURN', 'CREDIT_NOTE']:
                running_balance += txn.amount
            elif txn.transaction_type in ['REDUCE', 'TRANSFER_OUT', 'PAYMENT_OUT', 'SALES_RETURN', 'DEBIT_NOTE']:
                running_balance -= txn.amount
            
            if txn.id == obj.id:  # Stop when we reach the current transaction
                break
                
        return float(running_balance)
