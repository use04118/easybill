from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Value, CharField,F,Sum, Case, When, IntegerField,DecimalField,Max
from sales.models import InvoiceItem, Quotation, SalesReturnItem, CreditNoteItem, PaymentIn, Invoice,SalesReturn, CreditNote,Proforma, DeliveryChallan,PaymentInInvoice
from purchase.models import PurchaseItem,  Purchase,PurchaseReturnItem, DebitNoteItem, DebitNote ,PaymentOut,PurchaseReturn,PurchaseOrder
from parties.models import Party, PartyCategory
from expenses.models import Expense, ExpenseCategory
from inventory.models import Item
from decimal import Decimal
from time import timezone
from django.utils import timezone
from django.db.models.functions import Coalesce
from collections import defaultdict
from django.utils.dateparse import parse_date
from .models import AuditTrail
from rest_framework.response import Response
from datetime import datetime
from rest_framework import status
from cash_and_bank.models import BankAccount
from .models import CapitalEntry, LoanEntry, FixedAssetEntry, InvestmentEntry, LoansAdvanceEntry, CurrentLiabilityEntry, CurrentAssetEntry
from .serializers import CapitalEntrySerializer, LoanEntrySerializer, FixedAssetEntrySerializer, InvestmentEntrySerializer, LoansAdvanceEntrySerializer, CurrentLiabilityEntrySerializer, CurrentAssetEntrySerializer
from collections import defaultdict
from django.db.models.functions import Cast

# import logging

# # Create a logger to store audit logs
# audit_logger = logging.getLogger('audit_logger')
# audit_handler = logging.FileHandler('audit_log.txt')
# audit_formatter = logging.Formatter('%(asctime)s - %(message)s')
# audit_handler.setFormatter(audit_formatter)
# audit_logger.addHandler(audit_handler)
# audit_logger.setLevel(logging.INFO)


from users.utils import get_current_business
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

#party

#recivable ageing report
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def receivable_ageing_report(request):
    today = timezone.now().date()
    business = get_current_business(request.user)

    # ✅ Filter invoices only for current business
    sales_data = Invoice.objects.filter(business=business).annotate(
        transaction_no=F('invoice_no'),
        transaction_type=Value('Invoice', output_field=CharField()),
        party_name=F('party__party_name'),
        pid=F('party__id'),
        amount=F('total_amount'),
        dueDate=F('due_date'),
        balanceAmount=F('balance_amount')
    ).values('pid', 'party_name', 'date', 'transaction_no', 'transaction_type', 'amount', 'dueDate', 'balanceAmount')

    ageing_report = {}

    for invoice in sales_data:
        party_name = invoice['party_name']
        party_id = invoice['pid']
        days_due = (today - invoice['dueDate']).days
        balance = invoice['balanceAmount']

        if party_name not in ageing_report:
            ageing_report[party_name] = {
                'pid': party_id,
                '0-30_days': 0,
                '31-60_days': 0,
                '61-90_days': 0,
                '91_plus_days': 0,
                'current': 0,
                'total': 0
            }

        if days_due < 0:
            ageing_report[party_name]['current'] += float(balance)
        elif 0 <= days_due <= 30:
            ageing_report[party_name]['0-30_days'] += float(balance)
        elif 31 <= days_due <= 60:
            ageing_report[party_name]['31-60_days'] += float(balance)
        elif 61 <= days_due <= 90:
            ageing_report[party_name]['61-90_days'] += float(balance)
        else:
            ageing_report[party_name]['91_plus_days'] += float(balance)

        ageing_report[party_name]['total'] += float(balance)

    return JsonResponse(ageing_report, safe=False)

#party report by item

@api_view(['GET'])
@permission_classes([IsAuthenticated])

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def party_report_by_item(request):
    business = get_current_business(request.user)
    item_id = request.GET.get('item_id')

    # Fetch item(s)
    if item_id:
        try:
            item = Item.objects.get(pk=item_id, business=business)
            items = [item]
        except Item.DoesNotExist:
            return Response({'error': 'Item not found'}, status=404)
    else:
        items = Item.objects.filter(business=business)

    parties = Party.objects.filter(business=business)
    report_data = []

    for item in items:
        for party in parties:
            # Fetch all sales entries for this item and party
            sales_entries = InvoiceItem.objects.filter(
                item=item,
                invoice__party=party,
                invoice__business=business
            ).values(
                'quantity', 'amount', 'invoice__date'
            )

            # Fetch all purchase entries for this item and party
            purchase_entries = PurchaseItem.objects.filter(
                item=item,
                purchase__party=party,
                purchase__business=business
            ).values(
                'quantity', 'amount', 'purchase__date'
            )

            sales_data = [
                {
                    'date': entry['invoice__date'],
                    'quantity': float(entry['quantity']),
                    'amount': float(entry['amount'])
                }
                for entry in sales_entries
            ]

            purchase_data = [
                {
                    'date': entry['purchase__date'],
                    'quantity': float(entry['quantity']),
                    'amount': float(entry['amount'])
                }
                for entry in purchase_entries
            ]

            report_data.append({
                'item_name': item.itemName,
                'party_name': party.party_name,
                'sales': sales_data,
                'purchases': purchase_data,
            })

    return Response({'transactions': report_data})#party ledger 


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def party_ledger(request, party_id):
    business = get_current_business(request.user)

    try:
        party = Party.objects.get(pk=party_id, business=business)
    except Party.DoesNotExist:
        return JsonResponse({'error': 'Party not found or access denied'}, status=404)

    opening_balance = party.opening_balance
    transactions = []

    # Common fields
    base_fields = ['date', 'transaction_no', 'tid', 'transaction_type', 'debit_amount', 'credit_amount', 'mode']

    # Invoices (Debits)
    invoices = Invoice.objects.filter(party=party, business=business).annotate(
        transaction_no=F('invoice_no'),
        tid=F('id'),
        transaction_type=Value('Invoice', output_field=CharField()),
        Date=F('date'),
        debit_amount=F('total_amount'),
        credit_amount=Value(Decimal('0.00'), output_field=DecimalField()),
        mode=F('payment_method')
    ).values(*base_fields)

    # Payments (Credits)
    payments = PaymentIn.objects.filter(party=party, business=business).annotate(
        transaction_no=F('payment_in_number'),
        tid=F('id'),
        transaction_type=Value('Payment In', output_field=CharField()),
        Date=F('date'),
        debit_amount=Value(Decimal('0.00'), output_field=DecimalField()),
        credit_amount=F('amount'),
        mode=F('payment_mode')
    ).values(*base_fields)

    # Sales Returns (Credits)
    sales_returns = SalesReturn.objects.filter(party=party, business=business).annotate(
        transaction_no=F('salesreturn_no'),
        tid=F('id'),
        transaction_type=Value('SalesReturn', output_field=CharField()),
        Date=F('date'),
        debit_amount=Value(Decimal('0.00'), output_field=DecimalField()),
        credit_amount=F('total_amount'),
        mode=F('payment_method')
    ).values(*base_fields)

    # Credit Notes (Credits)
    credit_notes = CreditNote.objects.filter(party=party, business=business).annotate(
        transaction_no=F('credit_note_no'),
        tid=F('id'),
        transaction_type=Value('CreditNote', output_field=CharField()),
        Date=F('date'), 
        debit_amount=Value(Decimal('0.00'), output_field=DecimalField()),
        credit_amount=F('total_amount'),
        mode=F('payment_method')
    ).values(*base_fields)

    # Purchases (Debits)
    purchases = Purchase.objects.filter(party=party, business=business).annotate(
        transaction_no=F('purchase_no'),
        tid=F('id'),
        transaction_type=Value('Purchase', output_field=CharField()),
        Date=F('date'), 
        debit_amount=F('total_amount'),
        credit_amount=Value(Decimal('0.00'), output_field=DecimalField()),
        mode=F('payment_method')
    ).values(*base_fields)

    # Payments Out (Credits)
    payments_out = PaymentOut.objects.filter(party=party, business=business).annotate(
        transaction_no=F('payment_out_number'),
        tid=F('id'),
        transaction_type=Value('Payment Out', output_field=CharField()),
        Date=F('date'), 
        debit_amount=Value(Decimal('0.00'), output_field=DecimalField()),
        credit_amount=F('amount'),
        mode=F('payment_mode')
    ).values(*base_fields)

    # Debit Notes (Debits)
    debit_notes = DebitNote.objects.filter(party=party, business=business).annotate(
        transaction_no=F('debitnote_no'),
        tid=F('id'),
        transaction_type=Value('DebitNote', output_field=CharField()),
        Date=F('date'), 
        debit_amount=F('total_amount'),
        credit_amount=Value(Decimal('0.00'), output_field=DecimalField()),
        mode=F('payment_method')
    ).values(*base_fields)

    # Merge all transactions
    transactions = list(invoices) + list(payments) + list(sales_returns) + list(credit_notes) + list(purchases) + list(payments_out) + list(debit_notes)

    # Sort by date
    transactions.sort(key=lambda x: x['date'])

    # Running Balance
    balance = opening_balance
    for txn in transactions:
        balance += Decimal(txn['debit_amount']) - Decimal(txn['credit_amount'])
        txn['balance'] = str(balance)

    return JsonResponse({
        'party': party.party_name,
        'opening_balance': float(opening_balance),
        'closing_balance': float(balance),
        'transactions': transactions
    }, safe=False)
    
#party wise outstanding

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def party_wise_outstanding(request):
    business = get_current_business(request.user)
    party_category_id = request.GET.get('party_category_id')

    # Filter base: always filter by business
    filter_conditions = {'business': business}

    if party_category_id:
        try:
            category = PartyCategory.objects.get(id=party_category_id, business=business)
            filter_conditions['category'] = category
        except PartyCategory.DoesNotExist:
            return JsonResponse({"error": "Category ID not found"}, status=400)

    # Parties with 'To Pay'
    to_pay_parties = list(
        Party.objects.filter(balance_type='To Pay', **filter_conditions)
        .annotate(
            name=F('party_name'),
            pid=F('id'),
            number=F('mobile_number'),
            closingBalance=F('closing_balance'),
            category_name=F('category__name'),
            createdAt=F('created_at')  # Add the created_at field here
        ).values('name', 'pid', 'category_name', 'number', 'closing_balance', 'createdAt')
    )

    # Parties with 'To Collect'
    to_collect_parties = list(
        Party.objects.filter(balance_type='To Collect', **filter_conditions)
        .annotate(
            name=F('party_name'),
            pid=F('id'),
            number=F('mobile_number'),
            closingBalance=F('closing_balance'),
            category_name=F('category__name'),
            createdAt=F('created_at')  # Add the created_at field here
        ).values('name', 'pid', 'category_name', 'number', 'closing_balance', 'createdAt')
    )

    # Combine both
    all_parties = to_pay_parties + to_collect_parties
    all_parties_sorted = sorted(all_parties, key=lambda x: x['closing_balance'], reverse=True)

    # Totals
    total_to_pay = sum(float(party['closing_balance']) for party in to_pay_parties)
    total_to_collect = sum(float(party['closing_balance']) for party in to_collect_parties)

    return JsonResponse({
        'To Pay': total_to_pay,
        'To Collect': total_to_collect,
        'transactions': all_parties_sorted
    }, safe=False)

#SALES SUMMARY CATEGORY WISE

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sales_summary_categorywise(request):
    # Annotate invoice data with related fields
    invoices = Invoice.objects.select_related('party__category').annotate(
        Invoice_no=F('invoice_no'),
        party_name=F('party__party_name'),
        category_name=F('party__category__name'),
        transaction_type=Value('Invoice', output_field=CharField()),
        amount=F('total_amount'),
        Balance_amount=F('balance_amount'),
        Due_date=F('due_date'),
        invoice_type=F('payment_method'),
        invoice_status=F('status')
    ).values(
        'date', 'Invoice_no', 'party_name', 'Due_date',
        'amount', 'Balance_amount', 'invoice_type', 'invoice_status', 'category_name'
    )

    # Organize by category name
    grouped_data = defaultdict(lambda: {
        'transactions': [],
        'total': 0
    })

    for invoice in invoices:
        category = invoice['category_name'] or 'No Category'
        grouped_data[category]['transactions'].append(invoice)
        grouped_data[category]['total'] += invoice['amount']

    # Optional: sort transactions inside each category by date (latest first)
    for cat in grouped_data:
        grouped_data[cat]['transactions'].sort(key=lambda x: x['date'], reverse=True)

    # Format final response
    response = []
    for category, data in grouped_data.items():
        response.append({
            'category_name': category,
            'transactions': data['transactions'],
            'total': data['total']
        })

    return JsonResponse(response, safe=False)


#ITEM

#ITEM REPORT BY PARTY
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def item_report_by_party(request):
    business = get_current_business(request.user)

    party_id = request.GET.get('party_id')

    # Filter items by business
    item_data = Item.objects.filter(business=business)

    report_data = []

    # Determine party/parties under the same business
    if party_id:
        try:
            party = Party.objects.get(pk=party_id, business=business)
            parties = [party]
        except Party.DoesNotExist:
            return JsonResponse({'error': 'Party not found'}, status=404)
    else:
        parties = Party.objects.filter(business=business)

    # Generate report data
    for item in item_data:
        for party in parties:
            sales_filter = {
                'item': item,
                'invoice__party': party,
                'invoice__business': business
            }
            purchase_filter = {
                'item': item,
                'purchase__party': party,
                'purchase__business': business
            }

            # Get sales data (using the related invoice date, with Max to get latest sales date)
            sales_data = InvoiceItem.objects.filter(**sales_filter).aggregate(
                total_sales_quantity=Sum('quantity'),
                total_sales_amount=Sum('amount'),
                # latest_sales_date=Max('invoice__date')  # Use Max to get the latest sales date
            )

            # Get purchase data (using the related purchase date, with Max to get latest purchase date)
            purchase_data = PurchaseItem.objects.filter(**purchase_filter).aggregate(
                total_purchase_quantity=Sum('quantity'),
                total_purchase_amount=Sum('amount'),
                # latest_purchase_date=Max('purchase__date')  # Use Max to get the latest purchase date
            )

            report_data.append({
                'item_name': item.itemName,
                'item_date':item.created_at,
                'party_name': party.party_name,
                'sales_quantity': sales_data['total_sales_quantity'] or 0,
                'sales_amount': float(sales_data['total_sales_amount'] or 0),
                # 'latest_sales_date': sales_data['latest_sales_date'] or 'No sales date',  # Show latest sales date
                'purchase_quantity': purchase_data['total_purchase_quantity'] or 0,
                'purchase_amount': float(purchase_data['total_purchase_amount'] or 0),
                # 'latest_purchase_date': purchase_data['latest_purchase_date'] or 'No purchase date',  # Show latest purchase date
            })

    return JsonResponse({'transactions': report_data}, safe=False)#ITEM SALES AND PURCHASE SUMMARY

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def item_sales_and_purchase_summary(request):
    business = get_current_business(request.user)

    # date_str = request.GET.get('date')
    # filter_date = parse_date(date_str) if date_str else None

    items = Item.objects.filter(business=business).select_related('gstTaxRate', 'measuringUnit')

    report_data = []

    for item in items:
        stock_qty = item.openingStock
        stock_value = stock_qty * item.purchasePrice if stock_qty > 0 else Decimal(0)

        sales_filter = {
            'item': item,
            'invoice__business': business
        }
        purchase_filter = {
            'item': item,
            'purchase__business': business
        }

        # if filter_date:
        #     sales_filter['invoice__date'] = filter_date
        #     purchase_filter['purchase__date'] = filter_date

        sales_data = InvoiceItem.objects.filter(**sales_filter).aggregate(
            total_sales_quantity=Sum('quantity'),
            total_sales_value=Sum(F('quantity') * F('unit_price'))
        )

        purchase_data = PurchaseItem.objects.filter(**purchase_filter).aggregate(
            total_purchase_quantity=Sum('quantity'),
            total_purchase_value=Sum(F('quantity') * F('unit_price'))
        )

        report_data.append({
            "item_name": item.itemName,
            "item_code": getattr(item, "itemCode", ""),
            "date":item.created_at,
            "stock_quantity": float(stock_qty or 0),
            "stock_value": float(stock_value or 0),
            "total_sales_quantity": float(sales_data['total_sales_quantity'] or 0),
            "total_sales_value": float(sales_data['total_sales_value'] or 0),
            "total_purchase_quantity": float(purchase_data['total_purchase_quantity'] or 0),
            "total_purchase_value": float(purchase_data['total_purchase_value'] or 0),
        })

    return JsonResponse({'stock_summary': report_data}, safe=False)

#LOW STOCK SUMMARY
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def low_stock_summary(request):
    business = get_current_business(request.user)

    # Fetch items only for the current business where low stock warning is enabled
    items = Item.objects.filter(business=business, enableLowStockWarning=True)

    report_data = []
    total_stock_value = 0

    for item in items:
        stock_quantity = item.openingStock
        stock_value = stock_quantity * item.salesPrice if stock_quantity else 0

        report_data.append({
            "item_name": item.itemName,
            "item_code": getattr(item, "itemCode", ""),  # Optional, safe fallback
            "stock_quantity": float(stock_quantity or 0),
            "low_stock_value": float(item.lowStockQty or 0),
            "stock_value": round(float(stock_value), 2)
        })

        total_stock_value += stock_value

    return JsonResponse({
        "transactions": report_data,
        "total_stock_value": round(float(total_stock_value), 2)
    }, safe=False)

# RATE LIST
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def rate_list(request):
    business = get_current_business(request.user)

    # Fetch only items belonging to the current business
    items = Item.objects.filter(business=business)

    report_data = []

    for item in items:
        report_data.append({
            'item_name': item.itemName,
            'item_code': getattr(item, 'itemCode', ''),  # Optional fallback
            'MRP': "",  # Leave this empty unless you plan to add an MRP field
            'selling_price': float(item.salesPrice or 0)
        })

    return JsonResponse({'transactions': report_data}, safe=False)


#STOCK DETAIL REPORTS
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stock_details_report(request):
    item_id = request.GET.get('item_id')
    business = get_current_business(request.user)

    if not item_id:
        return JsonResponse({'message': 'No item selected'}, status=400)

    try:
        item = Item.objects.prefetch_related(
            'invoiceitem_set',
            'salesreturnitem_set',
            'creditnoteitem_set',
            'purchaseitem_set',
            'purchasereturnitem_set',
            'debitnoteitem_set'
        ).get(id=item_id, business=business)  # ✅ restrict to current business

        transactions = []
        closing_stock = item.openingStock

        # Sales
        for sales_item in item.invoiceitem_set.all():
            transactions.append({
                'date': sales_item.invoice.date,
                'transaction_type': 'Invoice',
                'tid': sales_item.invoice.id,
                'quantity': -sales_item.quantity,
                'closing_stock': closing_stock - sales_item.quantity,
                'notes': 'Sales made to customers',
            })
            closing_stock -= sales_item.quantity

        # Sales Returns
        for return_item in item.salesreturnitem_set.all():
            transactions.append({
                'date': return_item.salesreturn.date,
                'transaction_type': 'Sales Return',
                'tid': return_item.salesreturn.id,
                'quantity': return_item.quantity,
                'closing_stock': closing_stock + return_item.quantity,
                'notes': 'Items returned by customers',
            })
            closing_stock += return_item.quantity

        # Credit Notes
        for credit_item in item.creditnoteitem_set.all():
            transactions.append({
                'date': credit_item.creditnote.date,
                'transaction_type': 'Credit Note',
                'tid': credit_item.creditnote.id,
                'quantity': credit_item.quantity,
                'closing_stock': closing_stock + credit_item.quantity,
                'notes': 'Credit notes issued for returned items',
            })
            closing_stock += credit_item.quantity

        # Purchases
        for purchase_item in item.purchaseitem_set.all():
            transactions.append({
                'date': purchase_item.purchase.date,
                'transaction_type': 'Purchase',
                'tid': purchase_item.purchase.id,
                'quantity': purchase_item.quantity,
                'closing_stock': closing_stock + purchase_item.quantity,
                'notes': 'Stock purchased from suppliers',
            })
            closing_stock += purchase_item.quantity

        # Purchase Returns
        for pr_item in item.purchasereturnitem_set.all():
            transactions.append({
                'date': pr_item.purchasereturn.date,
                'transaction_type': 'Purchase Return',
                'tid': pr_item.purchasereturn.id,
                'quantity': -pr_item.quantity,
                'closing_stock': closing_stock - pr_item.quantity,
                'notes': 'Items returned to suppliers',
            })
            closing_stock -= pr_item.quantity

        # Debit Notes
        for debit_item in item.debitnoteitem_set.all():
            transactions.append({
                'date': debit_item.debitnote.date,
                'transaction_type': 'Debit Note',
                'tid': debit_item.debitnote.id,
                'quantity': debit_item.quantity,
                'closing_stock': closing_stock + debit_item.quantity,
                'notes': 'Debit notes issued for returned items',
            })
            closing_stock += debit_item.quantity

        # Sort by date for chronological order
        transactions.sort(key=lambda x: x['date'])

        return JsonResponse({
            'stock_details_report': {
                'item_name': item.itemName,
                'item_code': getattr(item, 'itemCode', ''),
                'transactions': transactions
            }
        }, safe=False)

    except Item.DoesNotExist:
        return JsonResponse({'error': 'Item not found or unauthorized access'}, status=404)

# STOCK SUMMARY
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stock_summary(request):
    business = get_current_business(request.user)
    category_id = request.GET.get('category_id')

    # Filter items by business and optionally category
    items = Item.objects.filter(business=business)
    if category_id:
        items = items.filter(category_id=category_id)

    report_data = []
    total_stock_value = Decimal(0)
    

    for item in items:
        def get_purchasePrice_without_tax(item):
            """Returns the tax-inclusive purchase price if stored without tax."""
            if item.purchasePriceType == "With Tax":
                return item.calculate_price(item.purchasePrice, "With Tax")
            return item.purchasePrice  # Already tax-inclusive
        purchase_price_without_tax = get_purchasePrice_without_tax(item)
        
        # Calculate stock value based on closingStock and purchasePrice_without_tax
        if item.closingStock and purchase_price_without_tax:
            stock_value = item.closingStock * purchase_price_without_tax
        else:
            stock_value = 0.00
        
        total_stock_value += stock_value
        
        report_data.append({
            
            'item_name': item.itemName,
            'item_code': getattr(item, 'itemCode', ''),
            'purchase_price': round(item.purchasePrice, 2),
            'selling_price': round(item.salesPrice, 2),
            'stock_quantity': round(item.closingStock, 2),
            'stock_value': round(stock_value, 2),
            'last_updated': item.created_at
        })

    return JsonResponse({
        'stock_summary': report_data,
        'total_stock_value': round(total_stock_value, 2)
    }, safe=False)
    

# TRANSACTIONS
#BILL WISE PROOFIT

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bill_wise_profit(request):
    business = get_current_business(request.user)
    party_id_filter = request.GET.get('party_id')

    invoices = Invoice.objects.filter(business=business).prefetch_related('invoice_items', 'party')

    if party_id_filter:
        try:
            party_id_filter = int(party_id_filter)
            invoices = invoices.filter(party_id=party_id_filter)
        except ValueError:
            return JsonResponse({'error': 'Invalid party_id'}, status=400)

    report_data = []
    net_profit = Decimal(0)
    total_sales = Decimal(0)

    for invoice in invoices:
        sales_amount = invoice.total_amount or Decimal(0)
        total_purchase_price = Decimal(0)

        for item in invoice.invoice_items.all():
            if hasattr(item, 'get_purchasePrice_with_tax'):
                total_purchase_price += Decimal(item.get_purchasePrice_with_tax())
            else:
                total_purchase_price += Decimal(0)

        profit = sales_amount - total_purchase_price
        net_profit += profit
        total_sales += sales_amount

        report_data.append({
            'date': invoice.date,
            'invoice_no': invoice.invoice_no,
            'tid': invoice.id,
            'party_name': invoice.party.party_name,
            'party_id': invoice.party.id,
            'invoice_amount': float(invoice.total_amount),
            'sales_amount': float(sales_amount),
            'purchase_amount': float(total_purchase_price),
            'profit': float(profit),
        })

    sorted_report = sorted(report_data, key=lambda x: x['date'], reverse=True)

    return JsonResponse({
        'transactions': sorted_report,
        'total_sales': float(total_sales),
        'net_profit': float(net_profit)
    }, safe=False)
    

#CASH AND BANK

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cash_and_bank_report(request):
    business = get_current_business(request.user)
    voucher_type_filter = request.GET.get('Voucher_type', None)

    def annotate_common_qs(qs, voucher_type, trans_no_field, paid_field=None, received_field=None):
        return qs.annotate(
            Voucher_type=Value(voucher_type, output_field=CharField()),
            transaction_no=F(trans_no_field),
            tid=F('id'),
            party_name=F('party__party_name'),
            paid=F(paid_field) if paid_field else Value(None, output_field=DecimalField()),
            received=F(received_field) if received_field else Value(None, output_field=DecimalField()),
            notes_annotated=F('notes')
        ).values('date', 'tid', 'transaction_no', 'Voucher_type', 'party_name', 'paid', 'received', 'notes_annotated')

    # SALES
    sales_data = list(annotate_common_qs(
        Invoice.objects.filter(business=business), 'Invoice', 'invoice_no', received_field='amount_received'
    )) + list(annotate_common_qs(
        SalesReturn.objects.filter(business=business), 'Sales Return', 'salesreturn_no', paid_field='amount_received'
    )) + list(annotate_common_qs(
        PaymentIn.objects.filter(business=business), 'Payment In', 'payment_in_number', received_field='amount'
    )) + list(annotate_common_qs(
        CreditNote.objects.filter(business=business), 'Credit Note', 'credit_note_no', paid_field='amount_received'
    ))

    # PURCHASE
    purchase_data = list(annotate_common_qs(
        Purchase.objects.filter(business=business), 'Purchase', 'purchase_no', paid_field='amount_received'
    )) + list(annotate_common_qs(
        PurchaseReturn.objects.filter(business=business), 'Purchase Return', 'purchasereturn_no', received_field='amount_received'
    )) + list(annotate_common_qs(
        DebitNote.objects.filter(business=business), 'Debit Note', 'debitnote_no', received_field='amount_received'
    )) + list(annotate_common_qs(
        PaymentOut.objects.filter(business=business), 'Payment Out', 'payment_out_number', paid_field='amount'
    ))

    # Apply voucher filter if present
    if voucher_type_filter:
        sales_data = [tx for tx in sales_data if tx['Voucher_type'] == voucher_type_filter]
        purchase_data = [tx for tx in purchase_data if tx['Voucher_type'] == voucher_type_filter]

    all_data = sales_data + purchase_data
    all_data_sorted = sorted(all_data, key=lambda x: (x['date'], x['tid']))

    # Balance tracking
    total_paid = Decimal(0)
    total_received = Decimal(0)
    balance = Decimal(0)
    results = []

    for tx in all_data_sorted:
        paid = Decimal(tx.get('paid') or 0)
        received = Decimal(tx.get('received') or 0)

        if received:
            balance += received
            total_received += received
        if paid:
            balance -= paid
            total_paid += paid

        results.append({
            'transaction_no': tx['transaction_no'],
            'Voucher_type': tx['Voucher_type'],
            'party_name': tx['party_name'],
            'date': tx['date'],
            'received': float(received),
            'paid': float(paid),
            'balance': float(balance),
            'notes': tx.get('notes_annotated') or '',
        })

    return JsonResponse({
        'transactions': results,
        'total_received': float(total_received),
        'total_paid': float(total_paid),
        'closing_balance': float(balance)
    }, safe=False)


#DAY BOOK
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def daybook(request):
    business = get_current_business(request.user)
    transaction_type_filter = request.GET.get('transaction_type')

    def annotate_qs(qs, trans_type, trans_no_field, amount_field='total_amount', money_in=None, money_out=None):
        return qs.annotate(
            transaction_type=Value(trans_type, output_field=CharField()),
            transaction_no=F(trans_no_field),
            tid=F('id'),
            party_name=F('party__party_name'),
            amount_annotated=F(amount_field) if amount_field else Value(None, output_field=DecimalField()),
            money_in=F(money_in) if money_in else Value(None, output_field=DecimalField()),
            money_out=F(money_out) if money_out else Value(None, output_field=DecimalField()),
            Balance_amount=F('balance_amount') if hasattr(qs.model, 'balance_amount') else Value(None, output_field=DecimalField())
        ).values('date', 'tid', 'transaction_no', 'transaction_type', 'party_name', 'amount_annotated', 'money_in', 'money_out', 'Balance_amount')

    sales = list(annotate_qs(Invoice.objects.filter(business=business), 'Invoice', 'invoice_no', money_in='amount_received'))
    sales += list(annotate_qs(Quotation.objects.filter(business=business), 'Quotation', 'quotation_no'))
    sales += list(annotate_qs(SalesReturn.objects.filter(business=business), 'Sales Return', 'salesreturn_no', money_out='total_amount'))
    sales += list(annotate_qs(PaymentIn.objects.filter(business=business), 'Payment In', 'payment_in_number', amount_field=None, money_in='amount'))
    sales += list(annotate_qs(CreditNote.objects.filter(business=business), 'Credit Note', 'credit_note_no', money_out='total_amount'))
    sales += list(annotate_qs(DeliveryChallan.objects.filter(business=business), 'Delivery Challan', 'delivery_challan_no'))
    sales += list(annotate_qs(Proforma.objects.filter(business=business), 'Proforma', 'proforma_no'))

    purchases = list(annotate_qs(Purchase.objects.filter(business=business), 'Purchase', 'purchase_no', money_out='total_amount'))
    purchases += list(annotate_qs(PurchaseReturn.objects.filter(business=business), 'Purchase Return', 'purchasereturn_no', money_in='amount_received'))
    purchases += list(annotate_qs(DebitNote.objects.filter(business=business), 'Debit Note', 'debitnote_no', money_in='amount_received'))
    purchases += list(annotate_qs(PaymentOut.objects.filter(business=business), 'Payment Out', 'payment_out_number', amount_field=None, money_out='amount'))
    purchases += list(annotate_qs(PurchaseOrder.objects.filter(business=business), 'Purchase Order', 'purchase_order_no'))

    if transaction_type_filter:
        sales = [tx for tx in sales if tx['transaction_type'] == transaction_type_filter]
        purchases = [tx for tx in purchases if tx['transaction_type'] == transaction_type_filter]

    all_tx = sales + purchases
    all_tx_sorted = sorted(all_tx, key=lambda x: (x['date'], x['tid']), reverse=True)

    total_money_in = sum(Decimal(tx.get('money_in') or 0) for tx in all_tx)
    total_money_out = sum(Decimal(tx.get('money_out') or 0) for tx in all_tx)
    net_amount = total_money_in - total_money_out

    return JsonResponse({
        'transactions': all_tx_sorted,
        'total_money_in': float(total_money_in),
        'total_money_out': float(total_money_out),
        'total_net_amount': float(net_amount)
    }, safe=False)

# #EXPENSE CATEGORY REPORT
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def expense_category(request):
    business = get_current_business(request.user)

    expenses = (
        Expense.objects
        .filter(business=business)
        .annotate(
            expense_category_id=F('category_id'),
            category_name=Coalesce(F('category__name'), Value('Unknown')),
            createdAt=F('category__created_at')  # Add the created_at field to the annotation
        )
        .values('expense_category_id', 'category_name', 'createdAt')  # Include created_at in values
        .annotate(total_amount=Sum('total_amount'))
        .order_by('total_amount')
    )

    return JsonResponse({
        'category_totals': list(expenses)
    }, safe=False)

    

#EXPENSE TRANSACTION REPORT
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def expense_transaction_report(request):
    business = get_current_business(request.user)
    category_filter = request.GET.get('category', None)

    # Filter expenses by current business
    expenses = Expense.objects.filter(business=business)

    # Optional category filter (by ID)
    if category_filter:
        expenses = expenses.filter(category__id=category_filter)

    # Annotate fields for report display
    expense_query = expenses.annotate(
        Expense_no=F('expense_no'),
        Category=F('category__name'),
        Date=F('date'),
        Total_amount=F('total_amount'),
        Payment_mode=F('payment_method'),
    ).values(
        'Expense_no', 'Category', 'Date', 'Total_amount', 'Payment_mode'
    ).order_by('-Date')  # Most recent first

    return JsonResponse({
        'transactions': list(expense_query)
    }, safe=False)


#SALES SUMMARY
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sales_summary(request):
    business = get_current_business(request.user)
    party_id_filter = request.GET.get('party_id')

    # Start with all invoices of current business
    invoices = Invoice.objects.filter(business=business)

    # Optional filter by party
    if party_id_filter:
        try:
            party_id_filter = int(party_id_filter)
            invoices = invoices.filter(party_id=party_id_filter)
        except ValueError:
            return JsonResponse({'error': 'Invalid party_id'}, status=400)

    # Annotate with fields for response
    invoices = invoices.annotate(
        Invoice_no=F('invoice_no'),
        tid=F('id'),
        party_name=F('party__party_name'),
        transaction_type=Value('Invoice', output_field=CharField()),
        amount=F('total_amount'),
        Balance_amount=F('balance_amount'),
        Due_date=F('due_date'),
        invoice_type=F('payment_method'),
        invoice_status=F('status')
    ).values(
        'tid', 'date', 'Invoice_no', 'party_name',
        'Due_date', 'amount', 'Balance_amount', 'invoice_type', 'invoice_status'
    ).order_by('-date')

    # Total sales for this filtered list
    total_sales = invoices.aggregate(total=Sum('amount'))['total'] or 0

    return JsonResponse({
        'transactions': list(invoices),
        'total_sales': round(total_sales, 2)
    }, safe=False)

#PURCHASE SUMMARY
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def purchase_summary(request):
    business = get_current_business(request.user)

    # Query filtered by current business
    purchase_qs = Purchase.objects.filter(business=business)

    # Annotate for structured response
    purchase_data = list(purchase_qs.annotate(
        Purchase_no=F('purchase_no'),
        Original_invoice_no=F('original_invoice_no'),
        tid=F('id'),
        party_name=F('party__party_name'),
        purchase_amount=F('total_amount'),
        purchase_notes=F('notes')
    ).values('date', 'tid', 'Purchase_no', 'Original_invoice_no', 'party_name', 'purchase_amount', 'purchase_notes').order_by('-date'))

    # Aggregate total purchase from the filtered queryset
    total_purchase = purchase_qs.aggregate(total=Sum('total_amount'))['total'] or 0

    return JsonResponse({
        'transactions': purchase_data,
        'total_purchases': round(total_purchase, 2)
    }, safe=False)
    
    

#BALANCE SHEET

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_loans_advance_entry(request):
    serializer = LoansAdvanceEntrySerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(business=get_current_business(request.user))
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_loans_advance_entries(request):
    entries = LoansAdvanceEntry.objects.filter(business=get_current_business(request.user))
    serializer = LoansAdvanceEntrySerializer(entries, many=True)
    return Response(serializer.data)

@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def loans_advance_entry_detail(request, pk):
    try:
        entry = LoansAdvanceEntry.objects.get(pk=pk, business=get_current_business(request.user))
    except LoansAdvanceEntry.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)

    if request.method == 'PUT':
        serializer = LoansAdvanceEntrySerializer(entry, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)
    elif request.method == 'DELETE':
        entry.delete()
        return Response(status=204)
    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_investment_entry(request):
    serializer = InvestmentEntrySerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(business=get_current_business(request.user))
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_investment_entries(request):
    entries = InvestmentEntry.objects.filter(business=get_current_business(request.user))
    serializer = InvestmentEntrySerializer(entries, many=True)
    return Response(serializer.data)

@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def investment_entry_detail(request, pk):
    try:
        entry = InvestmentEntry.objects.get(pk=pk, business=get_current_business(request.user))
    except InvestmentEntry.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)

    if request.method == 'PUT':
        serializer = InvestmentEntrySerializer(entry, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)
    elif request.method == 'DELETE':
        entry.delete()
        return Response(status=204)
    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_fixed_asset_entry(request):
    serializer = FixedAssetEntrySerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(business=get_current_business(request.user))
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_fixed_asset_entries(request):
    entries = FixedAssetEntry.objects.filter(business=get_current_business(request.user))
    serializer = FixedAssetEntrySerializer(entries, many=True)
    return Response(serializer.data)

@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def fixed_asset_entry_detail(request, pk):
    try:
        entry = FixedAssetEntry.objects.get(pk=pk, business=get_current_business(request.user))
    except FixedAssetEntry.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)

    if request.method == 'PUT':
        serializer = FixedAssetEntrySerializer(entry, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)
    elif request.method == 'DELETE':
        entry.delete()
        return Response(status=204)    

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_current_asset_entry(request):
    serializer = CurrentAssetEntrySerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(business=get_current_business(request.user))
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_current_asset_entries(request):
    entries = CurrentAssetEntry.objects.filter(business=get_current_business(request.user))
    serializer = CurrentAssetEntrySerializer(entries, many=True)
    return Response(serializer.data)

@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def current_asset_entry_detail(request, pk):
    try:
        entry = CurrentAssetEntry.objects.get(pk=pk, business=get_current_business(request.user))
    except CurrentAssetEntry.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)

    if request.method == 'PUT':
        serializer = CurrentAssetEntrySerializer(entry, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)
    elif request.method == 'DELETE':
        entry.delete()
        return Response(status=204)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_loan_entry(request):
    serializer = LoanEntrySerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(business=get_current_business(request.user))
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_loan_entries(request):
    entries = LoanEntry.objects.filter(business=get_current_business(request.user))
    serializer = LoanEntrySerializer(entries, many=True)
    return Response(serializer.data)

@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def loan_entry_detail(request, pk):
    try:
        entry = LoanEntry.objects.get(pk=pk, business=get_current_business(request.user))
    except LoanEntry.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)

    if request.method == 'PUT':
        serializer = LoanEntrySerializer(entry, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)
    elif request.method == 'DELETE':
        entry.delete()
        return Response(status=204)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_current_liability_entry(request):
    serializer = CurrentLiabilityEntrySerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(business=get_current_business(request.user))
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_current_liability_entries(request):
    entries = CurrentLiabilityEntry.objects.filter(business=get_current_business(request.user))
    serializer = CurrentLiabilityEntrySerializer(entries, many=True)
    return Response(serializer.data)

@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def current_liability_entry_detail(request, pk):
    try:
        entry = CurrentLiabilityEntry.objects.get(pk=pk, business=get_current_business(request.user))
    except CurrentLiabilityEntry.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)

    if request.method == 'PUT':
        serializer = CurrentLiabilityEntrySerializer(entry, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)
    elif request.method == 'DELETE':
        entry.delete()
        return Response(status=204)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_capital_entry(request):
    serializer = CapitalEntrySerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(business=get_current_business(request.user))
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_capital_entries(request):
    entries = CapitalEntry.objects.filter(business=get_current_business(request.user))
    serializer = CapitalEntrySerializer(entries, many=True)
    return Response(serializer.data)

@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def capital_entry_detail(request, pk):
    try:
        entry = CapitalEntry.objects.get(pk=pk, business=get_current_business(request.user))
    except CapitalEntry.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)

    if request.method == 'PUT':
        serializer = CapitalEntrySerializer(entry, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)
    elif request.method == 'DELETE':
        entry.delete()
        return Response(status=204)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def balance_sheet(request):
    business = get_current_business(request.user)
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # Add at the start of the function
    if start_date and end_date:
        if parse_date(start_date) > parse_date(end_date):
            return JsonResponse({
                'error': 'Start date cannot be after end date'
            }, status=400)

    date_filter = {}
    if start_date:
        date_filter['date__gte'] = parse_date(start_date)
    if end_date:
        date_filter['date__lte'] = parse_date(end_date)

    def sum_queryset(qs, field='amount'):
        return qs.aggregate(total=Sum(field))['total'] or Decimal('0.00')

    # Capital (Owner's money invested)
    capital = sum_queryset(CapitalEntry.objects.filter(business=business, **date_filter))

    # Loans (Money taken from bank/person, to be paid back with interest)
    loans = sum_queryset(LoanEntry.objects.filter(business=business, **date_filter))

    # Fixed Assets (Property, land, equipment, etc.)
    fixed_assets = sum_queryset(FixedAssetEntry.objects.filter(business=business, **date_filter))

    # Investments (Stocks, mutual funds, FDs, etc.)
    investments = sum_queryset(InvestmentEntry.objects.filter(business=business, **date_filter))

    # Loan Advance (Loan given to someone or advance paid to supplier)
    loans_advance = sum_queryset(LoansAdvanceEntry.objects.filter(business=business, **date_filter))

    # Current Liabilities (Amounts due to creditors, including accounts payable)
    current_liabilities = defaultdict(Decimal)
    
    # Tax Payable
    tax_payable = sum_queryset(Invoice.objects.filter(
        business=business,
        **date_filter
    ).annotate(
        tax_amount=F('total_amount') - F('taxable_amount')
    ), field='tax_amount')
    current_liabilities['Tax Payable'] += tax_payable

    # TCS Payable
    tcs_payable = sum_queryset(Purchase.objects.filter(
        business=business,
        **date_filter
    ).annotate(
        tcsAmount=F('tcs_amount')
    ), field='tcsAmount')
    current_liabilities['TCS Payable'] += tcs_payable

    # TDS Payable
    tds_payable = sum_queryset(Purchase.objects.filter(
        business=business,
        **date_filter
    ).annotate(
        tdsAmount=F('tds_amount')
    ), field='tdsAmount')
    current_liabilities['TDS Payable'] += tds_payable

    # Accounts Payable (Amounts due to suppliers)
    accounts_payable = sum_queryset(Purchase.objects.filter(
        business=business, status__in=['Unpaid', 'Partially Paid'], **date_filter
    ), field='total_amount')
    current_liabilities['Accounts Payable'] += accounts_payable

    # Current Assets (Things easily converted to cash, plus inventory, accounts receivable)
    current_assets = defaultdict(Decimal)

    # Tax Receivable
    tax_receivable = sum_queryset(Purchase.objects.filter(
        business=business,
        **date_filter
    ).annotate(
        tax_amount=F('total_amount') - F('taxable_amount')
    ), field='tax_amount')
    current_assets['Tax Receivable'] += tax_receivable

    # TCS Receivable
    tcs_receivable = sum_queryset(Invoice.objects.filter(
        business=business,
        **date_filter
    ).annotate(
        tcsAmount=F('tcs_amount')
    ), field='tcsAmount')
    current_assets['TCS Receivable'] += tcs_receivable

    # TDS Receivable
    # tds_receivable = sum_queryset(Invoice.objects.filter(
    #     business=business,
    #     **date_filter
    # ).annotate(
    #     tdsAmount=F('tds_amount')
    # ), field='tdsAmount')
    # current_assets['TDS Receivable'] += tds_receivable

    # Accounts Receivable (Amounts due from customers)
    accounts_receivable = sum_queryset(Invoice.objects.filter(
        business=business, status__in=['Unpaid', 'Partially Paid'], **date_filter
    ), field='total_amount')
    current_assets['Accounts Receivable'] += accounts_receivable

    # Inventory in Hand
    inventory_in_hand = Item.objects.filter(business=business).aggregate(
        total=Sum(
            Case(
                When(
                    purchasePriceType='With Tax',
                    then=F('closingStock') * F('purchasePrice') / (1 + F('gstTaxRate__rate') / 100)
                ),
                default=F('closingStock') * F('purchasePrice'),
                output_field=DecimalField()
            )
        )
    )['total'] or Decimal('0.00')
    current_assets['Inventory In Hand'] += inventory_in_hand

    # Cash/Bank
    cash_in_hand = sum_queryset(BankAccount.objects.filter(
        business=business, account_type='Cash', **date_filter
    ), field='current_balance')
    bank_balance = sum_queryset(BankAccount.objects.filter(
        business=business, account_type='Bank', **date_filter
    ), field='current_balance')
    current_assets['Cash In Hand'] += cash_in_hand
    current_assets['Cash In Bank'] += bank_balance

    # Net Income (profit/loss after all expenses)
    total_sales = sum_queryset(Invoice.objects.filter(business=business, **date_filter), field='total_amount')
    total_purchases = sum_queryset(Purchase.objects.filter(business=business, **date_filter), field='total_amount')
    gross_profit = total_sales - total_purchases
    
    # Get income and expenses
    other_income = sum_queryset(Expense.objects.filter(
        business=business,
        **date_filter
    ), field='total_amount')
    indirect_expenses = sum_queryset(Expense.objects.filter(
        business=business,
        **date_filter
    ), field='total_amount')
    net_income = gross_profit + other_income - indirect_expenses

    # Add TCS and TDS Payable
    tcs_payable = sum_queryset(Purchase.objects.filter(
        business=business,
        status__in=['Unpaid', 'Partially Paid'],
        **date_filter
    ).annotate(
        tcsAmount=F('tcs_amount')
    ), field='tcsAmount')

    tds_payable = sum_queryset(Purchase.objects.filter(
        business=business,
        status__in=['Unpaid', 'Partially Paid'],
        **date_filter
    ).annotate(
        tdsAmount=F('tds_amount')
    ), field='tdsAmount')

    current_liabilities['TCS Payable'] += tcs_payable
    current_liabilities['TDS Payable'] += tds_payable

    # Add GST calculations
    gst_payable = sum_queryset(Invoice.objects.filter(
        business=business,
        **date_filter
    ).annotate(
        gst_amount=F('total_amount') - F('taxable_amount')
    ), field='gst_amount')

    gst_receivable = sum_queryset(Purchase.objects.filter(
        business=business,
        **date_filter
    ).annotate(
        gst_amount=F('total_amount') - F('taxable_amount')
    ), field='gst_amount')

    current_liabilities['GST Payable'] += gst_payable
    current_assets['GST Receivable'] += gst_receivable

    # Totals
    total_liabilities = capital + loans + net_income + sum(current_liabilities.values())
    total_assets = sum(current_assets.values()) + fixed_assets + investments + loans_advance

    # Prepare response
    balance_sheet_data = {
        'assets': {
            'Current Assets': sorted(
                [{'name': k, 'amount': round(float(v), 2)} for k, v in current_assets.items()],
                key=lambda x: x['name']
            ),
            'Fixed Assets': round(float(fixed_assets), 2),
            'Investments': round(float(investments), 2),
            'Loan Advance': round(float(loans_advance), 2),
            'Total Assets': round(float(total_assets), 2)
        },
        'liabilities': {
            'Capital': round(float(capital), 2),
            'Current Liabilities': sorted(
                [{'name': k, 'amount': round(float(v), 2)} for k, v in current_liabilities.items()],
                key=lambda x: x['name']
            ),
            'Loans': round(float(loans), 2),
            'Net Income': round(float(net_income), 2),
            'Total Liabilities': round(float(total_liabilities), 2)
        },
        'net_income': round(float(net_income), 2),
        'date_range': {
            'start_date': start_date,
            'end_date': end_date
        }
    }

    return JsonResponse({'balance_sheet': balance_sheet_data})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profit_and_loss(request):
    business = get_current_business(request.user)

    # Get start and end dates from query parameters (if provided)
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # Convert string dates to proper date objects
    if start_date:
        start_date = parse_date(start_date)
    if end_date:
        end_date = parse_date(end_date)

    # 1. Sales (+)
    invoice_qs = Invoice.objects.filter(business=business)
    
    # Apply date filter if dates are provided
    if start_date:
        invoice_qs = invoice_qs.filter(date__gte=start_date)
    if end_date:
        invoice_qs = invoice_qs.filter(date__lte=end_date)

    total_sales = invoice_qs.aggregate(total=Sum('total_amount'))['total'] or Decimal(0)
    total_sales_tax = invoice_qs.aggregate(
        tax=Sum(F('invoice_items__amount') * (F('invoice_items__gstTaxRate__rate') / 100), output_field=DecimalField())
    )['tax'] or Decimal(0)

    # 2. Credit Notes (-)
    credit_qs = CreditNote.objects.filter(business=business)
    
    # Apply date filter if dates are provided
    if start_date:
        credit_qs = credit_qs.filter(date__gte=start_date)
    if end_date:
        credit_qs = credit_qs.filter(date__lte=end_date)

    total_credit_notes = credit_qs.aggregate(total=Sum('total_amount'))['total'] or Decimal(0)
    total_credit_note_tax = credit_qs.aggregate(
        tax=Sum(F('creditnote_items__amount') * (F('creditnote_items__gstTaxRate__rate') / 100), output_field=DecimalField())
    )['tax'] or Decimal(0)

    # 3. Purchases (+)
    purchase_qs = Purchase.objects.filter(business=business)
    
    # Apply date filter if dates are provided
    if start_date:
        purchase_qs = purchase_qs.filter(date__gte=start_date)
    if end_date:
        purchase_qs = purchase_qs.filter(date__lte=end_date)

    total_purchases = purchase_qs.aggregate(total=Sum('total_amount'))['total'] or Decimal(0)
    total_purchase_tax = purchase_qs.aggregate(
        tax=Sum(F('purchase_items__amount') * (F('purchase_items__gstTaxRate__rate') / 100), output_field=DecimalField())
    )['tax'] or Decimal(0)

    # 4. Debit Notes (-)
    debit_qs = DebitNote.objects.filter(business=business)
    
    # Apply date filter if dates are provided
    if start_date:
        debit_qs = debit_qs.filter(date__gte=start_date)
    if end_date:
        debit_qs = debit_qs.filter(date__lte=end_date)

    total_debit_notes = debit_qs.aggregate(total=Sum('total_amount'))['total'] or Decimal(0)
    total_debit_note_tax = debit_qs.aggregate(
        tax=Sum(F('debitnote_items__amount') * (F('debitnote_items__gstTaxRate__rate') / 100), output_field=DecimalField())
    )['tax'] or Decimal(0)

    # 5. Tax Payable (-)
    total_tax_payable = total_sales_tax - total_credit_note_tax

    # 6. Tax Receivable (+)
    total_tax_receivable = total_purchase_tax - total_debit_note_tax

    # 7. Stock Calculations
    items = Item.objects.filter(business=business, itemType='Product')
    opening_stock = closing_stock = Decimal(0)

    for item in items:
        def get_purchase_price_without_tax(item):
            if item.purchasePriceType == "With Tax":
                return item.calculate_price(item.purchasePrice, "With Tax")
            return item.purchasePrice or Decimal(0)

        price = get_purchase_price_without_tax(item)
        opening_stock += (item.openingStock or 0) * price
        closing_stock += (item.closingStock or 0) * price

    # 8. Gross Profit
    cogs = total_purchases - total_debit_notes
    gross_profit = total_sales - cogs

    # 9 & 10. Other Income & Net Profit
    other_income = Decimal(0)
    indirect_expenses = Decimal(0)
    net_profit = gross_profit - indirect_expenses + other_income

    # Return the response including the totals and date range
    return JsonResponse({
        
        'total_sales': round(total_sales, 2),
        'total_credit_notes': round(total_credit_notes, 2),
        'total_purchases': round(total_purchases, 2),
        'total_debit_notes': round(total_debit_notes, 2),
        'total_tax_payable': round(total_tax_payable, 2),
        'total_tax_receivable': round(total_tax_receivable, 2),
        'opening_stock': round(opening_stock, 2),
        'closing_stock': round(closing_stock, 2),
        'gross_profit': round(gross_profit, 2),
        'other_income': round(other_income, 2),
        'indirect_expenses': round(indirect_expenses, 2),
        'net_profit': round(net_profit, 2),
    }, safe=False)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def gstr_1(request):
    business = get_current_business(request.user)

    # Get distinct party IDs from invoices for this business
    used_party_ids = Invoice.objects.filter(business=business).values_list('party', flat=True).distinct()

    # Fetch relevant party details
    party_data = Party.objects.filter(id__in=used_party_ids).annotate(
        GSTIN=F('gstin'),
        Customer_Name=F('party_name'),
        state_code=Value(" ", output_field=CharField()),  # Placeholder for actual state code
        state_name=Value("", output_field=CharField())    # Placeholder for actual state name
    ).values('id', 'GSTIN', 'Customer_Name', 'state_code', 'state_name')

    party_map = {party['id']: party for party in party_data}

    # Fetch and annotate invoice data for this business
    invoices = Invoice.objects.filter(business=business).annotate(
        taxableAmount=Sum(
            F('invoice_items__amount') / (1 + F('invoice_items__gstTaxRate__rate') / 100),
            output_field=DecimalField()
        ),
        total_tax=Sum(
            F('invoice_items__amount') - (F('invoice_items__amount') / (1 + F('invoice_items__gstTaxRate__rate') / 100)),
            output_field=DecimalField()
        ),
        cgst=Sum(F('invoice_items__amount') * F('invoice_items__gstTaxRate__rate') / 200, output_field=DecimalField()),
        sgst=Sum(F('invoice_items__amount') * F('invoice_items__gstTaxRate__rate') / 200, output_field=DecimalField()),
        igst=Sum(F('invoice_items__amount') * F('invoice_items__gstTaxRate__rate') / 100, output_field=DecimalField()),
        cess=Sum(F('invoice_items__amount') * F('invoice_items__gstTaxRate__cess_rate') / 100, output_field=DecimalField())
    ).values(
        'invoice_no', 'date', 'total_amount', 'party',
        'cgst', 'sgst', 'igst', 'cess', 'taxableAmount', 'total_tax'
    )

    # Process invoice records
    sales_data = []
    seen_invoice_nos = set()

    for invoice in invoices:
        if invoice['invoice_no'] not in seen_invoice_nos:
            seen_invoice_nos.add(invoice['invoice_no'])
            party = party_map.get(invoice['party'])

            if party:
                sales_data.append({
                    **party,
                    'invoice_no': invoice['invoice_no'],
                    'invoice_date':invoice['date'],
                    'invoice_value': round(float(invoice['total_amount'] or 0), 2),
                    'taxable_amount': round(float(invoice['taxableAmount'] or 0), 2),
                    'cgst': round(float(invoice['cgst'] or 0), 2),
                    'sgst': round(float(invoice['sgst'] or 0), 2),
                    'igst': round(float(invoice['igst'] or 0), 2),
                    'cess': round(float(invoice['cess'] or 0), 2),
                    'total_tax': round(float(invoice['total_tax'] or 0), 2),
                    'total_tax_percentage': round(
                        (float(invoice['total_tax'] or 0) / float(invoice['taxableAmount'] or 1)) * 100, 0
                    ),
                })

    return JsonResponse({'sales_data': sales_data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def gst_purchase_with_hsn(request):
    business = get_current_business(request.user)

    # Prefetch data relevant to the current business
    purchases_data = Purchase.objects.filter(business=business).prefetch_related(
        'purchase_items',
        'purchase_items__item',
        'purchase_items__gstTaxRate'
    ).annotate(
        Invoice_no=F('purchase_no'),
        Original_invoice_no=F('original_invoice_no'),
        tid=F('id'),
        party_name=F('party__party_name'),
        party_gstin=F('party__gstin'),
    )

    filtered_purchases = []

    for purchase in purchases_data:
        for purchase_item in purchase.purchase_items.all():
            item = purchase_item.item
            tax_rate_obj = purchase_item.gstTaxRate

            if item and item.hsnCode:
                unit_price = purchase_item.unit_price
                amount = purchase_item.get_amount()

                # Safely calculate taxes
                if tax_rate_obj:
                    tax_rate = tax_rate_obj.rate / 100
                    cess_rate = tax_rate_obj.cess_rate / 100

                    cgst = round(unit_price * (tax_rate / 2), 2)
                    sgst = round(unit_price * (tax_rate / 2), 2)
                    igst = round(unit_price * tax_rate, 2)
                    cess = round(unit_price * cess_rate, 2)
                else:
                    cgst = sgst = igst = cess = 0.00

                filtered_purchases.append({
                    'Invoice_no': purchase.Invoice_no,
                    'Original_invoice_no': purchase.Original_invoice_no,
                    'tid': purchase.tid,
                    'date': purchase.date,
                    'party_name': purchase.party_name,
                    'party_gstin': purchase.party_gstin,
                    'item_name': item.itemName,
                    'hsn_code': item.hsnCode,
                    'Quantity': purchase_item.quantity,
                    'unit_price': unit_price,
                    'cgst': cgst,
                    'sgst': sgst,
                    'igst': igst,
                    'cess': cess,
                    'amount': amount
                })

    return JsonResponse({'purchases': filtered_purchases})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def gst_sales_with_hsn(request):
    business = get_current_business(request.user)

    # Prefetch related fields for efficiency
    sales_data = Invoice.objects.filter(business=business).prefetch_related(
        'invoice_items',
        'invoice_items__item',
        'invoice_items__gstTaxRate'
    ).annotate(
        Invoice_no=F('invoice_no'),
        party_name=F('party__party_name'),
        party_gstin=F('party__gstin'),
    )

    filtered_invoices = []

    for invoice in sales_data:
        for invoice_item in invoice.invoice_items.all():
            item = invoice_item.item
            tax_rate_obj = invoice_item.gstTaxRate

            if item and item.hsnCode:
                unit_price = invoice_item.unit_price
                amount = invoice_item.get_amount()

                if tax_rate_obj:
                    tax_rate = tax_rate_obj.rate / 100
                    cess_rate = tax_rate_obj.cess_rate / 100

                    cgst = round(unit_price * (tax_rate / 2), 2)
                    sgst = round(unit_price * (tax_rate / 2), 2)
                    igst = round(unit_price * tax_rate, 2)
                    cess = round(unit_price * cess_rate, 2)
                else:
                    cgst = sgst = igst = cess = 0.00

                filtered_invoices.append({
                    'Invoice_no': invoice.Invoice_no,
                    'id': invoice.id,
                    'party_name': invoice.party_name,
                    'party_gstin': invoice.party_gstin,
                    'date': invoice.date,
                    'item_name': item.itemName,
                    'hsn_code': item.hsnCode,
                    'Quantity': invoice_item.quantity,
                    'unit_price': unit_price,
                    'cgst': cgst,
                    'sgst': sgst,
                    'igst': igst,
                    'cess': cess,
                    'amount': amount
                })

    return JsonResponse({'invoices': filtered_invoices})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def hsn_wise_sales_summary(request):
    business = get_current_business(request.user)

    sales_data = Invoice.objects.filter(business=business).prefetch_related(
        'invoice_items',
        'invoice_items__item',
        'invoice_items__gstTaxRate'
    ).annotate(
        Invoice_no=F('invoice_no'),
        Date=F('date'),
        party_name=F('party__party_name'),
        party_gstin=F('party__gstin'),
    )

    filtered_invoices = []

    for invoice in sales_data:
        for invoice_item in invoice.invoice_items.all():
            item = invoice_item.item
            tax_rate_obj = invoice_item.gstTaxRate

            if item and item.hsnCode:
                unit_price = invoice_item.unit_price
                taxable_value = invoice_item.get_price_item()
                amount = invoice_item.get_amount()
                taxable_amount = invoice_item.get_tax_rate_amount()
                cgst_amount = invoice_item.get_cgst_amount()
                sgst_amount = invoice_item.get_sgst_amount()
                igst_amount = invoice_item.get_igst_amount()

                if tax_rate_obj:
                    tax_rate = tax_rate_obj.rate / 100
                    cess_rate = tax_rate_obj.cess_rate / 100
                    cess = round(unit_price * cess_rate, 2)
                else:
                    cess = 0.00

                filtered_invoices.append({
                    'date': invoice.date,
                    'hsn_code': item.hsnCode,
                    'item_name': item.itemName,
                    'Quantity': invoice_item.quantity,
                    'total_value': amount,
                    'taxable_value': taxable_value,
                    'cgst': round(cgst_amount, 2),
                    'sgst': round(sgst_amount, 2),
                    'igst': round(igst_amount, 2),
                    'cess': cess,
                    'total_taxable_amount': round(taxable_amount, 2),
                })

    return JsonResponse({'invoices': filtered_invoices})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def gstr_2_purchase(request):
    business = get_current_business(request.user)

    purchases_data = Purchase.objects.filter(business=business).prefetch_related(
        'purchase_items',
        'purchase_items__gstTaxRate',
        'party'
    ).all()

    purchase_returns_data = PurchaseReturn.objects.filter(business=business).prefetch_related(
        'purchasereturn_items',
        'purchasereturn_items__gstTaxRate',
        'party'
    ).all()

    filtered_purchases = []
    filtered_purchase_returns = []

    # Process Purchases
    for purchase in purchases_data:
        total_invoice_value = purchase.get_total_amount()
        total_taxable_value = purchase.get_taxable_amount()

        total_cgst = Decimal(0)
        total_sgst = Decimal(0)
        total_igst = Decimal(0)
        total_cess = Decimal(0)
        total_tax = Decimal(0)
        tax_rate_percentage = 0

        for purchase_item in purchase.purchase_items.all():
            if purchase_item.gstTaxRate:
                rate = purchase_item.gstTaxRate.rate / 100
                cess_rate = purchase_item.gstTaxRate.cess_rate / 100
                unit_price = purchase_item.unit_price
                tax_rate_percentage = purchase_item.gstTaxRate.rate

                total_tax += purchase_item.get_tax_rate_amount()
                total_cgst += round(unit_price * (rate / 2), 2)
                total_sgst += round(unit_price * (rate / 2), 2)
                total_igst += round(unit_price * rate, 2)
                total_cess += round(unit_price * cess_rate, 2)

        filtered_purchases.append({
            'gstin': purchase.party.gstin if purchase.party else "",
            'customer_name': purchase.party.party_name if purchase.party else "",
            'state_code': "",
            'state_name': "",
            'Invoice_no': purchase.purchase_no,
            'Original_invoice_no': purchase.original_invoice_no,
            'date': purchase.date,
            'invoice_value': round(total_invoice_value, 2),
            'total_taxable_value': round(total_taxable_value, 2),
            'total_tax_percentage': round(tax_rate_percentage, 0),
            'cgst': round(total_cgst, 2),
            'sgst': round(total_sgst, 2),
            'igst': round(total_igst, 2),
            'cess': round(total_cess, 2),
            'total_tax': round(total_tax, 2),
        })

    # Process Purchase Returns
    for purchasereturn in purchase_returns_data:
        total_invoice_value = purchasereturn.get_total_amount()
        total_taxable_value = purchasereturn.get_taxable_amount()

        total_cgst = Decimal(0)
        total_sgst = Decimal(0)
        total_igst = Decimal(0)
        total_cess = Decimal(0)
        total_tax = Decimal(0)
        tax_rate_percentage = 0

        for item in purchasereturn.purchasereturn_items.all():
            if item.gstTaxRate:
                rate = item.gstTaxRate.rate / 100
                cess_rate = item.gstTaxRate.cess_rate / 100
                unit_price = item.unit_price
                tax_rate_percentage = item.gstTaxRate.rate

                total_tax += item.get_tax_rate_amount()
                total_cgst += round(unit_price * (rate / 2), 2)
                total_sgst += round(unit_price * (rate / 2), 2)
                total_igst += round(unit_price * rate, 2)
                total_cess += round(unit_price * cess_rate, 2)

        filtered_purchase_returns.append({
            'gstin': purchasereturn.party.gstin if purchasereturn.party else "",
            'customer_name': purchasereturn.party.party_name if purchasereturn.party else "",
            'state_code': "",
            'state_name': "",
            'Invoice_no': purchasereturn.purchasereturn_no,
            'date': purchasereturn.date,
            'invoice_value': round(total_invoice_value, 2),
            'total_taxable_value': round(total_taxable_value, 2),
            'total_tax_percentage': round(tax_rate_percentage, 0),
            'cgst': round(total_cgst, 2),
            'sgst': round(total_sgst, 2),
            'igst': round(total_igst, 2),
            'cess': round(total_cess, 2),
            'total_tax': round(total_tax, 2),
        })

    return JsonResponse({
        'purchases': filtered_purchases,
        'purchase_returns': filtered_purchase_returns
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tcs_payable(request):
    business = get_current_business(request.user)

    invoices_query = Invoice.objects.filter(
        business=business,
        tcs_amount__gt=0
    ).annotate(
        party_name=F('party__party_name'),
        party_gst=F('party__gstin'),
        party_pan=F('party__pan'),
        Invoice_no=F('invoice_no'),
        Date=F('date'),
        amount=Cast(F('total_amount'), DecimalField()),
        Taxable_amount=Cast(F('taxable_amount'), DecimalField()),
        Tcs_amount=Cast(F('tcs_amount'), DecimalField()),
        tax_name=F('tcs__description'),
        tax_section=F('tcs__section'),
        tax_rate=F('tcs__rate'),
        source=Value('Invoice')
    ).values(
        'party_name', 'party_gst', 'party_pan',
        'Invoice_no', 'Date', 'amount', 'Taxable_amount',
        'Tcs_amount', 'tax_name', 'tax_section', 'tax_rate', 'source'
    )

    credit_notes_query = CreditNote.objects.filter(
        business=business,
        tcs_amount__gt=0
    ).annotate(
        party_name=F('party__party_name'),
        party_gst=F('party__gstin'),
        party_pan=F('party__pan'),
        invoice_no=F('credit_note_no'),
        Date=F('date'),
        amount=Cast(F('total_amount'), DecimalField()),
        Taxable_amount=Cast(F('taxable_amount'), DecimalField()),
        Tcs_amount=Cast(F('tcs_amount'), DecimalField()),
        tax_name=F('tcs__description'),
        tax_section=F('tcs__section'),
        tax_rate=F('tcs__rate'),
        source=Value('Credit Note')
    ).values(
        'party_name', 'party_gst', 'party_pan',
        'invoice_no', 'Date', 'amount', 'Taxable_amount',
        'Tcs_amount', 'tax_name', 'tax_section', 'tax_rate', 'source'
    )

    # Combine and format dates
    combined = list(invoices_query) + list(credit_notes_query)
    for item in combined:
        if isinstance(item['Date'], datetime):
            item['date'] = item['Date'].strftime('%Y-%m-%d')

    return JsonResponse({'transactions': combined}, safe=False)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tcs_receivable(request):
    business = get_current_business(request.user)

    purchases_query = Purchase.objects.filter(
        business=business,
        tcs_amount__gt=0
    ).annotate(
        party_name=F('party__party_name'),
        party_gst=F('party__gstin'),
        party_pan=F('party__pan'),
        invoice_no=F('purchase_no'),
        Date=F('date'),
        amount=F('total_amount'),
        taxableAmount=F('taxable_amount'),
        tcsAmount=F('tcs_amount'),
        tax_name=F('tcs__description'),
        tax_section=F('tcs__section'),
        tax_rate=F('tcs__rate'),
    ).values(
        'party_name', 'party_gst', 'party_pan',
        'invoice_no', 'Date', 'amount', 'taxableAmount',
        'tcsAmount', 'tax_name', 'tax_section', 'tax_rate'
    ).order_by('-date')

    # Debit Notes with TCS
    debit_notes_query = DebitNote.objects.filter(
        business=business,
        tcs_amount__gt=0
    ).annotate(
        party_name=F('party__party_name'),
        party_gst=F('party__gstin'),
        party_pan=F('party__pan'),
        invoice_no=F('debitnote_no'),
        Date=F('date'),
        amount=F('total_amount'),
        taxableAmount=F('taxable_amount'),
        tcsAmount=F('tcs_amount'),
        tax_name=F('tcs__description'),
        tax_section=F('tcs__section'),
        tax_rate=F('tcs__rate'),
        source=Value('Debit Note')
    ).values(
        'party_name', 'party_gst', 'party_pan',
        'invoice_no', 'Date', 'amount', 'taxableAmount',
        'tcsAmount', 'tax_name', 'tax_section', 'tax_rate', 'source'
    )

    # Combine and sort by date
    combined = list(purchases_query) + list(debit_notes_query)
    combined_sorted = sorted(combined, key=lambda x: x['Date'], reverse=True)

    return JsonResponse({'transactions': combined_sorted}, safe=False)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tds_receivable(request):
    business = get_current_business(request.user)

    invoices_query = PaymentInInvoice.objects.filter(
        payment_in__business=business,
        tds_amount__gt=0
    ).annotate(
        party_name=F('payment_in__party__party_name'),
        party_gst=F('payment_in__party__gstin'),
        party_pan=F('payment_in__party__pan'),
        Invoice_no=F('payment_in__payment_in_number'),
        Date=F('payment_in__date'),
        Amount=F('invoice_amount'),
        Tds_Amount=F('tds_amount'),
        Tax_rate=F('tds_rate')
    ).values(
        'party_name',
        'party_gst',
        'party_pan',
        'Invoice_no',
        'Date',         # ✅ matches annotation
        'Amount',
        'Tds_Amount',
        'Tax_rate'
    ).order_by('-Date')

    return JsonResponse({
        'transactions': list(invoices_query)
    }, safe=False)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tds_payable(request):
    # Start building the query
    business = get_current_business(request.user)
    invoices_query = Purchase.objects.filter(
    business=business,
    tds_amount__gt=0
).annotate(
    party_name=F('party__party_name'),
    party_gst=F('party__gstin'),
    party_pan=F('party__pan'),
    Invoice_no=F('purchase_no'),
    Date=F('date'),  # 👈 Consistent with debit note
    amount=F('total_amount'),
    Tds_Amount=F('tds_amount'),
    Tax_name=F('tds__description'),
    Tax_section=F('tds__section'),
    Tax_rate=F('tds__rate'),
).values(
    'party_name', 'party_gst', 'party_pan', 'Invoice_no',
    'amount', 'Tds_Amount', 'Tax_name', 'Tax_section',
    'Tax_rate', 'Date'  # 👈 not 'date'
)
    # Debit notes with TDS
    debit_note_query = DebitNote.objects.filter(
        business=business,
        tds_amount__gt=0
    ).annotate(
        party_name=F('party__party_name'),
        party_gst=F('party__gstin'),
        party_pan=F('party__pan'),
        Invoice_no=F('debitnote_no'),
        Date=F('date'),
        amount=F('total_amount'),
        tdsAmount=F('tds_amount'),
        Tax_name=F('tds__description'),
        Tax_section=F('tds__section'),
        Tax_rate=F('tds__rate'),
        source=Value('Debit Note')
    ).values(
        'party_name', 'party_gst', 'party_pan', 'Invoice_no',
        'amount', 'tdsAmount', 'Tax_name', 'Tax_section',
        'Tax_rate', 'Date', 'source'
    )

    # Combine both querysets
    combined = list(invoices_query) + list(debit_note_query)

    # Sort combined data by date descending
    combined_sorted = sorted(combined, key=lambda x: x['Date'], reverse=True)

    return JsonResponse({
        'transactions': combined_sorted
    }, safe=False)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def audit_trial(request):
    business = get_current_business(request.user)
    
    # Get date range from query parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Base queryset with filters to exclude internal updates
    audit_trails = AuditTrail.objects.filter(
        business=business
    ).exclude(
        model_name__in=['AuditLog', 'AuditTrail']  # Exclude audit-related models
    ).exclude(
        action__startswith='Updated'  # Exclude update actions
    )
    
    # Apply date filters if provided
    if start_date:
        audit_trails = audit_trails.filter(date__gte=start_date)
    if end_date:
        audit_trails = audit_trails.filter(date__lte=end_date)
    
    # Get the data
    audit_data = audit_trails.values(
        'date',
        'voucher_no',
        'action',
        'user__name',
        'model_name',
        'record_id',
        'old_values',
        'new_values'
    ).order_by('-date')
    
    # Format the data for frontend with deduplication
    formatted_data = []
    seen_entries = set()  # To track unique entries
    
    for trail in audit_data:
        # Create a unique key for each entry
        entry_key = (
            str(trail['date']),
            trail['voucher_no'],
            trail['action'],
            trail['user__name'],
            trail['model_name'],
            str(trail['record_id'])
        )
        
        # Only add if we haven't seen this combination before
        if entry_key not in seen_entries:
            seen_entries.add(entry_key)
            # Format the date to YYYY-MM-DD
            formatted_date = trail['date'].strftime('%Y-%m-%d')
            
            formatted_data.append({
                'date': formatted_date,
                'voucher_no': trail['voucher_no'],
                'action': trail['action'],
                'by_user': trail['user__name'],
                'model_name': trail['model_name'],
                'record_id': trail['record_id'],
                'old_values': trail['old_values'],
                'new_values': trail['new_values']
            })
    
    return JsonResponse({'transactions': formatted_data}, safe=False)


def round_nested_dict(d):
    for key, value in d.items():
        if isinstance(value, dict):
            round_nested_dict(value)
        elif isinstance(value, (int, float, Decimal)):
            d[key] = round(value, 2)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def gstr_3b(request):
    business = get_current_business(request.user)
    business_state = business.state

    # Get date range from query parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # Base queryset with date filtering
    base_filter = {'business': business}
    if start_date:
        base_filter['date__gte'] = parse_date(start_date)
    if end_date:
        base_filter['date__lte'] = parse_date(end_date)

    # Get invoices within date range
    invoices = Invoice.objects.filter(**base_filter)
    # print(f"Found {invoices.count()} invoices for date range {start_date} to {end_date}")

    totals = {
        '3_1_a': {'taxable': Decimal('0'), 'igst': Decimal('0'), 'cgst': Decimal('0'), 'sgst': Decimal('0'), 'cess': Decimal('0')},
        '3_1_b': {'taxable': Decimal('0')},
        '3_1_c': {'taxable': Decimal('0')},
        '3_1_d': {'taxable': Decimal('0'), 'igst': Decimal('0'), 'cgst': Decimal('0'), 'sgst': Decimal('0'), 'cess': Decimal('0')},
        '3_1_e': {'taxable': Decimal('0')},
        '3_2': {
            'details of inter state supplies made to unregistered persons, composition dealers and UIN holders': {
                'unregistered': {},
                'composition': {},
                'uin': {}
            }
        },
        '4': {
            'import_of_goods': {'igst': Decimal('0'), 'cgst': Decimal('0'), 'sgst': Decimal('0'), 'cess': Decimal('0')},
            'import_of_services': {'igst': Decimal('0'), 'cgst': Decimal('0'), 'sgst': Decimal('0'), 'cess': Decimal('0')},
            'inward_reverse_charge': {'igst': Decimal('0'), 'cgst': Decimal('0'), 'sgst': Decimal('0'), 'cess': Decimal('0')},
            'inward_for_isd': {'igst': Decimal('0'), 'cgst': Decimal('0'), 'sgst': Decimal('0'), 'cess': Decimal('0')},
            'other_itc': {'igst': Decimal('0'), 'cgst': Decimal('0'), 'sgst': Decimal('0'), 'cess': Decimal('0')},
            'ineligible_itc': {'igst': Decimal('0'), 'cgst': Decimal('0'), 'sgst': Decimal('0'), 'cess': Decimal('0')},
            'others': {'igst': Decimal('0'), 'cgst': Decimal('0'), 'sgst': Decimal('0'), 'cess': Decimal('0')}
        },
        '5': {
            'composition_scheme, export_nil_rated': {'inter_state': Decimal('0'), 'intra_state': Decimal('0')},
            'non_gst': {'inter_state': Decimal('0'), 'intra_state': Decimal('0')}
        }
    }

    # Process invoices
    for invoice in invoices:
        is_inter_state = invoice.party.state != business_state
        is_registered = bool(invoice.party.gstin)
        is_composition = getattr(invoice.party, 'is_composition', False)
        is_uin = getattr(invoice.party, 'is_uin', False)

        taxable = invoice.taxable_amount or Decimal('0')
        igst = cgst = sgst = cess = Decimal('0')

        for item in invoice.invoice_items.all():
            if item.gstTaxRate:
                rate = item.gstTaxRate.rate
                cess_rate = item.gstTaxRate.cess_rate

                value = Decimal(str(item.amount))
                base = value / (1 + rate / 100) if rate else value
                tax_amount = value - base
                cess_amount = base * (cess_rate / 100)

                if is_inter_state:
                    igst += tax_amount
                else:
                    cgst += tax_amount / 2
                    sgst += tax_amount / 2

                cess += cess_amount
                taxable += base

        # Categorize based on invoice type
        if getattr(invoice, 'is_reverse_charge', False):
            totals['3_1_d']['taxable'] += taxable
            totals['3_1_d']['igst'] += igst
            totals['3_1_d']['cgst'] += cgst
            totals['3_1_d']['sgst'] += sgst
            totals['3_1_d']['cess'] += cess
        elif getattr(invoice, 'is_zero_rated', False):
            totals['3_1_b']['taxable'] += taxable
        elif getattr(invoice, 'is_exempt', False):
            totals['3_1_c']['taxable'] += taxable
        elif getattr(invoice, 'is_non_gst', False):
            totals['3_1_e']['taxable'] += taxable
        else:
            totals['3_1_a']['taxable'] += taxable
            totals['3_1_a']['igst'] += igst
            totals['3_1_a']['cgst'] += cgst
            totals['3_1_a']['sgst'] += sgst
            totals['3_1_a']['cess'] += cess

        # Handle inter-state supplies
        if is_inter_state:
            pos = invoice.party.state
            if not is_registered:
                if pos not in totals['3_2']['details of inter state supplies made to unregistered persons, composition dealers and UIN holders']['unregistered']:
                    totals['3_2']['details of inter state supplies made to unregistered persons, composition dealers and UIN holders']['unregistered'][pos] = {'taxable': Decimal('0'), 'igst': Decimal('0')}
                totals['3_2']['details of inter state supplies made to unregistered persons, composition dealers and UIN holders']['unregistered'][pos]['taxable'] += taxable
                totals['3_2']['details of inter state supplies made to unregistered persons, composition dealers and UIN holders']['unregistered'][pos]['igst'] += igst
            elif is_composition:
                if pos not in totals['3_2']['details of inter state supplies made to unregistered persons, composition dealers and UIN holders']['composition']:
                    totals['3_2']['details of inter state supplies made to unregistered persons, composition dealers and UIN holders']['composition'][pos] = {'taxable': Decimal('0'), 'igst': Decimal('0')}
                totals['3_2']['details of inter state supplies made to unregistered persons, composition dealers and UIN holders']['composition'][pos]['taxable'] += taxable
                totals['3_2']['details of inter state supplies made to unregistered persons, composition dealers and UIN holders']['composition'][pos]['igst'] += igst
            elif is_uin:
                if pos not in totals['3_2']['details of inter state supplies made to unregistered persons, composition dealers and UIN holders']['uin']:
                    totals['3_2']['details of inter state supplies made to unregistered persons, composition dealers and UIN holders']['uin'][pos] = {'taxable': Decimal('0'), 'igst': Decimal('0')}
                totals['3_2']['details of inter state supplies made to unregistered persons, composition dealers and UIN holders']['uin'][pos]['taxable'] += taxable
                totals['3_2']['details of inter state supplies made to unregistered persons, composition dealers and UIN holders']['uin'][pos]['igst'] += igst

    # Process purchases for ITC
    purchases = Purchase.objects.filter(**base_filter)
    # print(f"Found {purchases.count()} purchases for date range {start_date} to {end_date}")
    
    for purchase in purchases:
        is_import = getattr(purchase, 'is_import', False)
        is_service = getattr(purchase, 'is_service', False)
        is_reverse_charge = getattr(purchase, 'is_reverse_charge', False)
        is_isd = getattr(purchase, 'is_isd', False)
        is_inter_state = purchase.party.state != business_state  # <-- Added

        for item in purchase.purchase_items.all():
            if item.gstTaxRate:
                rate = item.gstTaxRate.rate
                cess_rate = item.gstTaxRate.cess_rate

                value = Decimal(str(item.amount))
                base = value / (1 + rate / 100) if rate else value
                tax_amount = value - base
                cess_amount = base * (cess_rate / 100)

                if is_import:
                    if is_service:
                        totals['4']['import_of_services']['igst'] += tax_amount
                        totals['4']['import_of_services']['cess'] += cess_amount
                    else:
                        totals['4']['import_of_goods']['igst'] += tax_amount
                        totals['4']['import_of_goods']['cess'] += cess_amount
                elif is_reverse_charge:
                    if is_inter_state:
                        totals['4']['inward_reverse_charge']['igst'] += tax_amount
                    else:
                        totals['4']['inward_reverse_charge']['cgst'] += tax_amount / 2
                        totals['4']['inward_reverse_charge']['sgst'] += tax_amount / 2
                    totals['4']['inward_reverse_charge']['cess'] += cess_amount
                elif is_isd:
                    if is_inter_state:
                        totals['4']['inward_for_isd']['igst'] += tax_amount
                    else:
                        totals['4']['inward_for_isd']['cgst'] += tax_amount / 2
                        totals['4']['inward_for_isd']['sgst'] += tax_amount / 2
                    totals['4']['inward_for_isd']['cess'] += cess_amount
                else:
                    if is_inter_state:
                        totals['4']['other_itc']['igst'] += tax_amount
                    else:
                        totals['4']['other_itc']['cgst'] += tax_amount / 2
                        totals['4']['other_itc']['sgst'] += tax_amount / 2
                    totals['4']['other_itc']['cess'] += cess_amount

    # Process exempt and non-GST supplies
    for invoice in invoices:
        is_inter_state = invoice.party.state != business_state
        is_composition = getattr(invoice.party, 'is_composition', False)
        is_exempt = getattr(invoice, 'is_exempt', False)
        is_non_gst = getattr(invoice, 'is_non_gst', False)

        if is_composition or is_exempt:
            if is_inter_state:
                totals['5']['composition_scheme, export_nil_rated']['inter_state'] += invoice.taxable_amount or Decimal('0')
            else:
                totals['5']['composition_scheme, export_nil_rated']['intra_state'] += invoice.taxable_amount or Decimal('0')
        elif is_non_gst:
            if is_inter_state:
                totals['5']['non_gst']['inter_state'] += invoice.taxable_amount or Decimal('0')
            else:
                totals['5']['non_gst']['intra_state'] += invoice.taxable_amount or Decimal('0')

    # Round all values
    round_nested_dict(totals)
    
    # Print debug information
    # print("Final totals:", totals)
    
    return JsonResponse({
        '3.1(a) Outward taxable supplies (other than zero-rated, nil, exempt)': totals['3_1_a'],
        '3.1(b) Outward taxable supplies (zero-rated)': totals['3_1_b'],
        '3.1(c) Other outward supplies (nil-rated, exempt)': totals['3_1_c'],
        '3.1(d) Inward supplies (reverse charge)': totals['3_1_d'],
        '3.1(e) Non-GST outward supplies': totals['3_1_e'],
        '3.2 Eligible ITC and Inter-State Supplies': totals['3_2'],
        '4 Eligible ITC Breakdown': totals['4'],
        '5 Exempt / Nil-rated / Non-GST Inward Supplies': totals['5'],
    }, safe=False)
