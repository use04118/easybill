from django.urls import path
from .views import GenerateEWayBillView , GenerateEInvoiceView
from . import views

urlpatterns = [
    path('generate-eway-bill-form/<int:invoice_id>/', views.GenerateEWayBillFormView.as_view(), name='generate_eway_bill_form'),
    path('generate-eway-bill/<int:invoice_id>/', views.GenerateEWayBillView.as_view(), name='generate_eway_bill'),
    path('einvoice/generate/', GenerateEInvoiceView.as_view(), name='generate_einvoice'),
    path('reconciliations/', views.GSTR1ReconciliationListView.as_view(), name='gstr1_reconciliation_list'),
    path('reconciliations/<int:pk>/', views.GSTR1ReconciliationDetailView.as_view(), name='gstr1_reconciliation_detail'),
    path('reconcile_invoices/', views.ReconcileInvoicesView.as_view(), name='reconcile_invoices'),

]
