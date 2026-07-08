from django.contrib import admin
from .models import (
    Dataset,
    DatasetFile,
    FormSubmission,
    TaskParameters,
    TaskRun,
    PipelineRun,
    PipelineStepRun,
    DicomImportSession,
    DicomImportFile,
)

admin.site.register(Dataset)
admin.site.register(DatasetFile)
admin.site.register(TaskParameters)
admin.site.register(TaskRun)
admin.site.register(PipelineRun)
admin.site.register(PipelineStepRun)
admin.site.register(FormSubmission)
admin.site.register(DicomImportSession)
admin.site.register(DicomImportFile)