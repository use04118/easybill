from django.urls import path
from . import views

urlpatterns = [
    # Automated Invoice Views
    path('automated-invoices/', views.AutomatedInvoiceListCreateView.as_view(), name='automated_invoice_list_create'),
    path('automated-invoices/<int:pk>/', views.AutomatedInvoiceDetailView.as_view(), name='automated_invoice_detail'),

    # Automated Invoice Item Views
    path('automated-invoice-items/', views.AutomatedInvoiceItemListCreateView.as_view(), name='automated_invoice_item_list_create'),
    path('automated-invoice-items/<int:pk>/', views.AutomatedInvoiceItemDetailView.as_view(), name='automated_invoice_item_detail'),

    # Optional: Trigger generation manually
    # path('generate-invoice/<int:pk>/', views.GenerateInvoiceFromAutomatedView.as_view(), name='generate_invoice'),
    # path('convert-automated-invoice-to-invoice/<int:pk>/', views.convert_automated_invoice_to_invoice, name='convert-automated-invoice-to-invoice'),
]