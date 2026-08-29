"""
URL configuration for assessments app.
"""
from django.urls import path
from . import views

app_name = 'assessments'

urlpatterns = [
    path('', views.assessment_list, name='list'),
    path('<int:pk>/', views.assessment_detail, name='detail'),
    path('<int:pk>/report/', views.assessment_report, name='report'),
    path('run/<int:pk>/', views.run_assessment_view, name='run'),
    path('layout/<int:layout_pk>/setup/', views.layout_assessment_setup, name='layout_setup'),
    path('layout/<int:layout_pk>/result/<int:assessment_pk>/', views.layout_assessment_result, name='layout_result'),
]
