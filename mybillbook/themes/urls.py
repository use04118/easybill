
from django.urls import path
from .views import Theme
urlpatterns = [
    path('theme/', Theme ,name='theme'),
]
