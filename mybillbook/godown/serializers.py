from rest_framework import serializers
from .models import Godown, State


class StateSerializer(serializers.ModelSerializer):
    class Meta:
        model = State
        fields = '__all__'


class GodownSerializer(serializers.ModelSerializer):
    class Meta:
        model = Godown
        fields = '__all__'
        read_only_fields = ['business']  # Business will be injected from context
