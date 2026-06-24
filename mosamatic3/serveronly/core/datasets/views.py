from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from ..models import Dataset

@login_required
def data_page(request):
    datasets = Dataset.objects.filter(owner=request.user).prefetch_related('files').order_by('-created_at')
    input_datasets = [d for d in datasets if d.kind != 'output']
    output_datasets = [d for d in datasets if d.kind == 'output']
    return render(request, 'datasets/data.html', {
        'input_datasets': input_datasets, 
        'output_datasets': output_datasets,
        'output_empty_message': 'No output results yet. Run a task to generate output datasets.',
    })

@login_required
def dataset_detail_page(request, dataset_id):
    dataset = get_object_or_404(Dataset.objects.prefetch_related('files'), id=dataset_id, owner=request.user)
    return render(request, 'datasets/dataset_detail.html', {'dataset': dataset})
