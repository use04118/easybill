from django.urls import path
from .views import (
    ItemListCreateView, ItemDetailView,
    ExpenseListCreateView, ExpenseDetailView,
    ExpenseItemListCreateView, ExpenseItemDetailView,
    ExpenseServiceListCreateView, ExpenseServiceDetailView,
    ExpenseCategoryListCreateView, ExpenseCategoryDetailView,
)

urlpatterns = [
    # Expenses
    path('expenses/', ExpenseListCreateView.as_view(), name='expense-list-create'),
    path('expenses/<int:pk>/', ExpenseDetailView.as_view(), name='expense-detail'),

    # Expense Items
    path('expense-items/', ExpenseItemListCreateView.as_view(), name='expense-item-list-create'),
    path('expense-items/<int:pk>/', ExpenseItemDetailView.as_view(), name='expense-item-detail'),

    # Item
    path('items/', ItemListCreateView.as_view(), name='item-list-create'),
    path('items/<int:pk>/', ItemDetailView.as_view(), name='item-detail'),
    
    # Services
    path('services/', ExpenseServiceListCreateView.as_view(), name='service-list-create'),
    path('services/<int:pk>/', ExpenseServiceDetailView.as_view(), name='service-detail'),

    # Categories
    path('categories/', ExpenseCategoryListCreateView.as_view(), name='category-list-create'),
    path('categories/<int:pk>/', ExpenseCategoryDetailView.as_view(), name='category-detail'),
]
