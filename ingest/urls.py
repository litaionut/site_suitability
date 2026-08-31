"""
URL configuration for ingest app.
"""
from django.urls import path
from . import views

app_name = 'ingest'

urlpatterns = [
    path('upload/', views.upload_page, name='upload_page'),
    path('upload/file/', views.upload_file, name='upload_file'),
    path('preview/<str:session_id>/', views.preview_package, name='preview'),
    path('commit/<str:session_id>/', views.commit_package, name='commit'),
]
