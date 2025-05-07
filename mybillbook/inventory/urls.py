from django.urls import path
from . import views

urlpatterns = [
    # API endpoints for Items
    path('items/', views.ItemListCreateView.as_view(), name='item-list-create'),  # List and Create Items
    path('items/<int:pk>/', views.ItemDetailView.as_view(), name='item-detail'),  # Retrieve, Update, Delete a single Item
    path('all-item/', views.ItemListView.as_view(), name='item-list'),
    
    path('service/', views.ServiceListCreateView.as_view(), name='service-list-create'),  # List and Create Items
    path('service/<int:pk>/', views.ServiceDetailView.as_view(), name='ervice-detail'),  # Retrieve, Update, Delete a single Item
    # path('all-service/', views.ServiceListView.as_view(), name='service-list'),
    
    # API endpoints for Category
    path('categories/', views.ItemCategoryListCreateView.as_view(), name='category-list-create'),  # List and Create Category
    path('categories/<int:pk>/', views.ItemCategoryDetailView.as_view(), name='category-detail'),  # Retrieve, Update, Delete Category
    
    # API endpoints for Measuring Units
    path('measuring-units/', views.MeasuringUnitListCreateView.as_view(), name='measuring-unit-list-create'),  # List and Create Measuring Units
    path('measuring-units/<int:pk>/', views.MeasuringUnitDetailView.as_view(), name='measuring-unit-detail'),  # Retrieve, Update, Delete Measuring Unit
    
    # API endpoints for GST Tax Rates
    path('gst-tax-rates/', views.GSTTaxRateListCreateView.as_view(), name='gst-tax-rate-list-create'),  # List and Create GST Tax Rates
    path('gst-tax-rates/<int:pk>/', views.GSTTaxRateDetailView.as_view(), name='gst-tax-rate-detail'),  # Retrieve, Update, Delete GST Tax Rate


    path('stock/stock-value/', views.stock_value, name='stock-value'),
    path('stock/low-stock/', views.low_stock_value, name='low-stock'),
   

    # path('dashboard/', views.dashboard_data, name='item-dashboard'),
]