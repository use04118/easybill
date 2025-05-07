from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from .models import HSNCode
from .serializers import HSNCodeSerializer

class HSNCodeDetail(APIView):
    def get(self, request, hsn_cd):
        # Validate that the HSN code length is between 2 and 8 characters
        if not (2 <= len(hsn_cd) <= 8):
            raise ValidationError({"message": "HSN Code must be between 2 and 8 characters."})

        # Function to recursively find the correct HSN description
        # def get_valid_hsn_code(hsn_cd):
        #     while len(hsn_cd) >= 2:  # Keep checking as long as the length is at least 2
        #         try:
        #             hsn_code = HSNCode.objects.get(hsn_cd=hsn_cd)
        #             # Check if the description is valid and not "OTHER"
        #             if "OTHER" not in hsn_code.hsn_description.upper():
        #                 return hsn_code
        #             else:
        #                 # If the description is "OTHER", truncate the last 1 digits and try again
        #                 hsn_cd = hsn_cd[:-2]
        #         except HSNCode.DoesNotExist:
        #             # If no code is found, return None
        #             return None
        #     return None

        # Try to find the valid HSN code
        # hsn_code = get_valid_hsn_code(hsn_cd)
        hsn_code = HSNCode.objects.get(hsn_cd=hsn_cd)

        if hsn_code:
            # Serialize and return the valid HSN code
            serializer = HSNCodeSerializer(hsn_code)
            return Response(serializer.data)
        else:
            # If no valid code is found, return an error message
            return Response({"message": "HSN code not found or description is too generic."}, status=status.HTTP_404_NOT_FOUND)


class HSNCodeSearch(APIView):
    def get(self, request):
        query = request.query_params.get('q', '')
        
        if query:
            # Fetch HSN codes starting with the query value.
            hsn_codes = HSNCode.objects.filter(hsn_cd__startswith=query)
            
            # Check if the query is only the code (exact match) to allow "OTHER" descriptions for that code
            # if query and len(query) > 1:
            #     # Remove "OTHER" descriptions for regular search
            #     hsn_codes = hsn_codes.exclude(hsn_description__iexact="OTHER")
            
            # If results are found
            if hsn_codes.exists():
                serializer = HSNCodeSerializer(hsn_codes, many=True)
                return Response(serializer.data)
            else:
                return Response({"message": "No results found for the given query."}, status=status.HTTP_404_NOT_FOUND)
        
        return Response({"message": "No search query provided."}, status=status.HTTP_400_BAD_REQUEST)