import pandas as pd
from django.core.management.base import BaseCommand
from hsn_api.models import HSNCode

class Command(BaseCommand):
    help = 'Import HSN codes from an Excel file into the database'

    def handle(self, *args, **kwargs):
        # Read the Excel file
        file_path = 'D:\mybillbook\mybillbook\static\HSN_SAC.xlsx' # Adjust the path to your file
        df = pd.read_excel(file_path)

        # Loop through the rows and insert data into the database
        for index, row in df.iterrows():
            hsn_cd = str(row['HSN_CD']).strip()
            hsn_description = str(row['HSN_Description']).strip()
            
            # Insert the data into the HSNCode model
            HSNCode.objects.create(hsn_cd=hsn_cd, hsn_description=hsn_description)
        
        self.stdout.write(self.style.SUCCESS('Successfully imported HSN codes'))
