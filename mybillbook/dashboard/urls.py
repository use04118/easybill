from django.urls import path
from .views import dashboard_data, dashboard_profit, summary_counts, top_parties_combined

urlpatterns = [
    path('dashboard/', dashboard_data, name='dashboard_data'),
    path('profit/', dashboard_profit, name='dashboard_profit'),
    path('summary-counts/', summary_counts, name='summary_counts'),
    path('top-parties-combined/', top_parties_combined, name='top_parties_combined'),
]
