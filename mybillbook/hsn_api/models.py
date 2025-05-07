from django.db import models

# Create your models here.

class HSNCode(models.Model):
    hsn_cd = models.CharField(max_length=10, unique=True)  # HSN Code (e.g., '0101')
    hsn_description = models.TextField()  # HSN Description

    def __str__(self):
        return f"{self.hsn_cd} - {self.hsn_description[:50]}"