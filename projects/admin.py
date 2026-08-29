from django.contrib import admin
from .models import Project, ClassEnvelope


class ClassEnvelopeInline(admin.StackedInline):
    model = ClassEnvelope
    can_delete = False


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'uuid', 'created_at', 'updated_at']
    search_fields = ['name', 'notes']
    readonly_fields = ['uuid', 'created_at', 'updated_at']
    inlines = [ClassEnvelopeInline]


@admin.register(ClassEnvelope)
class ClassEnvelopeAdmin(admin.ModelAdmin):
    list_display = ['project', 'vref_i', 'vref_ii', 'vref_iii', 'iref_a', 'iref_b', 'iref_c']
    readonly_fields = ['project']
