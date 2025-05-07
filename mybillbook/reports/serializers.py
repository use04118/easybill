# in reports/serializers.py
from rest_framework import serializers
from .models import CapitalEntry, LoanEntry, FixedAssetEntry, InvestmentEntry, LoansAdvanceEntry, CurrentLiabilityEntry, CurrentAssetEntry

class CapitalEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = CapitalEntry
        fields = '__all__'
        read_only_fields = ['business']

class CurrentLiabilityEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = CurrentLiabilityEntry
        fields = '__all__'
        read_only_fields = ['business']

class LoanEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanEntry
        fields = '__all__'
        read_only_fields = ['business']

class CurrentAssetEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = CurrentAssetEntry
        fields = '__all__'
        read_only_fields = ['business']


class FixedAssetEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = FixedAssetEntry
        fields = '__all__'
        read_only_fields = ['business']
        
class InvestmentEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = InvestmentEntry
        fields = '__all__'
        read_only_fields = ['business']

class LoansAdvanceEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LoansAdvanceEntry
        fields = '__all__'
        read_only_fields = ['business']

