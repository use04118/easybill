from decimal import Decimal, ROUND_HALF_UP
from .models import PaymentOutPurchase

def apply_payment_to_purchase(payment_out, purchases_data):
    total_remaining = payment_out.amount

    for item in purchases_data:
        purchase = item['purchase']
        settled_amount = item['settled_amount']


        PaymentOutPurchase.objects.create(
            payment_out=payment_out,
            purchase=purchase,
            purchase_amount=purchase.total_amount,
            settled_amount=settled_amount,
        )

        purchase.make_payment(settled_amount)
        total_remaining -= settled_amount

    if total_remaining > 0:
        payment_out.adjust_party_balance(total_remaining)
