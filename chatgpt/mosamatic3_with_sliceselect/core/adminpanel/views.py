from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from ..models import Dataset

@login_required
def admin_panel_page(request):
    if not request.user.is_staff:
        messages.error(request, 'Admin access required')
        return redirect('home')
    return render(request, 'adminpanel/admin_panel.html', {'users': User.objects.order_by('username'), 'datasets': Dataset.objects.all().prefetch_related('files')})
