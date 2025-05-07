from django.urls import path
from . import views

urlpatterns = [
    # API endpoints for Godown
    path('godown/', views.GodownListCreateView.as_view(), name='godown-list-create'),
    path('godown/<int:pk>/', views.GodownDetailView.as_view(), name='godown-detail'),
    
    path('dashboard/', views.dashboard_data, name='godown-dashboard'),  # For all Godowns
    path('dashboard/<int:godown_id>/', views.dashboard_data, name='godown-dashboard-filtered'),  # For specific Godown
    
    path('state/', views.StateListCreateView.as_view(), name='State-list-create'),
    path('state/<int:pk>/', views.StateDetailView.as_view(), name='State-detail'),
]
