from django.urls import path
from .views import SACCodeDetail, SACCodeSearch

urlpatterns = [
    path('sac/<str:sac_cd>/', SACCodeDetail.as_view(), name='sac-detail'),
    path('sac/search/', SACCodeSearch.as_view(), name='sac-search'),
]
