"""
URL configuration for turbines app.
"""
from django.urls import path
from . import views

app_name = 'turbines'

urlpatterns = [
    path('layout/create/<int:site_pk>/', views.layout_create, name='layout_create'),
    path('layout/<int:pk>/', views.layout_detail, name='layout_detail'),
    path('layout/<int:pk>/edit/', views.layout_edit, name='layout_edit'),
    path('layout/<int:layout_pk>/turbine/create/', views.turbine_create, name='turbine_create'),
    path('layout/<int:layout_pk>/turbine/import/', views.turbine_import_csv, name='turbine_import'),
    path('turbine/<int:pk>/edit/', views.turbine_edit, name='turbine_edit'),
    path('turbine/<int:pk>/delete/', views.turbine_delete, name='turbine_delete'),
]
