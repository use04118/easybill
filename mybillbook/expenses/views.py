from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import F
from django.http import JsonResponse
from django_filters.rest_framework import DjangoFilterBackend
from .models import ExpenseItem,ExpenseService,ExpenseCategory,Item,Expense
from .serializers import (
    ExpenseCategorySerializer,ExpenseItemSerializer,ExpenseServiceSerializer,ItemSerializer,ExpenseSerializer
)
from users.utils import get_current_business, log_action
from .permissions import HasExpensePermission
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes


# Item CRUD Operations
class ItemListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, HasExpensePermission]
    serializer_class = ItemSerializer
    filter_backends = [DjangoFilterBackend]

    def get_queryset(self):
        return Item.objects.filter(business=get_current_business(self.request.user))
    
    def perform_create(self, serializer):
        business = get_current_business(self.request.user)
        serializer.save(business=business)
        instances = serializer.instance
        items = instances if isinstance(instances, list) else [instances]
       

        for item in items:
            item.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

class ItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ItemSerializer
    permission_classes = [IsAuthenticated, HasExpensePermission]

    
    def get_queryset(self):
        return Item.objects.filter(business=get_current_business(self.request.user))

    def perform_update(self, serializer):
        # Save the item and handle service/product-specific updates
        item = serializer.save()
        
        item.save()

        log_action(self.request.user,get_current_business(self.request.user),"item_updated",{"name": item.itemName} ) # adjust the field name as needed)

    def perform_destroy(self, instance):
        log_action(self.request.user, get_current_business(self.request.user), "item_deleted", {"name": instance.itemName})
        instance.delete()


class ExpenseServiceListCreateView(generics.ListCreateAPIView):
    queryset = ExpenseService.objects.all()
    serializer_class = ExpenseServiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ExpenseService.objects.filter(business=get_current_business(self.request.user))

    def perform_create(self, serializer):
        business = get_current_business(self.request.user)
        serializer.save(business=business)


class ExpenseServiceDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ExpenseService.objects.all()
    serializer_class = ExpenseServiceSerializer
    permission_classes = [IsAuthenticated, HasExpensePermission]

    
    def get_queryset(self):
        return ExpenseService.objects.filter(business=get_current_business(self.request.user))

    def perform_update(self, serializer):
        # Save the service
        service = serializer.save()
        # You can add additional logic for service if needed


# List and Create API for Categories
class ExpenseCategoryListCreateView(generics.ListCreateAPIView):
    serializer_class = ExpenseCategorySerializer
    permission_classes = [IsAuthenticated, HasExpensePermission]

    def get_queryset(self):
        return ExpenseCategory.objects.filter(business=get_current_business(self.request.user))

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
class ExpenseCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ExpenseCategorySerializer
    permission_classes = [IsAuthenticated, HasExpensePermission]

    
    def get_queryset(self):
        return ExpenseCategory.objects.filter(business=get_current_business(self.request.user))

    def perform_update(self, serializer):
        category = serializer.save()
        log_action(self.request.user, get_current_business(self.request.user), "item_category_updated", {"name": category.name})

    def perform_destroy(self, instance):
        log_action(self.request.user, get_current_business(self.request.user), "item_category_deleted", {"name": instance.name})
        instance.delete()


# views.py

class ExpenseListCreateView(generics.ListCreateAPIView):
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated, HasExpensePermission]

    def get_queryset(self):
        return Expense.objects.filter(business=get_current_business(self.request.user))

    def perform_create(self, serializer):
        business = get_current_business(self.request.user)
        instance = serializer.save(business=business)
        log_action(self.request.user, business, "expense_created", {"expense_no": instance.expense_no})


class ExpenseDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated, HasExpensePermission]

    def get_queryset(self):
        return Expense.objects.filter(business=get_current_business(self.request.user))

    def perform_update(self, serializer):
        instance = serializer.save()
        log_action(self.request.user, get_current_business(self.request.user), "expense_updated", {"expense_no": instance.expense_no})

    def perform_destroy(self, instance):
        log_action(self.request.user, get_current_business(self.request.user), "expense_deleted", {"expense_no": instance.expense_no})
        instance.delete()


class ExpenseItemListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, HasExpensePermission]
    serializer_class = ExpenseItemSerializer
    filter_backends = [DjangoFilterBackend]

    def get_queryset(self):
        return ExpenseItem.objects.filter(expense__business=get_current_business(self.request.user))

    def perform_create(self, serializer):
        business = get_current_business(self.request.user)
        instance = serializer.save()
        log_action(self.request.user, business, "expense_item_created", {"type": instance.get_type()})


class ExpenseItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ExpenseItemSerializer
    permission_classes = [IsAuthenticated, HasExpensePermission]

    def get_queryset(self):
        return ExpenseItem.objects.filter(expense__business=get_current_business(self.request.user))

    def perform_update(self, serializer):
        item = serializer.save()
        log_action(self.request.user, get_current_business(self.request.user), "expense_item_updated", {"type": item.get_type()})

    def perform_destroy(self, instance):
        log_action(self.request.user, get_current_business(self.request.user), "expense_item_deleted", {"type": instance.get_type()})
        instance.delete()

