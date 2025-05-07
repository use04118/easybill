from django.urls import path
from .views import PartyListCreateView, PartyDetailView, PartyCategoryDetailView, PartyCategoryListCreateView, FetchGSTDetails, PartyListView, get_to_pay_parties, get_to_collect_parties
urlpatterns = [
    path('parties/', PartyListCreateView.as_view(), name='party-list'),
    path('parties/<int:pk>/', PartyDetailView.as_view(), name='party-detail'),  # Handles GET, PUT, PATCH, DELETE
    path('fetch-gst/<str:gstin>/', FetchGSTDetails.as_view(), name='fetch-gst-detail'),
    path('all-parties/', PartyListView.as_view(), name='all-party-list'),
    
    path('categories/', PartyCategoryListCreateView.as_view(), name='Category-list'),
    path('categories/<int:pk>/', PartyCategoryDetailView.as_view(), name='Category-detail'), # Handles GET, PUT, PATCH, DELETE
    
    path('parties/to-pay/', get_to_pay_parties, name='to-pay-parties'),
    path('parties/to-collect/', get_to_collect_parties, name='to-collect-parties'),
]
