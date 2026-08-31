"""
URL configuration for sites app.
"""
from django.urls import path
from . import views

app_name = 'sites'

urlpatterns = [
    path('create/<uuid:project_uuid>/', views.site_create, name='create'),
    path('<int:pk>/', views.site_detail, name='detail'),
    path('<int:pk>/edit/', views.site_edit, name='edit'),
    path('<int:pk>/compare/', views.site_compare_layouts, name='compare'),
]
