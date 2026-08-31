"""
URL configuration for climate app.
"""
from django.urls import path
from . import views

app_name = 'climate'

urlpatterns = [
    path('create/<int:site_pk>/', views.hub_climate_create, name='create'),
    path('<int:pk>/', views.hub_climate_detail, name='detail'),
    path('<int:pk>/edit/', views.hub_climate_edit, name='edit'),
    path('<int:hub_climate_pk>/import/', views.ti_bin_import_csv, name='ti_bin_import'),
]
