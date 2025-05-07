from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.http import JsonResponse
from django.conf import settings
from django.db.models import Sum
from django_filters.rest_framework import DjangoFilterBackend

import requests

from .models import Party, PartyCategory
from .serializers import PartySerializer, PartyCategorySerializer
from .filter import PartyFilter
from users.utils import get_current_business, log_action
from .permissions import HasPartyPermission


# ---------------------------
# ✅ To Collect / To Pay APIs
# ---------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated, HasPartyPermission])
def get_to_pay_parties(request):
    business = get_current_business(request.user)
    to_pay_parties = Party.objects.filter(balance_type='To Pay', business=business)
    total_to_pay = to_pay_parties.aggregate(Sum('closing_balance'))['closing_balance__sum'] or 0
    serialized = PartySerializer(to_pay_parties, many=True)
    return Response({'totalToPay': total_to_pay, 'parties': serialized.data})


@api_view(['GET'])
@permission_classes([IsAuthenticated, HasPartyPermission])
def get_to_collect_parties(request):
    business = get_current_business(request.user)
    to_collect_parties = Party.objects.filter(balance_type='To Collect', business=business)
    total_to_collect = to_collect_parties.aggregate(Sum('closing_balance'))['closing_balance__sum'] or 0
    serialized = PartySerializer(to_collect_parties, many=True)
    return Response({'totalToCollect': total_to_collect, 'parties': serialized.data})


# ---------------------------
# ✅ Party CRUD
# ---------------------------

class PartyListCreateView(generics.ListCreateAPIView):
    serializer_class = PartySerializer
    permission_classes = [IsAuthenticated, HasPartyPermission]

    def get_queryset(self):
        return Party.objects.filter(business=get_current_business(self.request.user))

    def create(self, request, *args, **kwargs):
        business = get_current_business(request.user)
        data = request.data
        many = isinstance(data, list)
        serializer = self.get_serializer(data=data, many=many)

        if serializer.is_valid():
            serializer.save(business=business)
            if many:
                for party in serializer.instance:
                    log_action(request.user, business, "party_created", {"name": party.party_name})
            else:
                log_action(request.user, business, "party_created", {"name": serializer.instance.party_name})
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class PartyDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PartySerializer
    permission_classes = [IsAuthenticated, HasPartyPermission]

    def get_queryset(self):
        return Party.objects.filter(business=get_current_business(self.request.user))

    def perform_update(self, serializer):
        party = serializer.save()
        log_action(self.request.user, get_current_business(self.request.user), "party_updated", {"name": party.party_name})

    def perform_destroy(self, instance):
        log_action(self.request.user, get_current_business(self.request.user), "party_deleted", {"name": instance.party_name})
        instance.delete()


# ---------------------------
# ✅ GST Fetching API
# ---------------------------

class FetchGSTDetails(APIView):
    permission_classes = [IsAuthenticated]  # changed from AllowAny to secure

    def get(self, request, gstin):
        api_key = settings.GSTIN_API_KEY
        url = f"http://sheet.gstincheck.co.in/check/{api_key}/{gstin}"

        try:
            res = requests.get(url)
            if res.status_code == 200:
                data = res.json()
                if data.get("flag"):
                    gst_data = data.get("data", {})
                    return JsonResponse({
                        "name": gst_data.get("lgnm"),
                        "shipping_address": gst_data.get("pradr", {}).get("adr", "N/A"),
                        "billing_address": gst_data.get("pradr", {}).get("adr", "N/A")
                    })
                return JsonResponse({"error": "Invalid GSTIN"}, status=400)
            return JsonResponse({"error": "API Error"}, status=500)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)


# ---------------------------
# ✅ Party List Filter View
# ---------------------------

class PartyListView(generics.ListAPIView):
    serializer_class = PartySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = PartyFilter
    permission_classes = [IsAuthenticated, HasPartyPermission]

    def get_queryset(self):
        return Party.objects.filter(business=get_current_business(self.request.user))


# ---------------------------
# ✅ Party Category CRUD
# ---------------------------

class PartyCategoryListCreateView(generics.ListCreateAPIView):
    serializer_class = PartyCategorySerializer
    permission_classes = [IsAuthenticated, HasPartyPermission]

    def get_queryset(self):
        return PartyCategory.objects.filter(business=get_current_business(self.request.user))

    def create(self, request, *args, **kwargs):
        business = get_current_business(request.user)
        data = request.data
        many = isinstance(data, list)
        serializer = self.get_serializer(data=data, many=many)
        if serializer.is_valid():
            serializer.save(business=business)
            if many:
                for cat in serializer.instance:
                    log_action(request.user, business, "party_category_created", {"name": cat.name})
            else:
                log_action(request.user, business, "party_category_created", {"name": serializer.instance.name})
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class PartyCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PartyCategorySerializer
    permission_classes = [IsAuthenticated, HasPartyPermission]

    def get_queryset(self):
        return PartyCategory.objects.filter(business=get_current_business(self.request.user))

    def perform_update(self, serializer):
        category = serializer.save()
        log_action(self.request.user, get_current_business(self.request.user), "party_category_updated", {"name": category.name})

    def perform_destroy(self, instance):
        log_action(self.request.user, get_current_business(self.request.user), "party_category_deleted", {"name": instance.name})
        instance.delete()
