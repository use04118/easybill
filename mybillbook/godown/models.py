from django.db import models
from users.models import Business


class State(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        app_label = 'godown'
        verbose_name = 'State'
        verbose_name_plural = 'States'
        ordering = ['name']

    def __str__(self):
        return self.name


class Godown(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="godowns")
    godownName = models.CharField(max_length=100)
    streetAddress = models.CharField(max_length=255, blank=True, null=True)
    state = models.ForeignKey(State, on_delete=models.SET_NULL, null=True, related_name='godowns')
    pincode = models.CharField(max_length=10, blank=True, null=True)
    city = models.CharField(max_length=100)

    class Meta:
        app_label = 'godown'
        unique_together = ['business', 'godownName']
        ordering = ['godownName']

    def __str__(self):
        return f"{self.godownName} ({self.business.name})"
