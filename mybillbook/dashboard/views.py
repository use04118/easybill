from django.http import JsonResponse
from django.db.models import Value, CharField,F, Sum, Count, Q
from sales.models import Invoice, Quotation, SalesReturn, CreditNote, PaymentIn, DeliveryChallan,Proforma
from purchase.models import Purchase, PurchaseReturn, DebitNote, PaymentOut, PurchaseOrder
import reports.models as reports
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.db.models import DecimalField
from decimal import Decimal
from django.utils.dateparse import parse_date
from users.utils import get_current_business
from expenses.models import Expense
from parties.models import Party
from sales.models import Invoice
from purchase.models import Purchase
from datetime import datetime, timedelta
from django.utils import timezone

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_data(request):
    # Fetch sales-related transactions
    sales_data = list(Invoice.objects.annotate(
        tid=F('id'),
        transaction_no=F('invoice_no'),
        type=Value('Invoice', output_field=CharField()),
        party_name=F('party__party_name'),  # Correctly fetching related party name
        amount=F('total_amount')  # Correctly fetching related party name
    ).values('tid','date', 'transaction_no', 'type', 'party_name','amount'))
    
    sales_data += list(Quotation.objects.annotate(
        tid=F('id'),
        transaction_no=F('quotation_no'),
        type=Value('Quotation', output_field=CharField()),
        party_name=F('party__party_name'),  # Correctly fetching related party name
        amount=F('total_amount')  # Correctly fetching related party name
    ).values('tid','date', 'transaction_no', 'type', 'party_name','amount'))

    sales_data += list(SalesReturn.objects.annotate(
        tid=F('id'),
        transaction_no=F('salesreturn_no'),
        type=Value('SalesReturn', output_field=CharField()),
        party_name=F('party__party_name'),  # Correctly fetching related party name
        amount=F('total_amount')  # Correctly fetching related party name
    ).values('tid','date', 'transaction_no', 'type', 'party_name','amount'))

    sales_data += list(PaymentIn.objects.annotate(
        tid=F('id'),
        transaction_no=F('payment_in_number'),
        type=Value('PaymentIn', output_field=CharField()),
        party_name=F('party__party_name'),  # Correctly fetching related party name
        # payment_amount=F('amount')  # Correctly fetching related party name
    ).values('tid','date', 'transaction_no', 'type', 'party_name','amount'))

    sales_data += list(DeliveryChallan.objects.annotate(
        tid=F('id'),
        transaction_no=F('delivery_challan_no'),
        type=Value('DeliveryChallan', output_field=CharField()),
        party_name=F('party__party_name'),  # Correctly fetching related party name
        amount=F('total_amount')  # Correctly fetching related party name
    ).values('tid','date', 'transaction_no', 'type', 'party_name','amount'))

    sales_data += list(CreditNote.objects.annotate(
        tid=F('id'),
        transaction_no=F('credit_note_no'),
        type=Value('CreditNote', output_field=CharField()),
        party_name=F('party__party_name'),  # Correctly fetching related party name
        amount=F('total_amount')  # Correctly fetching related party name
    ).values('tid','date', 'transaction_no', 'type', 'party_name','amount'))

    sales_data += list(Proforma.objects.annotate(
        tid=F('id'),
        transaction_no=F('proforma_no'),
        type=Value('Proforma', output_field=CharField()),
        party_name=F('party__party_name'),  # Correctly fetching related party name
        amount=F('total_amount')  # Correctly fetching related party name
    ).values('tid','date', 'transaction_no', 'type', 'party_name','amount'))
    
    # Fetch purchase-related transactions
    purchase_data = list(Purchase.objects.annotate(
        tid=F('id'),
        transaction_no=F('purchase_no'),
        type=Value('Purchase', output_field=CharField()),
        party_name=F('party__party_name'),  # Correctly fetching related party name
        amount=F('total_amount')  # Correctly fetching related party name
    ).values('tid','date', 'transaction_no', 'type', 'party_name','amount'))  # No annotation needed

    purchase_data += list(PurchaseReturn.objects.annotate(
        tid=F('id'),
        transaction_no=F('purchasereturn_no'),
        type=Value('PurchaseReturn', output_field=CharField()),
        party_name=F('party__party_name'),  # Correctly fetching related party name
        amount=F('total_amount')  # Correctly fetching related party name
    ).values('tid','date', 'transaction_no', 'type', 'party_name','amount'))

    
    purchase_data += list(DebitNote.objects.annotate(
        tid=F('id'),
        transaction_no=F('debitnote_no'),
        type=Value('DebitNote', output_field=CharField()),
        party_name=F('party__party_name'),  # Correctly fetching related party name
        amount=F('total_amount')  # Correctly fetching related party name
    ).values('tid','date', 'transaction_no', 'type', 'party_name','amount'))

    
    purchase_data += list(PaymentOut.objects.annotate(
        tid=F('id'),
        transaction_no=F('payment_out_number'),
        type=Value('PaymentOut', output_field=CharField()),
        party_name=F('party__party_name'),  # Correctly fetching related party name
        # payment_amount=F('amount')  # Correctly fetching related party name
    ).values('tid','date', 'transaction_no', 'type', 'party_name','amount'))

    purchase_data += list(PurchaseOrder.objects.annotate(
        tid=F('id'),
        transaction_no=F('purchase_order_no'),
        type=Value('PurchaseOrder', output_field=CharField()),
        party_name=F('party__party_name'),  # Correctly fetching related party name
        amount=F('total_amount')  # Correctly fetching related party name
    ).values('tid','date', 'transaction_no', 'type', 'party_name','amount'))

    
    for data in purchase_data:
        data['date'] = data.pop('date', None)

    # Merge and sort by date (newest first)
    transactions = sorted(sales_data +  purchase_data  , key=lambda x: x['date']or "", reverse=True)

    return JsonResponse({'transactions': transactions}, safe=False)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_profit(request):
    business = get_current_business(request.user)  # If you use business context

    # Get start and end dates from query parameters (if provided)
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if start_date:
        start_date = parse_date(start_date)
    if end_date:
        end_date = parse_date(end_date)

    # 1. Sales (+)
    invoice_qs = Invoice.objects.filter(business=business)
    if start_date:
        invoice_qs = invoice_qs.filter(date__gte=start_date)
    if end_date:
        invoice_qs = invoice_qs.filter(date__lte=end_date)
    total_sales = invoice_qs.aggregate(total=Sum('total_amount'))['total'] or Decimal(0)

    # 2. Credit Notes (-)
    credit_qs = CreditNote.objects.filter(business=business)
    if start_date:
        credit_qs = credit_qs.filter(date__gte=start_date)
    if end_date:
        credit_qs = credit_qs.filter(date__lte=end_date)
    total_credit_notes = credit_qs.aggregate(total=Sum('total_amount'))['total'] or Decimal(0)

    # 3. Purchases (+)
    purchase_qs = Purchase.objects.filter(business=business)
    if start_date:
        purchase_qs = purchase_qs.filter(date__gte=start_date)
    if end_date:
        purchase_qs = purchase_qs.filter(date__lte=end_date)
    total_purchases = purchase_qs.aggregate(total=Sum('total_amount'))['total'] or Decimal(0)

    # 4. Debit Notes (-)
    debit_qs = DebitNote.objects.filter(business=business)
    if start_date:
        debit_qs = debit_qs.filter(date__gte=start_date)
    if end_date:
        debit_qs = debit_qs.filter(date__lte=end_date)
    total_debit_notes = debit_qs.aggregate(total=Sum('total_amount'))['total'] or Decimal(0)

    # 5. Gross Profit
    cogs = total_purchases - total_debit_notes
    gross_profit = total_sales - cogs

    return JsonResponse({
        'total_sales': round(total_sales, 2),
        'total_credit_notes': round(total_credit_notes, 2),
        'total_purchases': round(total_purchases, 2),
        'total_debit_notes': round(total_debit_notes, 2),
        'gross_profit': round(gross_profit, 2),
    }, safe=False)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def summary_counts(request):
    business = get_current_business(request.user)
    period = request.GET.get('period', 'yearly')  # default to yearly

    now = timezone.now()
    if period == 'monthly':
        start_date = now.replace(day=1)
    elif period == 'weekly':
        start_date = now - timedelta(days=now.weekday())  # Monday of this week
    else:  # yearly
        start_date = now.replace(month=1, day=1)

    # Filter by business and date
    sales = Invoice.objects.filter(business=business, date__gte=start_date).count()
    purchase = Purchase.objects.filter(business=business, date__gte=start_date).count()
    expenses = Expense.objects.filter(business=business, date__gte=start_date).count()
    parties = Party.objects.filter(business=business, created_at__gte=start_date).count()  # Assuming Party has created_at

    return JsonResponse({
        'sales': sales,
        'purchase': purchase,
        'expenses': expenses,
        'parties': parties,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def top_parties_combined(request):
    business = get_current_business(request.user)
    period = request.GET.get('period', 'yearly')
    now = timezone.now()

    if period == 'monthly':
        start_date = now.replace(day=1)
    elif period == 'weekly':
        start_date = now - timedelta(days=now.weekday())
    else:  # yearly
        start_date = now.replace(month=1, day=1)

    # Get all parties with their sales and purchase stats
    

    parties = (
        Party.objects.filter(business=business)
        .annotate(
            total_sales=Count('invoice', filter=Q(invoice__date__gte=start_date)),
            total_revenue=Sum('invoice__total_amount', filter=Q(invoice__date__gte=start_date)),
            total_purchases=Count('purchase', filter=Q(purchase__date__gte=start_date)),
            total_purchase_amount=Sum('purchase__total_amount', filter=Q(purchase__date__gte=start_date)),
        )
        .order_by('-total_revenue')[:5]
    )

    data = []
    for party in parties:
        data.append({
            'id': party.id,
            'name': party.party_name,
            'total_sales': party.total_sales or 0,
            'total_revenue': float(party.total_revenue or 0),
            'total_purchases': party.total_purchases or 0,
            'total_purchase_amount': float(party.total_purchase_amount or 0),
        })

    return JsonResponse({'parties': data})


