from rest_framework import serializers
from .models import Party, PartyCategory

class PartySerializer(serializers.ModelSerializer):
    class Meta:
        model = Party
        fields = '__all__'
        read_only_fields = ['business']


class PartyCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PartyCategory
        fields = '__all__'
        read_only_fields = ['business']  # ✅ This fixes the issue
