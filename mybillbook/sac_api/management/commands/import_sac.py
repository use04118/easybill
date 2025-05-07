import pandas as pd
from django.core.management.base import BaseCommand
from sac_api.models import SACCode

class Command(BaseCommand):
    help = 'Import SAC codes from an Excel file into the database'

    def handle(self, *args, **kwargs):
        # Read the Excel file
        file_path = 'D:\mybillbook\mybillbook\static\SAC_code.xlsx' # Adjust the path to your file
        df = pd.read_excel(file_path)

        # Loop through the rows and insert data into the database
        for index, row in df.iterrows():
            sac_cd = str(row['SAC_CD']).strip()
            sac_description = str(row['SAC_Description']).strip()
            
            # Insert the data into the SACCode model
            SACCode.objects.create(sac_cd=sac_cd, sac_description=sac_description)
        
        self.stdout.write(self.style.SUCCESS('Successfully imported SAC codes'))
