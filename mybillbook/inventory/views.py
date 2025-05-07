from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import F
from django.http import JsonResponse
from django_filters.rest_framework import DjangoFilterBackend
from .filter import ItemFilter
from .models import Item, ItemCategory, MeasuringUnit, GSTTaxRate, Service
from .serializers import (
    ItemSerializer, ItemCategorySerializer, MeasuringUnitSerializer,
    GSTTaxRateSerializer, ServiceSerializer
)
from users.utils import get_current_business, log_action
from .permissions import HasItemPermission
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes


@api_view(['GET'])
@permission_classes([IsAuthenticated, HasItemPermission])
def stock_value(request):
    # Query all items where itemType is 'Product'
    items = Item.objects.filter(itemType='Product')

    stock_values = []
    total_stock_value = 0  # Initialize the total stock value

    for item in items:
        # Calculate purchase price without tax
        def get_purchasePrice_without_tax(item):
            """Returns the tax-inclusive purchase price if stored without tax."""
            if item.purchasePriceType == "With Tax":
                return item.calculate_price(item.purchasePrice, "With Tax")
            return item.purchasePrice  # Already tax-inclusive
        purchase_price_without_tax = get_purchasePrice_without_tax(item)
        
        # Calculate stock value based on closingStock and purchasePrice_without_tax
        if item.closingStock and purchase_price_without_tax:
            stock_value = item.closingStock * purchase_price_without_tax
        else:
            stock_value = 0.00
        
        # Add the stock value to the total stock value
        total_stock_value += stock_value
        
        # Store the result in a dictionary to return as JSON or log
        stock_values.append({
            "item_name": item.itemName,
            "stock_value": round(stock_value,2)
        })

    # Return as a JSON response with total stock value included
    return JsonResponse({
        "stock_values": stock_values,
        "total_stock_value": round(total_stock_value,2)
    })


# Low Stock Count
@api_view(['GET'])
@permission_classes([IsAuthenticated, HasItemPermission])
def low_stock_value(request):
    low_stock_count = Item.objects.filter(enableLowStockWarning=True).count()
    return Response({'totalLowStockItems': low_stock_count})


# Item CRUD Operations
class ItemListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, HasItemPermission]
    serializer_class = ItemSerializer
    filter_backends = [DjangoFilterBackend]

    def get_queryset(self):
        return Item.objects.filter(business=get_current_business(self.request.user))
    
    def perform_create(self, serializer):
        business = get_current_business(self.request.user)
        serializer.save(business=business)
        # data= request.data
        # many = isinstance(data, list)
        # serializer = self.get_serializer(data=data, many=many)
        instances = serializer.instance
        items = instances if isinstance(instances, list) else [instances]
       

        for item in items:
            if item.itemType == "Product":
                if item.closingStock is not None and item.lowStockQty is not None:
                    item.enableLowStockWarning = item.closingStock <= item.lowStockQty
                else:
                    item.enableLowStockWarning = False  # Default to False if None

            elif item.itemType == "Service":
                # Handle Service-specific fields
                item.closingStock = None
                item.lowStockQty = None
                item.enableLowStockWarning = None

            item.save()

            return Response(serializer.data, status=201)

        return Response(serializer.errors, status=400)

class ItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ItemSerializer
    permission_classes = [IsAuthenticated, HasItemPermission]

    
    def get_queryset(self):
        return Item.objects.filter(business=get_current_business(self.request.user))

    def perform_update(self, serializer):
        # Save the item and handle service/product-specific updates
        item = serializer.save()
        if item.itemType == "Product":
            if item.closingStock is not None and item.lowStockQty is not None:
                item.enableLowStockWarning = item.closingStock <= item.lowStockQty
            else:
                item.enableLowStockWarning = False  # Default to False if None
        
        elif item.itemType == "Service":
            # Handle Service-specific fields
            item.closingStock = None
            item.lowStockQty = None
            item.enableLowStockWarning = None
        
        item.save()

        log_action(self.request.user,get_current_business(self.request.user),"item_updated",{"name": item.itemName} ) # adjust the field name as needed)

    def perform_destroy(self, instance):
        log_action(self.request.user, get_current_business(self.request.user), "item_deleted", {"name": instance.itemName})
        instance.delete()


class ServiceListCreateView(generics.ListCreateAPIView):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Service.objects.filter(business=get_current_business(self.request.user))

    def perform_create(self, serializer):
        business = get_current_business(self.request.user)
        serializer.save(business=business)


class ServiceDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated, HasItemPermission]

    
    def get_queryset(self):
        return Service.objects.filter(business=get_current_business(self.request.user))

    def perform_update(self, serializer):
        # Save the service
        service = serializer.save()
        # You can add additional logic for service if needed


class ItemListView(generics.ListAPIView):
    filterset_class = ItemFilter


# List and Create API for Categories
class ItemCategoryListCreateView(generics.ListCreateAPIView):
    serializer_class = ItemCategorySerializer
    permission_classes = [IsAuthenticated, HasItemPermission]

    def get_queryset(self):
        return ItemCategory.objects.filter(business=get_current_business(self.request.user))

    def create(self, request, *args, **kwargs):
        business = get_current_business(request.user)
        data = request.data
        many = isinstance(data, list)
        serializer = self.get_serializer(data=data, many=many)
        if serializer.is_valid():
            serializer.save(business=business)
            if many:
                for cat in serializer.instance:
                    log_action(request.user, business, "item_category_created", {"name": cat.name})
            else:
                log_action(request.user, business, "item_category_created", {"name": serializer.instance.name})
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

# Retrieve, Update, Destroy API for Categories
class ItemCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ItemCategorySerializer
    permission_classes = [IsAuthenticated, HasItemPermission]

    
    def get_queryset(self):
        return ItemCategory.objects.filter(business=get_current_business(self.request.user))

    def perform_update(self, serializer):
        category = serializer.save()
        log_action(self.request.user, get_current_business(self.request.user), "item_category_updated", {"name": category.name})

    def perform_destroy(self, instance):
        log_action(self.request.user, get_current_business(self.request.user), "item_category_deleted", {"name": instance.name})
        instance.delete()



class MeasuringUnitListCreateView(generics.ListCreateAPIView):
    serializer_class = MeasuringUnitSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return MeasuringUnit.objects.all()

    def create(self, request, *args, **kwargs):
        data = request.data
        many = isinstance(data, list)
        serializer = self.get_serializer(data=data, many=many)
        if serializer.is_valid():
            serializer.save()  # No need to attach business
            if many:
                for unit in serializer.instance:
                    log_action(request.user, None, "measuringunit_created", {"name": unit.name})
            else:
                log_action(request.user, None, "measuringunit_created", {"name": serializer.instance.name})
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class MeasuringUnitDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MeasuringUnitSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return MeasuringUnit.objects.all()


# --- GST Tax Rates ---

class GSTTaxRateListCreateView(generics.ListCreateAPIView):
    serializer_class = GSTTaxRateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return GSTTaxRate.objects.all()

    def create(self, request, *args, **kwargs):
        data = request.data
        many = isinstance(data, list)
        serializer = self.get_serializer(data=data, many=many)
        if serializer.is_valid():
            serializer.save()  # No need to attach business
            if many:
                for gst in serializer.instance:
                    log_action(request.user, None, "gsttaxrate_created", {
                        "rate": str(gst.rate),
                        "description": gst.description
                    })
            else:
                gst = serializer.instance
                log_action(request.user, None, "gsttaxrate_created", {
                    "rate": str(gst.rate),
                    "description": gst.description
                })
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class GSTTaxRateDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = GSTTaxRateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return GSTTaxRate.objects.all()

    def perform_update(self, serializer):
        gst = serializer.save()
        log_action(self.request.user, None, "gsttaxrate_updated", {
            "rate": str(gst.rate),
            "description": gst.description
        })

    def perform_destroy(self, instance):
        log_action(self.request.user, None, "gsttaxrate_deleted", {
            "rate": str(instance.rate),
            "description": instance.description
        })
        instance.delete()