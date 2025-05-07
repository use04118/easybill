from django.urls import path
from . import views

app_name = 'cash_and_bank'

urlpatterns = [
    # Bank Account URLs
    path('accounts/', views.BankAccountListCreateView.as_view(), name='bank-account-list'),
    path('accounts/<int:pk>/', views.BankAccountDetailView.as_view(), name='bank-account-detail'),
    path('accounts/<int:pk>/balance/', views.BankAccountBalanceView.as_view(), name='bank-account-balance'),
    
    # Bank Transaction URLs
    path('transactions/', views.BankTransactionListCreateView.as_view(), name='bank-transaction-list'),
    path('transactions/<int:pk>/', views.BankTransactionDetailView.as_view(), name='bank-transaction-detail'),
    path('transactions/summary/', views.BankTransactionSummaryView.as_view(), name='bank-transaction-summary'),
    
    # Bank Transfer URL
    path('transfers/', views.BankTransferView.as_view(), name='bank-transfer'),
    path('transactions/dashboard/', views.cash_bank_dashboard, name='cash-bank-dashboard'),
]
