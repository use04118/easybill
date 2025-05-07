from rest_framework import serializers
from .models import User, Business, Role,SubscriptionPlan, Subscription,StaffInvite,AuditLog
from .utils import get_current_business

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'mobile']

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'mobile', 'name', 'email', 'profile_picture']

class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = [
            'id', 'name', 'phone', 'email',
            'business_address', 'street_address',
            'tcs','tds', 'gstin', 'business_type',
            'industry_type', 'registration_type',
            'pan_number', 'website', 'state', 'city', 'pincode','signature'
        ]

    def create(self, validated_data):
        user = self.context['request'].user

        # Remove owner if passed by mistake
        validated_data.pop('owner', None)

        # Create business with phone number from user
        business = Business.objects.create(
            owner=user,
            **validated_data
        )

        # Assign 'admin' role to the user for this business
        Role.objects.create(
            user=user,
            business=business,
            role_name='admin',
            permissions={"*": True}
        )

        return business

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = '__all__'

class InviteStaffSerializer(serializers.Serializer):
    mobile = serializers.CharField()
    name = serializers.CharField()
    role_name = serializers.ChoiceField(choices=Role.ROLE_CHOICES)
    business_id = serializers.IntegerField()

    def validate_mobile(self, mobile):
        request = self.context['request']
        business_id = self.initial_data.get("business_id")

        from users.models import Business, Role, StaffInvite

        try:
            business = Business.objects.get(id=business_id)
        except Business.DoesNotExist:
            raise serializers.ValidationError("Invalid business ID.")

        if Role.objects.filter(user__mobile=mobile, business=business).exists():
            raise serializers.ValidationError("This user is already part of the business.")

        if StaffInvite.objects.filter(mobile=mobile, business=business, status='accepted').exists():
            raise serializers.ValidationError("This user has already accepted an invite.")

        return mobile


class VerifyStaffOTPSerializer(serializers.Serializer):
    mobile = serializers.CharField()
    otp = serializers.CharField()

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = ['id', 'name', 'price', 'duration_days', 'features']

class SubscriptionSerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanSerializer()

    class Meta:
        model = Subscription
        fields = ['plan', 'start_date', 'end_date', 'is_active']

class AuditLogSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source='user.mobile', read_only=True)

    class Meta:
        model = AuditLog
        fields = ['user', 'action', 'metadata', 'created_at']
