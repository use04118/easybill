from django.urls import path
from .views import InvoiceListCreateView, InvoiceDetailView, QuotationListCreateView, QuotationDetailView,ProformaDetailView,ProformaListCreateView,SalesReturnListCreateView,SalesReturnDetailView, PaymentInListCreateView,PaymentInDetailView,CreditNoteListCreateView,CreditNoteDetailView,DeliveryChallanListCreateView, DeliveryChallanDetailView,get_paid, get_unpaid, get_next_invoice_number,get_next_quotation_number,get_next_salesreturn_number,get_next_payment_in_number,get_next_creditnote_number,get_next_deliverychallan_number,get_next_proforma_number
from . import views
from .views import (
    TcsListCreateView, TcsDetailView,
    TdsListCreateView, TdsDetailView,
    business_tax_flags , settled_invoices
)

urlpatterns = [
    path('invoices/', InvoiceListCreateView.as_view(), name='invoice-list'),
    path('invoices/<int:pk>/', InvoiceDetailView.as_view(), name='invoice-detail'),
    path('invoices/next-number/', get_next_invoice_number, name='next-invoice-number'),
    
    path('quotation/', QuotationListCreateView.as_view(), name='quotation-list'),
    path('quotation/<int:pk>/', QuotationDetailView.as_view(), name='quotation-detail'),  # Handles GET, PUT, PATCH, DELETE
    path('convert-quotation-to-invoice/<int:pk>/', views.convert_quotation_to_invoice, name='convert-quotation-to-invoice'),
    path('quotation/next-number/', get_next_quotation_number, name='next-quotation-number'),

    path('salesreturn/', SalesReturnListCreateView.as_view(), name='salesreturn-list'),
    path('salesreturn/<int:pk>/', SalesReturnDetailView.as_view(), name='salesreturn-detail'),  # Handles GET, PUT, PATCH, DELETE
    path('salesreturn/next-number/', get_next_salesreturn_number, name='next-salesreturn-number'),

    path('paymentin/', PaymentInListCreateView.as_view(), name='paymentin-list'),
    path('paymentin/<int:pk>/', PaymentInDetailView.as_view(), name='payment-detail'),  # Handles GET, PUT, PATCH, DELETE
    path('payments/settled/<str:payment_in_number>/', settled_invoices, name='settled-invoices'),
    path('payment_in/next-number/', get_next_payment_in_number, name='next-payment_in-number'),

    path('creditnote/', CreditNoteListCreateView.as_view(), name='creditnote-list'),
    path('creditnote/<int:pk>/', CreditNoteDetailView.as_view(), name='creditnote-detail'),  # Handles GET, PUT, PATCH, DELETE
    path('creditnote/next-number/', get_next_creditnote_number, name='next-creditnote-number'),

    path('deliverychallan/', DeliveryChallanListCreateView.as_view(), name='deliverychallan-list'),
    path('deliverychallan/<int:pk>/', DeliveryChallanDetailView.as_view(), name='deliverychallan-detail'),  # Handles GET, PUT, PATCH, DELETE
    path('convert-deliverychallan-to-invoice/<int:pk>/', views.convert_deliverychallan_to_invoice, name='convert-deliverychallan-to-invoicedeliverychallan'),
    path('deliverychallan/next-number/', get_next_deliverychallan_number, name='next-deliverychallan-number'),

    path('proforma/', ProformaListCreateView.as_view(), name='proforma-list'),
    path('proforma/<int:pk>/', ProformaDetailView.as_view(), name='proforma-detail'),  # Handles GET, PUT, PATCH, DELETE
    path('convert-proforma-to-invoice/<int:pk>/', views.convert_proforma_to_invoice, name='convert-proforma-to-invoice'),
    path('proforma/next-number/', get_next_proforma_number, name='next-proforma-number'),

    path('invoice/paid/', get_paid, name='get-paid'),
    path('invoice/unpaid/', get_unpaid, name='get-unpaid'),
    
    # TCS
    path('tcs/', TcsListCreateView.as_view(), name='tcs-list-create'),
    path('tcs/<int:pk>/', TcsDetailView.as_view(), name='tcs-detail'),

    # TDS
    path('tds/', TdsListCreateView.as_view(), name='tds-list-create'),
    path('tds/<int:pk>/', TdsDetailView.as_view(), name='tds-detail'),

    # Current Business TCS/TDS Config (For Frontend)
    path('settings/tcs-tds/',business_tax_flags , name='business-tcs-tds-settings'),
]
