from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from .models import SACCode
from .serializers import SACCodeSerializer

class SACCodeDetail(APIView):
    def get(self, request, sac_cd):
        # Validate that the SAC code length is between 2 and 8 characters
        if not (2 <= len(sac_cd) <= 8):
            raise ValidationError({"message": "SAC Code must be between 2 and 8 characters."})

        sac_code = SACCode.objects.get(sac_cd=sac_cd)
        if sac_code:
            # Serialize and return the valid SAC code
            serializer = SACCodeSerializer(sac_code)
            return Response(serializer.data)
        else:
            # If no valid code is found, return an error message
            return Response({"message": "SAC code not found or description is too generic."}, status=status.HTTP_404_NOT_FOUND)


class SACCodeSearch(APIView):
    def get(self, request):
        query = request.query_params.get('q', '')
        
        if query:
            # Fetch SAC codes starting with the query value.
            sac_codes = SACCode.objects.filter(sac_cd__startswith=query)
            
            # Check if the query is only the code (exact match) to allow "OTHER" descriptions for that code
            # if query and len(query) > 1:
            #     # Remove "OTHER" descriptions for regular search
            #     sac_codes = sac_codes.exclude(sac_description__iexact="OTHER")
            
            # If results are found
            if sac_codes.exists():
                serializer = SACCodeSerializer(sac_codes, many=True)
                return Response(serializer.data)
            else:
                return Response({"message": "No results found for the given query."}, status=status.HTTP_404_NOT_FOUND)
        
        return Response({"message": "No search query provided."}, status=status.HTTP_400_BAD_REQUEST)