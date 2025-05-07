from django.urls import path
from .views import PurchaseListCreateView, PurchaseDetailView, PurchaseListView, PurchaseReturnListCreateView,PurchaseReturnDetailView, PaymentOutListCreateView,PaymentOutDetailView,DebitNoteListCreateView, DebitNoteDetailView,PurchaseOrdersListCreateView, PurchaseOrdersDetailView,get_paid,get_unpaid,convert_purchaseorder_to_invoice 

from .views import (
   settled_purchase,get_next_purchase_debit_number,get_next_purchase_number,get_next_purchase_order_number,get_next_payment_out_number,get_next_purchase_return_number
)

urlpatterns = [
    path('purchase/',PurchaseListCreateView.as_view(), name='purchase-list'),
    path('purchase/<int:pk>/',PurchaseDetailView.as_view(), name='purchase-detail'),# Handles GET, PUT, PATCH, DELETE
    path('all-purchase/', PurchaseListView.as_view(), name='purchase-list'),
    path('purchase/next-number/', get_next_purchase_number, name='next-purchase-number'),
    
    path('purchasereturn/', PurchaseReturnListCreateView.as_view(), name='purchasereturn-list'),
    path('purchasereturn/<int:pk>/', PurchaseReturnDetailView.as_view(), name='purchasereturn-detail'),  # Handles GET, PUT, PATCH, DELETE
    path('purchasereturn/next-number/', get_next_purchase_return_number, name='next-purchase-return-number'),
    
    path('paymentout/', PaymentOutListCreateView.as_view(), name='paymentout-list'),
    path('paymentout/<int:pk>/', PaymentOutDetailView.as_view(), name='paymentout-detail'),  # Handles GET, PUT, PATCH, DELETE
    path('payments/settled/<str:payment_out_number>/', settled_purchase, name='settled-invoices'),
    path('paymentout/next-number/', get_next_payment_out_number, name='next-payment-out-number'),
    
    path('debitnote/', DebitNoteListCreateView.as_view(), name='debitnote-list'),
    path('debitnote/<int:pk>/', DebitNoteDetailView.as_view(), name='debitnote-detail'),  # Handles GET, PUT, PATCH, DELETE
    path('debitnote/next-number/', get_next_purchase_debit_number, name='next-purchase-debit-number'),
    
    path('purchaseorder/', PurchaseOrdersListCreateView.as_view(), name='purchaseorder-list'),
    path('purchaseorder/<int:pk>/', PurchaseOrdersDetailView.as_view(), name='purchaseorder-detail'),  # Handles GET, PUT, PATCH, DELETE
    path('convert-purchaseorder-to-invoice/<int:pk>/', convert_purchaseorder_to_invoice, name='convert-purchaseorder-to-invoice'),
    path('purchaseorder/next-number/', get_next_purchase_order_number, name='next-purchase-order-number'),
    
    path('purchase/paid/', get_paid, name='get-paid'),
    path('purchase/unpaid/', get_unpaid, name='get-unpaid'),
   
]