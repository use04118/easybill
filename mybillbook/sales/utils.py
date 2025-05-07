from decimal import Decimal, ROUND_HALF_UP
from .models import PaymentInInvoice

def apply_payment_to_invoices(payment_in, invoices_data):
    total_remaining = payment_in.amount

    for item in invoices_data:
        invoice = item['invoice']
        settled_amount = item['settled_amount']
        apply_tds = item.get('apply_tds', False)
        tds_rate = item.get('tds_rate', Decimal("0.00"))
        tds_amount = Decimal("0.00")

        if apply_tds:
            base = invoice.get_taxable_amount()
            tds_amount = (base * tds_rate / Decimal("100.00")).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
            settled_amount = settled_amount + tds_amount
        print(f"1.Settled Amount: {settled_amount}")
        PaymentInInvoice.objects.create(
            payment_in=payment_in,
            invoice=invoice,
            invoice_amount=invoice.total_amount,
            settled_amount=settled_amount,
            apply_tds=apply_tds,
            tds_rate=tds_rate,
            tds_amount=tds_amount,
        )

        invoice.make_payment(settled_amount, bank_account=payment_in.bank_account)
        
        total_remaining = total_remaining - (settled_amount - tds_amount)

    if total_remaining > 0: 
        print(f"Total remaining: {total_remaining}")
        payment_in.adjust_party_balance(total_remaining)
