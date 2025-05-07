from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import date, timedelta
from .models import BankAccount, BankTransaction
from .serializers import BankAccountSerializer, BankTransactionSerializer
from sales.models import Invoice, PaymentIn, SalesReturn, CreditNote
from purchase.models import Purchase, PaymentOut, PurchaseReturn, DebitNote
from rest_framework.decorators import api_view, permission_classes
from users.models import Business
from rest_framework.permissions import IsAuthenticated

class BankAccountListCreateView(generics.ListCreateAPIView):
    serializer_class = BankAccountSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = BankAccount.objects.filter(business=self.request.user.current_business)
        
        # Filter by account type
        account_type = self.request.query_params.get('account_type')
        if account_type:
            queryset = queryset.filter(account_type=account_type)
            
        # Search by account name
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(account_name__icontains=search)
            
        return queryset

    def perform_create(self, serializer):
        serializer.save(business=self.request.user.current_business)

class BankAccountDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BankAccountSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return BankAccount.objects.filter(business=self.request.user.current_business)

class BankTransactionListCreateView(generics.ListCreateAPIView):
    serializer_class = BankTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        business = getattr(self.request.user, 'current_business', None)
        if not business:
            return BankTransaction.objects.none()
        queryset = BankTransaction.objects.filter(business=business)
        
        # Filter by account
        account_id = self.request.query_params.get('account_id')
        if account_id:
            queryset = queryset.filter(account_id=account_id)
            
        # Filter by transaction type
        transaction_type = self.request.query_params.get('transaction_type')
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
            
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(date__range=[start_date, end_date])
            
        # Search by reference or notes
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(reference__icontains=search) | 
                Q(notes__icontains=search)
            )
            
        # Filter by related transactions
        for model in [Invoice, PaymentIn, SalesReturn, CreditNote, Purchase, PaymentOut, PurchaseReturn, DebitNote]:
            model_name = model.__name__.lower()
            id_param = f"{model_name}_id"
            if id_param in self.request.query_params:
                queryset = queryset.filter(**{model_name: self.request.query_params[id_param]})
                
        return queryset

    def create(self, request, *args, **kwargs):
        data = request.data
        user = request.user
        business = getattr(user, 'current_business', None)
        if not business:
            return Response({'error': 'No current business selected for user.'}, status=400)

        # Add/Reduce Money
        if 'type' in data and 'money_type' in data:
            money_type = data['money_type']
            txn_type = data['type']
            account_id = data.get('account_id')
            if account_id:
                account = BankAccount.objects.filter(business=business, id=account_id).first()
            else:
                account = BankAccount.objects.filter(business=business, account_type=money_type).first()
            if not account:
                return Response({'error': f'{money_type} account not found'}, status=400)
            transaction_type = 'ADD' if txn_type == 'add' else 'REDUCE'
            serializer = self.get_serializer(data={
                "business": business.id,
                "account": account.id,
                "transaction_type": transaction_type,
                "amount": data['amount'],
                "date": data['date'],
                "notes": data.get('remarks', '')
            })
            serializer.is_valid(raise_exception=True)
            serializer.save(business=business)
            return Response(serializer.data, status=201)

        # Transfer Money
        if 'from' in data and 'to' in data:
            from_type = data['from'].capitalize()
            to_type = data['to'].capitalize()
            from_account_id = data.get('from_account_id')
            to_account_id = data.get('to_account_id')

            if from_account_id:
                from_account = BankAccount.objects.filter(business=business, id=from_account_id).first()
            else:
                from_account = BankAccount.objects.filter(business=business, account_type=from_type).first()

            if to_account_id:
                to_account = BankAccount.objects.filter(business=business, id=to_account_id).first()
            else:
                to_account = BankAccount.objects.filter(business=business, account_type=to_type).first()

            if not from_account or not to_account:
                return Response({'error': 'Account not found'}, status=400)
            amount = data['amount']
            date_val = data['date']
            remarks = data.get('remarks', '')
            # Transfer out
            BankTransaction.objects.create(
                business=business, account=from_account, transaction_type='TRANSFER_OUT',
                amount=amount, date=date_val, notes=remarks
            )
            # Transfer in
            BankTransaction.objects.create(
                business=business, account=to_account, transaction_type='TRANSFER_IN',
                amount=amount, date=date_val, notes=remarks
            )
            return Response({'message': 'Transfer successful'}, status=201)

        return super().create(request, *args, **kwargs)

class BankTransactionDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BankTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        business = getattr(self.request.user, 'current_business', None)
        if not business:
            return BankTransaction.objects.none()
        return BankTransaction.objects.filter(business=business)

class BankAccountBalanceView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            account = BankAccount.objects.get(pk=pk, business=request.user.current_business)
            return Response({
                'account_id': account.id,
                'account_name': account.account_name,
                'current_balance': account.current_balance,
                'as_of_date': account.as_of_date
            })
        except BankAccount.DoesNotExist:
            return Response({'error': 'Account not found'}, status=status.HTTP_404_NOT_FOUND)

class BankTransferView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from_account_id = request.data.get('from_account')
        to_account_id = request.data.get('to_account')
        amount = request.data.get('amount')
        reference = request.data.get('reference')
        notes = request.data.get('notes')

        try:
            from_account = BankAccount.objects.get(id=from_account_id, business=request.user.current_business)
            to_account = BankAccount.objects.get(id=to_account_id, business=request.user.current_business)
        except BankAccount.DoesNotExist:
            return Response({'error': 'Invalid account'}, status=status.HTTP_400_BAD_REQUEST)

        if from_account.current_balance < amount:
            return Response({'error': 'Insufficient balance'}, status=status.HTTP_400_BAD_REQUEST)

        # Create transfer out transaction
        transfer_out = BankTransaction.objects.create(
            business=request.user.current_business,
            account=from_account,
            transaction_type='TRANSFER_OUT',
            amount=amount,
            date=date.today(),
            reference=reference,
            notes=notes
        )

        # Create transfer in transaction
        transfer_in = BankTransaction.objects.create(
            business=request.user.current_business,
            account=to_account,
            transaction_type='TRANSFER_IN',
            amount=amount,
            date=date.today(),
            reference=reference,
            notes=notes
        )

        return Response({
            'transfer_out': BankTransactionSerializer(transfer_out).data,
            'transfer_in': BankTransactionSerializer(transfer_in).data
        })

class BankTransactionSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        account_id = request.query_params.get('account_id')

        if not start_date or not end_date:
            return Response({'error': 'Start date and end date are required'}, 
                          status=status.HTTP_400_BAD_REQUEST)

        business = getattr(request.user, 'current_business', None)
        if not business:
            return Response({'error': 'No current business selected for user.'}, status=400)

        queryset = BankTransaction.objects.filter(
            business=business,
            date__range=[start_date, end_date]
        )

        if account_id:
            queryset = queryset.filter(account_id=account_id)

        # Calculate totals
        total_credit = queryset.filter(
            transaction_type__in=['ADD', 'TRANSFER_IN', 'PAYMENT_IN', 'PURCHASE_RETURN', 'CREDIT_NOTE']
        ).aggregate(total=Sum('amount'))['total'] or 0

        total_debit = queryset.filter(
            transaction_type__in=['REDUCE', 'TRANSFER_OUT', 'PAYMENT_OUT', 'SALES_RETURN', 'DEBIT_NOTE']
        ).aggregate(total=Sum('amount'))['total'] or 0

        # Group by transaction type
        transaction_types = queryset.values('transaction_type').annotate(
            total=Sum('amount')
        ).order_by('transaction_type')

        return Response({
            'total_credit': total_credit,
            'total_debit': total_debit,
            'net_balance': total_credit - total_debit,
            'transaction_types': list(transaction_types)
        })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cash_bank_dashboard(request):
    user = request.user
    business = getattr(user, 'current_business', None)
    if not business:
        return Response({'error': 'No current business selected for user.'}, status=400)

    accounts = BankAccount.objects.filter(business=business)
    cash_account = accounts.filter(account_type='Cash').first()
    bank_accounts = accounts.filter(account_type='Bank')

    # Calculate total balance from accounts
    total_balance = sum(a.current_balance for a in accounts)
    cash = cash_account.current_balance if cash_account else 0

    # Get transactions ordered by date and created_at
    transactions = BankTransaction.objects.filter(
        business=business
    ).order_by('-date', '-created_at')

    if request.query_params.get('start_date') and request.query_params.get('end_date'):
        transactions = transactions.filter(
            date__range=[
                request.query_params['start_date'],
                request.query_params['end_date']
            ]
        )

    serializer = BankTransactionSerializer(transactions, many=True)

    return Response({
        "total_balance": float(total_balance),
        "cash": float(cash),
        "bank_accounts": [
            {
                "id": b.id,
                "name": b.account_name,
                "balance": float(b.current_balance)
            }
            for b in bank_accounts
        ],
        "unlinked_transactions": float(
            BankTransaction.objects.filter(
                business=business,
                account__isnull=True
            ).aggregate(total=Sum('amount'))['total'] or 0
        ),
        "transactions": serializer.data
    })
