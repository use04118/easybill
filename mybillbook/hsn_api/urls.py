from django.urls import path
from .views import HSNCodeDetail, HSNCodeSearch

urlpatterns = [
    path('hsn/<str:hsn_cd>/', HSNCodeDetail.as_view(), name='hsn-detail'),
    path('hsn/search/', HSNCodeSearch.as_view(), name='hsn-search'),
]
