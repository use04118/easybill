from django.db import models

# Create your models here.

class SACCode(models.Model):
    sac_cd = models.CharField(max_length=10, unique=True)  # SAC Code (e.g., '0101')
    sac_description = models.TextField()  # SAC Description

    def __str__(self):
        return f"{self.sac_cd} - {self.sac_description[:50]}"