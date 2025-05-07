from .models import Godown, State
from .serializers import GodownSerializer, StateSerializer
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from users.utils import get_current_business, log_action
from inventory.models import Item
from django.db.models import F, ExpressionWrapper, DecimalField
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .permissions import HasGodownPermission
from rest_framework.decorators import api_view, permission_classes
# -------------------------------
# ✅ GODOWN CRUD
# -------------------------------

class GodownListCreateView(generics.ListCreateAPIView):
    serializer_class = GodownSerializer
    permission_classes = [IsAuthenticated, HasGodownPermission]

    def get_queryset(self):
        return Godown.objects.filter(business=get_current_business(self.request.user))

    def perform_create(self, serializer):
        business = get_current_business(self.request.user)
        godown = serializer.save(business=business)
        log_action(self.request.user, business, "godown_created", {"name": godown.godownName})


class GodownDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = GodownSerializer
    permission_classes = [IsAuthenticated, HasGodownPermission]

    def get_queryset(self):
        return Godown.objects.filter(business=get_current_business(self.request.user))

    def perform_update(self, serializer):
        godown = serializer.save()
        log_action(self.request.user, get_current_business(self.request.user), "godown_updated", {"name": godown.godownName})

    def perform_destroy(self, instance):
        log_action(self.request.user, get_current_business(self.request.user), "godown_deleted", {"name": instance.godownName})
        instance.delete()


# -------------------------------
# ✅ STATE CRUD
# -------------------------------

class StateListCreateView(generics.ListCreateAPIView):
    queryset = State.objects.all()
    serializer_class = StateSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        data = request.data
        many = isinstance(data, list)
        serializer = self.get_serializer(data=data, many=many)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class StateDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = State.objects.all()
    serializer_class = StateSerializer
    permission_classes = [IsAuthenticated]


# -------------------------------
# ✅ DASHBOARD STOCK VALUE (per Godown)
# -------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_data(request, godown_id=None):
    user = request.user

    # Check if the user is authenticated
    if not user.is_authenticated:
        return JsonResponse({'error': 'User is not authenticated'}, status=401)

    # Get the current business for the authenticated user
    business = get_current_business(user)

    if godown_id:
        godown = get_object_or_404(Godown, id=godown_id, business=business)
        queryset = Item.objects.filter(godown=godown, business=business)
    else:
        queryset = Item.objects.filter(business=business)

    stock_data = list(queryset.annotate(
        item_name=F('itemName'),
        item_code=F('itemCode'),
        item_batch=F('itemBatch'),
        stock_qty=F('closingStock'),
        stock_value=ExpressionWrapper(F('closingStock') * F('purchasePrice'), output_field=DecimalField()),
        sales_price=F('salesPrice'),
        purchase_price=F('purchasePrice')
    ).values('item_name', 'item_code', 'item_batch', 'stock_qty', 'stock_value', 'sales_price', 'purchase_price'))

    return JsonResponse({'transactions': stock_data}, safe=False)
