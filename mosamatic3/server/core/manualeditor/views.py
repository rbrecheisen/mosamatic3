from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def manual_editor_page(request):
    return render(request, "manualeditor/manual_editor.html")