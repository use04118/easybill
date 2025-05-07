from rest_framework import serializers
from .models import SACCode

class SACCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SACCode
        fields = ['sac_cd', 'sac_description']
