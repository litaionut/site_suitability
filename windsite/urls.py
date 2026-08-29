"""
URL configuration for windsite project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('projects.urls')),
    path('projects/', include('projects.urls')),
    path('sites/', include('sites.urls')),
    path('turbines/', include('turbines.urls')),
    path('climate/', include('climate.urls')),
    path('assessments/', include('assessments.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
