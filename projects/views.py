"""
Views for projects app.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Project
from .forms import ProjectForm


def project_list(request):
    """List all projects."""
    projects = Project.objects.all()
    return render(request, 'projects/list.html', {'projects': projects})


def project_create(request):
    """Create a new project."""
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save()
            messages.success(request, f'Project "{project.name}" created successfully.')
            return redirect('projects:detail', uuid=project.uuid)
    else:
        form = ProjectForm()
    
    return render(request, 'projects/form.html', {'form': form, 'title': 'Create Project'})


def project_detail(request, uuid):
    """Project detail view."""
    project = get_object_or_404(Project, uuid=uuid)
    sites = project.sites.all()
    return render(request, 'projects/detail.html', {'project': project, 'sites': sites})


def project_edit(request, uuid):
    """Edit an existing project."""
    project = get_object_or_404(Project, uuid=uuid)
    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            project = form.save()
            messages.success(request, f'Project "{project.name}" updated successfully.')
            return redirect('projects:detail', uuid=project.uuid)
    else:
        form = ProjectForm(instance=project)
    
    return render(request, 'projects/form.html', {'form': form, 'title': 'Edit Project', 'project': project})
