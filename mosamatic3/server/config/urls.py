from django.contrib import admin
from django.urls import include, path

from core.common.apiviews import health


urlpatterns = [
    path("", include("core.pages.urls")),
    path("", include("core.accounts.urls")),
    path("", include("core.datasets.urls")),
    path("", include("core.tasking.urls")),
    path("", include("core.pipelines.urls")),
    path("", include("core.manualeditor.urls")),
    path("", include("core.adminpanel.urls")),

    path("api/health/", health),

    path("api/auth/", include("core.accounts.apiurls")),
    path("api/datasets/", include("core.datasets.apiurls")),
    path("api/forms/", include("core.forms.apiurls")),
    path("api/tasks/", include("core.tasking.apiurls")),
    path("api/pipelines/", include("core.pipelines.apiurls")),
    path("api/manual-editor/", include("core.manualeditor.apiurls")),
    path("api/admin/", include("core.adminpanel.apiurls")),

    path("admin/", admin.site.urls),
]