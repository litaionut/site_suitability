"""
URL configuration for projects app.
"""
from django.urls import path
from . import views

app_name = 'projects'

urlpatterns = [
    path('', views.project_list, name='list'),
    path('create/', views.project_create, name='create'),
    path('<uuid:uuid>/', views.project_detail, name='detail'),
    path('<uuid:uuid>/edit/', views.project_edit, name='edit'),
]
