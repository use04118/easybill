from rest_framework import serializers
from .models import HSNCode

class HSNCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = HSNCode
        fields = ['hsn_cd', 'hsn_description']
