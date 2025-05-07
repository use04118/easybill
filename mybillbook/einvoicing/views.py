from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import EWayBillSerializer, EInvoiceSerializer,GSTR1ReconciliationSerializer
from sales.models import Invoice
from .models import EWayBill, EInvoice,GSTR1Reconciliation
from datetime import datetime
# from .utils import generate_eway_bill_view, EInvoiceService # Import the function here!
from rest_framework import viewsets
import random
from django.shortcuts import get_object_or_404
from .models import EWayBill
from rest_framework.decorators import api_view
from django.http import JsonResponse
from .utils import build_einvoice_payload, reconcile_invoices
import uuid
from rest_framework import status, generics



# The view that handles the generation of the E-way Bill
class GenerateEWayBillFormView(APIView):
    def get(self, request, invoice_id):
        try:
            invoice = Invoice.objects.get(id=invoice_id)

            if hasattr(invoice, 'eway_bill'):
                return Response({"error": "E-Way Bill already exists for this invoice."}, status=status.HTTP_400_BAD_REQUEST)

            initial_data = {
                "invoice": invoice.id,
                "transporter_id": "TRANS12345",
                "transporter_name": "XYZ Transporter",
                "vehicle_number": "MH12AB1234",
                "mode": "Road",
                "distance": 50,
            }

            serializer = EWayBillSerializer(data=initial_data)

            if serializer.is_valid():
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Invoice.DoesNotExist:
            return Response({"error": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)


class GenerateEWayBillView(APIView):
    def post(self, request, invoice_id):
        try:
            invoice = Invoice.objects.get(id=invoice_id)

            if hasattr(invoice, 'eway_bill'):
                return Response({"error": "E-Way Bill already exists for this invoice."}, status=status.HTTP_400_BAD_REQUEST)

            ewb = generate_eway_bill_view(invoice_id, request.data)

            if ewb is None:
                return Response({"error": "Failed to generate E-Way Bill."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            serializer = EWayBillSerializer(ewb)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Invoice.DoesNotExist:
            return Response({"error": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# HELPER FUNCTION
def generate_eway_bill_view(invoice_id, data=None):
    try:
        invoice = Invoice.objects.get(id=invoice_id)

        transporter_id = data.get("transporter_id", "")
        transporter_name = data.get("transporter_name", "")
        vehicle_number = data.get("vehicle_number", "")
        mode = data.get("mode", "Road")
        distance = data.get("distance", 1)

        # Payload structure
        payload = {
            "supplyType": "Outward",
            "subSupplyType": 1,
            "docType": "INV",
            "docNo": invoice.invoice_no,
            "docDate": invoice.date.strftime("%d/%m/%Y"),
            "fromGstin": invoice.business.gstin,
            "fromAddr1": invoice.business.business_address,
            "fromPlace": invoice.business.city,
            "fromPincode": invoice.business.pincode,
            "fromStateCode": invoice.business.state,
            "toGstin": invoice.party.gstin,
            "toAddr1": invoice.party.billing_address,
            "toPlace": invoice.party.city,
            "toPincode": invoice.party.pincode,
            "toStateCode": invoice.party.state,
            "totalValue": float(invoice.get_total_amount()),
            "transMode": mode,
            "transDistance": distance,
            "transporterId": transporter_id,
            "transporterName": transporter_name,
            "vehicleNo": vehicle_number,
        }

        ewb_data = {
            "ewbNo": f"18100{random.randint(100000, 999999)}",
            "ewayBillDate": "16/04/2025 13:23:00",
            "validUpto": "17/04/2025 23:59:00",
            "status": "Generated"
        }

        ewb = EWayBill.objects.create(
            invoice=invoice,
            ewb_number=ewb_data["ewbNo"],
            generated_date=datetime.strptime(ewb_data["ewayBillDate"], "%d/%m/%Y %H:%M:%S"),
            valid_upto=datetime.strptime(ewb_data["validUpto"], "%d/%m/%Y %H:%M:%S"),
            status=ewb_data["status"],
            transporter_id=transporter_id,
            transporter_name=transporter_name,
            vehicle_number=vehicle_number,
            mode=mode,
            distance=distance,
            request_payload=payload,
            response_payload=ewb_data
        )

        return ewb

    except Invoice.DoesNotExist:
        print(f"Invoice with ID {invoice_id} not found.")
        return None
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None



    # Example of how to update the code with a real API URL and authentication key
    # def generate_eway_bill(invoice_id):
        # invoice = Invoice.objects.get(id=invoice_id)

        # payload = {
        #     "supplyType": "Outward",
        #     "subSupplyType": 1,
        #     "docType": "INV",
        #     "docNo": invoice.invoice_no,
        #     "docDate": invoice.date.strftime("%d/%m/%Y"),
        #     "fromGstin": invoice.business.gstin,
        #     "fromAddr1": invoice.business.address,
        #     "fromPlace": invoice.business.city,
        #     "fromPincode": invoice.business.pincode,
        #     "fromStateCode": invoice.business.state_code,
        #     "toGstin": invoice.party.gstin,
        #     "toAddr1": invoice.party.address,
        #     "toPlace": invoice.party.city,
        #     "toPincode": invoice.party.pincode,
        #     "toStateCode": invoice.party.state_code,
        #     "totalValue": float(invoice.get_total_amount()),
        #     "transMode": "1",  # Road
        #     "transDistance": 50,
        #     "transporterId": "TRANS12345",
        #     "vehicleNo": "MH12AB1234",
        # }

        # headers = {
        #     "Content-Type": "application/json",
        #     "Authorization": f"Bearer {get_gsp_token()}",
        #     "apikey": settings.GSP_API_KEY,
        #     "client_id": settings.GSP_CLIENT_ID,
        #     "client_secret": settings.GSP_CLIENT_SECRET
        # }

        # response = requests.post(
        #     f"{settings.GSP_API_BASE_URL}/ewaybill",
        #     json=payload,
        #     headers=headers
        # )

        # if response.status_code == 200:
        #     ewb_data = response.json()
        #     ewb = EWayBill.objects.create(
        #         invoice=invoice,
        #         ewb_number=ewb_data["ewbNo"],
        #         generated_date=datetime.strptime(ewb_data["ewayBillDate"], "%d/%m/%Y %H:%M:%S"),
        #         valid_upto=datetime.strptime(ewb_data["validUpto"], "%d/%m/%Y %H:%M:%S"),
        #         status=ewb_data["status"],
        #         request_payload=payload,
        #         response_payload=ewb_data
        #     )
        #     return ewb
        # else:
        #     raise Exception(f"GSP Error {response.status_code}: {response.text}")
        

class EWayBillViewSet(viewsets.ModelViewSet):
    queryset = EWayBill.objects.all()
    serializer_class = EWayBillSerializer

# def generate_einvoice(request, invoice_id):
#     try:
#         # Retrieve the invoice object
#         invoice = get_object_or_404(Invoice, id=invoice_id)
        
#         # Call the EInvoiceService to create or update the EInvoice
#         einvoice_obj = EInvoiceService.create_or_update_einvoice(invoice)
        
#         # If the EInvoice object was not created or updated
#         if not einvoice_obj:
#             return JsonResponse({"status": "error", "message": "Failed to generate or update e-invoice"}, status=500)
        
#         # Prepare the response data from the EInvoice object
#         response_data = {
#             "invoice_id": einvoice_obj.invoice.id,
#             "status": einvoice_obj.status,
#             "items": [
#                 {
#                     "item_id": item.item.id if item.item else None,
#                     "service_id": item.service.id if item.service else None,
#                     "item_name": item.item.itemName if item.item else None,
#                     "service_name": item.service.serviceName if item.service else None,
#                     "quantity": item.quantity,
#                     "unit_price": item.unit_price,
#                     "amount": item.amount,
#                     "gst_tax_rate": item.gstTaxRate.rate if item.gstTaxRate else None,
#                     "cgst_amount": item.get_cgst_amount(),
#                     "sgst_amount": item.get_sgst_amount(),
#                     "igst_amount": item.get_igst_amount(),
#                     "total_amount": item.get_amount(),
#                     # Add more fields as required from the invoice item model
#                 } for item in invoice.invoice_items.all()  # Accessing invoice_items from the related invoice
#             ],
#             "irn": einvoice_obj.irn,
#             "ack_no": einvoice_obj.ack_no,
#             "ack_date": einvoice_obj.ack_date,
#             "signed_invoice": einvoice_obj.signed_invoice,  # Assuming signed_invoice is base64 encoded or JSON
#             "signed_qr_code": einvoice_obj.signed_qr_code,  # Assuming signed QR code is base64 encoded
#             "qr_code_image": einvoice_obj.qr_code_image.url if einvoice_obj.qr_code_image else None,  # QR code image URL
#             "created_at": einvoice_obj.created_at,
#             "updated_at": einvoice_obj.updated_at
#         }

#         return JsonResponse({
#             "status": "success",
#             "message": "EInvoice created or updated successfully",
#             "data": response_data
#         }, status=200)
    
#     except Invoice.DoesNotExist:
#         # If the invoice with the provided ID doesn't exist
#         return JsonResponse({"status": "error", "message": "Invoice not found"}, status=404)

#     except Exception as e:
#         # Handle any unexpected errors
#         return JsonResponse({"status": "error", "message": str(e)}, status=500)
class GenerateEInvoiceView(APIView):
    def post(self, request):
        # Extract the invoice_id from the request data
        invoice_id = request.data.get('invoice_id')  # Use 'invoice_id' key to access

        if not invoice_id:
            return Response({'error': 'invoice_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Retrieve the invoice by ID
            invoice = Invoice.objects.get(id=invoice_id)
        except Invoice.DoesNotExist:
            return Response({'error': 'Invoice not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check if an E-Invoice already exists for this invoice
        if hasattr(invoice, 'e_invoice'):
            return Response({'error': 'E-Invoice already exists for this invoice.'}, status=status.HTTP_400_BAD_REQUEST)

        # Generate the e-invoice payload (you'll implement this logic in the generate_einvoice_payload function)
        payload = build_einvoice_payload(invoice)

        # Create the E-Invoice
        einvoice = EInvoice.objects.create(
            invoice=invoice,
            invoice_type=request.data.get('invoice_type', 'B2B'),
            supply_type=request.data.get('supply_type', 'Inter'),
            document_type=request.data.get('document_type', 'INV'),
            seller_gstin=request.data.get('seller_gstin'),
            buyer_gstin=request.data.get('buyer_gstin'),
            raw_invoice=payload
        )

        # Serialize the EInvoice data and return it in the response
        serializer = EInvoiceSerializer(einvoice)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
class GSTR1ReconciliationListView(generics.ListCreateAPIView):
    queryset = GSTR1Reconciliation.objects.all()
    serializer_class = GSTR1ReconciliationSerializer

class GSTR1ReconciliationDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = GSTR1Reconciliation.objects.all()
    serializer_class = GSTR1ReconciliationSerializer

class ReconcileInvoicesView(APIView):
    def post(self, request):
        """
        Trigger the reconciliation of invoices between the system and GST portal.
        """
        try:
            reconcile_invoices()  # This will reconcile the invoices and update the status
            return Response({"message": "Invoices reconciled successfully."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)