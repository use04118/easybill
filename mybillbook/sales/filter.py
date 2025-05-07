import django_filters
from .models import Party


class PartyFilter(django_filters.FilterSet):
    party_category = django_filters.CharFilter(field_name='party_category', lookup_expr='icontains')
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')


    class Meta:
        model = Party
        fields = ['party_category','name']
