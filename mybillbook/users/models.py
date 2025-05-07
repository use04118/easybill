from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin

class UserManager(BaseUserManager):
    def create_user(self, mobile, password=None, **extra_fields):
        if not mobile:
            raise ValueError('The Mobile number must be set')
        user = self.model(mobile=mobile, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, mobile, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True')

        return self.create_user(mobile, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    mobile = models.CharField(max_length=15, unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    name = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='static/profile/', null=True, blank=True)
    
    current_business = models.ForeignKey('Business', null=True, blank=True, on_delete=models.SET_NULL, related_name='current_users')

    objects = UserManager()

    USERNAME_FIELD = 'mobile'
    REQUIRED_FIELDS = []

INDIAN_STATES = [
    ('Andhra Pradesh', 'Andhra Pradesh'),
    ('Arunachal Pradesh', 'Arunachal Pradesh'),
    ('Assam', 'Assam'),
    ('Bihar', 'Bihar'),
    ('Chhattisgarh', 'Chhattisgarh'),
    ('Goa', 'Goa'),
    ('Gujarat', 'Gujarat'),
    ('Haryana', 'Haryana'),
    ('Himachal Pradesh', 'Himachal Pradesh'),
    ('Jharkhand', 'Jharkhand'),
    ('Karnataka', 'Karnataka'),
    ('Kerala', 'Kerala'),
    ('Madhya Pradesh', 'Madhya Pradesh'),
    ('Maharashtra', 'Maharashtra'),
    ('Manipur', 'Manipur'),
    ('Meghalaya', 'Meghalaya'),
    ('Mizoram', 'Mizoram'),
    ('Nagaland', 'Nagaland'),
    ('Odisha', 'Odisha'),
    ('Punjab', 'Punjab'),
    ('Rajasthan', 'Rajasthan'),
    ('Sikkim', 'Sikkim'),
    ('Tamil Nadu', 'Tamil Nadu'),
    ('Telangana', 'Telangana'),
    ('Tripura', 'Tripura'),
    ('Uttar Pradesh', 'Uttar Pradesh'),
    ('Uttarakhand', 'Uttarakhand'),
    ('West Bengal', 'West Bengal'),
    ('Delhi', 'Delhi'),
    ('Jammu and Kashmir', 'Jammu and Kashmir'),
    ('Ladakh', 'Ladakh'),
    ('Puducherry', 'Puducherry'),
    ('Chandigarh', 'Chandigarh'),
    ('Andaman and Nicobar Islands', 'Andaman and Nicobar Islands'),
    ('Dadra and Nagar Haveli and Daman and Diu', 'Dadra and Nagar Haveli and Daman and Diu'),
    ('Lakshadweep', 'Lakshadweep'),
]

BUSINESS_TYPES = [
    ('Retailer', 'Retailer'),
    ('Wholesaler', 'Wholesaler'),
    ('Distributor', 'Distributor'),
    ('Manufacturer', 'Manufacturer'),
    ('Services', 'Services'),
]

INDUSTRY_TYPES = [
    ('Accounting and Financial Services', 'Accounting and Financial Services'),
    ('Agriculture', 'Agriculture'),
    ('Automobile', 'Automobile'),
    ('Battery', 'Battery'),
    ('Broadband/ Cable/ Internet', 'Broadband/ Cable/ Internet'),
    ('Building Material and Construction', 'Building Material and Construction'),
    ('Cleaning and Pest Control', 'Cleaning and Pest Control'),
    ('Consulting', 'Consulting'),
    ('Dairy (Milk)', 'Dairy (Milk)'),
    ('Doctor / Clinic / Hospital', 'Doctor / Clinic / Hospital'),
    ('Education - Schooling/ Coaching', 'Education - Schooling/ Coaching'),
    ('Electrical works', 'Electrical works'),
    ('Electronics', 'Electronics'),
    ('Engineering', 'Engineering'),
    ('Event planning and management', 'Event planning and management'),
    ('FMCG', 'FMCG'),
    ('Fitness - Gym and Spa', 'Fitness - Gym and Spa'),
    ('Footwear', 'Footwear'),
    ('Fruits and Vegetables', 'Fruits and Vegetables'),
    ('Furniture', 'Furniture'),
    ('Garment/ Clothing', 'Garment/ Clothing'),
    ('General Store (Kirana)', 'General Store (Kirana)'),
    ('Gift Shop', 'Gift Shop'),
    ('Hardware', 'Hardware'),
    ('Home services', 'Home services'),
    ('Hotels and Hospitality', 'Hotels and Hospitality'),
    ('Information Technology', 'Information Technology'),
    ('Interiors', 'Interiors'),
    ('Jewellery', 'Jewellery'),
    ('Liquor', 'Liquor'),
    ('Machinery', 'Machinery'),
    ('Meat', 'Meat'),
    ('Medical Devices', 'Medical Devices'),
    ('Medicine (Pharma)', 'Medicine (Pharma)'),
    ('Mobile and accessories', 'Mobile and accessories'),
    ('Oil And Gas', 'Oil And Gas'),
    ('Opticals', 'Opticals'),
    ('Other services', 'Other services'),
    ('Others', 'Others'),
    ('Packaging', 'Packaging'),
    ('Paints', 'Paints'),
    ('Photography', 'Photography'),
    ('Plywood', 'Plywood'),
    ('Printing', 'Printing'),
    ('Real estate - Rentals and Lease', 'Real estate - Rentals and Lease'),
    ('Restaurants/ Cafe/ Catering', 'Restaurants/ Cafe/ Catering'),
    ('Safety Equipments', 'Safety Equipments'),
    ('Salon', 'Salon'),
    ('Scrap', 'Scrap'),
    ('Service Centres', 'Service Centres'),
    ('Sports Equipments', 'Sports Equipments'),
    ('Stationery', 'Stationery'),
    ('Tailoring/ Boutique', 'Tailoring/ Boutique'),
    ('Textiles', 'Textiles'),
    ('Tiles/Sanitary Ware', 'Tiles/Sanitary Ware'),
    ('Tours and Travel', 'Tours and Travel'),
    ('Transport and Logistics', 'Transport and Logistics'),
    ('Utensils', 'Utensils'),
]


REGISTRATION_TYPES = [
    ('Private Limited Company', 'Private Limited Company'),
    ('Public Limited Company', 'Public Limited Company'),
    ('Partnerships Firm', 'Partnerships Firm'),
    ('Limited Liability Partnership', 'Limited Liability Partnership'),
    ('One Person Company', 'One Person Company'),
    ('Sole Proprietorship', 'Sole Proprietorship'),
    ('Section 8 Company', 'Section 8 Company'),
    ('Business Not Registered', 'Business Not Registered'),
]



class Business(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_businesses')
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=15)
    email = models.EmailField(null=True, blank=True)
    business_address = models.TextField(blank=True)
    street_address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, choices=INDIAN_STATES, blank=True, null=True)
    pincode = models.CharField(max_length=10, blank=True, null=True)

    pan_number = models.CharField(max_length=15, blank=True, null=True)
    gstin = models.CharField(max_length=15, blank=True, null=True)
    tds = models.BooleanField(default=False)
    tcs = models.BooleanField(default=False)

    business_type = models.JSONField(default=list, blank=True)  # Multiple selections
    industry_type = models.CharField(max_length=50, choices=INDUSTRY_TYPES, blank=True, null=True)
    registration_type = models.CharField(max_length=50, choices=REGISTRATION_TYPES, blank=True, null=True)
    signature = models.ImageField(upload_to='static/signature/',blank=True,null=True)
    website = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name


class Role(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('salesman', 'Salesman'),
        ('delivery_boy', 'Delivery Boy'),
        ('stock_manager', 'Stock Manager'),
        ('partner', 'Partner'),
        ('accountant', 'Accountant'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, null=True, blank=True)
    role_name = models.CharField(choices=ROLE_CHOICES, max_length=30)
    permissions = models.JSONField(default=dict)
    is_removed = models.BooleanField(default=False)  # 👈 NEW

    
    
class StaffInvite(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    mobile = models.CharField(max_length=15)
    name = models.CharField(max_length=255)
    role_name = models.CharField(choices=Role.ROLE_CHOICES, max_length=30)
    invited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('accepted', 'Accepted')], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.mobile} → {self.business.name} ({self.role_name})"


class SubscriptionPlan(models.Model):
    PLAN_CHOICES = [
        ('Free Trial', 'Free Trial'),
        ('Premium Monthly', 'Premium Monthly'),
        ('Premium Annual', 'Premium Annual'),
    ]
    name = models.CharField(max_length=20, choices=PLAN_CHOICES, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.PositiveIntegerField()  # E.g., 30 for monthly
    features = models.JSONField(default=dict)  # optional for future

    def __str__(self):
        return self.name

class Subscription(models.Model):
    business = models.OneToOneField('Business', on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.business.name} - {self.plan.name}"

class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    business = models.ForeignKey(Business, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} by {self.user} at {self.created_at}"

