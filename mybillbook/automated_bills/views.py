from rest_framework import viewsets,generics
from .models import AutomatedInvoice, AutomatedInvoiceItem
from .serializers import AutomatedInvoiceSerializer, AutomatedInvoiceItemSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from sales.serializers import InvoiceSerializer, InvoiceItemSerializer
from sales.models import  InvoiceItem
from django.db import transaction
from datetime import date, timedelta
from rest_framework.permissions import IsAuthenticated, AllowAny
from .permissions import HasSalesPermission
from users.utils import get_current_business, log_action
from sales.models import Invoice
from django.utils import timezone
from .utils import generate_invoice_no, generate_sales_invoice_from_automated


class AutomatedInvoiceListCreateView(generics.ListCreateAPIView):
    serializer_class = AutomatedInvoiceSerializer
    permission_classes = [IsAuthenticated, HasSalesPermission]

    def get_queryset(self):
        return AutomatedInvoice.objects.filter(business=get_current_business(self.request.user))

    def perform_create(self, serializer):
        business = get_current_business(self.request.user)
        instance = serializer.save(business=business)
        log_action(self.request.user, business, "automated_invoice_created", {"automated_invoice_id": instance.id})
        return instance
    
    def post(self, request, *args, **kwargs):
        serializer = AutomatedInvoiceSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AutomatedInvoiceDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AutomatedInvoiceSerializer
    permission_classes = [IsAuthenticated, HasSalesPermission]

    def get_queryset(self):
        return AutomatedInvoice.objects.filter(business=get_current_business(self.request.user))

    def perform_update(self, serializer):
        instance = serializer.save()
        log_action(self.request.user, instance.business, "automated_invoice_updated", {"automated_invoice_id": instance.id})

    def perform_destroy(self, instance):
        log_action(self.request.user, instance.business, "automated_invoice_deleted", {"automated_invoice_id": instance.id})
        instance.delete()

class AutomatedInvoiceItemListCreateView(generics.ListCreateAPIView):
    queryset = AutomatedInvoiceItem.objects.all()
    serializer_class = AutomatedInvoiceItemSerializer

class AutomatedInvoiceItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = AutomatedInvoiceItem.objects.all()
    serializer_class = AutomatedInvoiceItemSerializer


