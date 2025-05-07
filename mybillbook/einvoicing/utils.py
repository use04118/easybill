from datetime import datetime
from .models import EWayBill, EInvoice,GSTR1Reconciliation
from sales.models import Invoice
import random
from django.core.exceptions import ValidationError
from django.utils.dateformat import format as date_format

def generate_eway_bill_view(invoice_id, transport_data=None):
    try:
        invoice = Invoice.objects.get(id=invoice_id)

        # Extracting transport-related fields from request data
        transporter_id = transport_data.get("transporter_id", "")
        transporter_name = transport_data.get("transporter_name", "")
        vehicle_number = transport_data.get("vehicle_number", "")
        mode = transport_data.get("mode", "Road")  # Expected to be 'Road', 'Rail', etc.
        distance = transport_data.get("distance", 1)

        # Dates (optional - may be user-defined or generated)
        generated_date_str = transport_data.get("generated_date")
        valid_upto_str = transport_data.get("valid_upto")

        generated_date = datetime.strptime(generated_date_str, "%Y-%m-%d %H:%M:%S") if generated_date_str else datetime.now()
        valid_upto = datetime.strptime(valid_upto_str, "%Y-%m-%d %H:%M:%S") if valid_upto_str else None

        # Construct payload for logging/storing
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

        # Simulated E-Way Bill response
        ewb_data = {
            "ewbNo": f"18100{random.randint(100000, 999999)}",
            "ewayBillDate": generated_date.strftime("%d/%m/%Y %H:%M:%S"),
            "validUpto": valid_upto.strftime("%d/%m/%Y %H:%M:%S") if valid_upto else "",
            "status": "Generated"
        }

        # Create and save EWayBill object
        ewb = EWayBill.objects.create(
            invoice=invoice,
            ewb_number=ewb_data["ewbNo"],
            generated_date=generated_date,
            valid_upto=valid_upto,
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
        print(f"Error generating E-Way Bill: {e}")
        return None
# class EInvoiceService:

#     @staticmethod
#     def generate_json(invoice):
#         """
#         Generates the raw invoice data to be stored.
#         This is the data before being signed by the GST portal.
#         """
#         return {
#             "customer": invoice.party.id,
#             "items": [
#                 {
#                     "item": item.item.id if item.item else None,
#                     "service": item.service.id if item.service else None,
#                     "quantity": float(item.quantity)
#                 } for item in invoice.invoice_items.all()
#             ]
#         }

#     @staticmethod
#     def create_or_update_einvoice(invoice, status='Pending', irn=None, ack_no=None, ack_date=None):
#         """
#         Creates or updates an EInvoice based on the provided invoice data.
#         Handles updating the EInvoice with the given status and other fields.
#         """
#         if not invoice:
#             raise ValueError("Invoice is required")

#         # Generate the raw invoice data
#         einvoice_data = EInvoiceService.generate_json(invoice)

#         # Add status-related fields and the raw_invoice
#         einvoice_obj, created = EInvoice.objects.update_or_create(
#             invoice=invoice,
#             defaults={
#                 "raw_invoice": einvoice_data,
#                 "status": status,
#                 "irn": irn,
#                 "ack_no": ack_no,
#                 "ack_date": ack_date
#             }
#         )

#         # Additional logic if needed after creation or update
#         if created:
#             # Logic for post-creation, if needed (e.g., notify or log)
#             pass

#         return einvoice_obj

def build_einvoice_payload(invoice):
    buyer = invoice.party
    seller = invoice.business
    invoice_items = invoice.invoice_items.all()

    item_list = []
    for idx, item in enumerate(invoice_items, 1):
        item_list.append({
            "SlNo": str(idx),
            "PrdDesc": str(item.item or item.service),
            "IsServc": "N" if item.item else "Y",
            "HsnCd": item.item.hsnCode if item.item else item.service.hsnCode,
            "Qty": float(item.quantity),
            # "Unit": item.item.unit_price if item.item else "OTH",
            "UnitPrice": float(item.unit_price),
            "TotAmt": float(item.amount),
            "Discount": float(item.discount),
            "AssAmt": float(item.get_price_item()),
            "GstRt": float(item.gstTaxRate.rate) if item.gstTaxRate else 0.0,
            "IgstAmt": float(item.get_igst_amount()),
            "CgstAmt": float(item.get_cgst_amount()),
            "SgstAmt": float(item.get_sgst_amount()),
            "CesRt": float(item.gstTaxRate.cess_rate) if item.gstTaxRate else 0.0,
            "CesAmt": float(item.get_cess_rate_amount()),
            "TotItemVal": float(item.get_amount()),
        })

    payload = {
        "Version": "1.1",
        "TranDtls": {
            "TaxSch": "GST",
            "SupTyp": "B2B",
            "RegRev": "Y",
            "IgstOnIntra": "N"
        },
        "DocDetails": {
            "Typ": "INV",
            "No": invoice.invoice_no,
            "Dt": date_format(invoice.date, "d/m/Y")
        },
        "SellerDetails": {
            "Gstin": seller.gstin,
            "LegalName": seller.name,
            # "TrdNm": seller.tradeName,
            "Addr1": seller.business_address,
            "Location": seller.city,
            "Pin": int(seller.pincode),
            "State": seller.state,
            "Phone": seller.phone,
            "Email": seller.email,
        },
        "BuyerDtls": {
            "Gstin": buyer.gstin,
            "LegalName": buyer.party_name,
            # "TrdNm": buyer.tradeName,
            "Pos": buyer.state,
            "Addr1": buyer.billing_address,
            "Location": buyer.city,
            "Pin": buyer.pincode,
            "State": buyer.state,
            "Phone": buyer.mobile_number,
            "Email": buyer.email,
        },
        "ItemList": item_list,
        "ValDtls": {
            "AssVal": float(invoice.get_taxable_amount()),
            "IgstVal": sum(float(i.get_igst_amount()) for i in invoice_items),
            "CgstVal": sum(float(i.get_cgst_amount()) for i in invoice_items),
            "SgstVal": sum(float(i.get_sgst_amount()) for i in invoice_items),
            "Discount": float(invoice.discount or 0),
            "TotInvVal": float(invoice.get_total_amount())
        }
    }
    return payload

def reconcile_invoices():
    """
    Utility function to reconcile local invoices with the e-invoices from the GST portal.
    It checks for the status of the invoice and creates the appropriate reconciliation records.
    """
    invoices = Invoice.objects.all()
    
    for invoice in invoices:
        # Try to fetch the matching e-invoice from the portal
        e_invoice = EInvoice.objects.filter(invoice_number=invoice.invoice_number, gstin=invoice.gstin).first()

        if e_invoice:
            # If an e-invoice is found, compare the values
            if invoice.total_amount == e_invoice.invoice_value:
                status = 'Matched'  # Set status to Matched if values match
            else:
                status = 'Mismatched'  # Set status to Mismatched if values don't match

            # Create or update the reconciliation record with automatic status assignment
            GSTR1Reconciliation.objects.update_or_create(
                invoice=invoice,
                gst_invoice_no=e_invoice.invoice_number,
                gst_invoice_date=e_invoice.invoice_date,
                gst_invoice_value=e_invoice.invoice_value,
                gst_gstin=e_invoice.gstin,
                local_invoice_value=invoice.total_amount,  # Use total_amount from Invoice model
                local_gstin=invoice.gstin,  # Use gstin from Invoice model
                defaults={'status': status, 'remarks': 'Reconciled automatically via script'}
            )
        else:
            # If no matching e-invoice is found, mark it as 'Missing in Portal'
            GSTR1Reconciliation.objects.update_or_create(
                invoice=invoice,
                defaults={'status': 'Missing in Portal', 'remarks': 'No matching e-invoice found'}
            )
    
    return True