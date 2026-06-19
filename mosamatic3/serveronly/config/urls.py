from django.contrib import admin
from django.urls import include, path

from core.common.apiviews import health
from core.accounts import apiviews as account_api_views
from core.datasets import apiviews as dataset_api_views
from core.forms import apiviews as form_api_views
from core.tasking import apiviews as task_api_views
from core.adminpanel import apiviews as admin_api_views
from core.pipelines import apiviews as pipeline_api_views


urlpatterns = [
    path("", include("core.pages.urls")),
    path("", include("core.accounts.urls")),
    path("", include("core.datasets.urls")),
    path("", include("core.tasking.urls")),
    path("", include("core.pipelines.urls")),
    path("", include("core.adminpanel.urls")),

    path("api/health", health),

    path("api/auth/register", account_api_views.register),
    path("api/auth/login", account_api_views.login),
    path("api/auth/me", account_api_views.me),

    path("api/datasets", dataset_api_views.datasets),
    path("api/datasets/output-results", dataset_api_views.delete_output_results),
    path("api/datasets/<uuid:dataset_id>", dataset_api_views.dataset_detail),
    path("api/datasets/<uuid:dataset_id>/download", dataset_api_views.download_dataset),

    path("api/forms", form_api_views.forms),

    path("api/tasks", task_api_views.tasks_list),
    path("api/tasks/<str:task_key>/schema", task_api_views.task_schema),
    path("api/tasks/<str:task_key>/parameters", task_api_views.task_parameters),
    path("api/tasks/<str:task_key>/run", task_api_views.task_run),
    path("api/tasks/<str:task_id>", task_api_views.task_status),
    path("api/tasks/<str:task_id>/cancel", task_api_views.task_cancel),

    path("api/pipelines", pipeline_api_views.pipeline_list),
    path("api/pipelines/run", pipeline_api_views.pipeline_run),
    path("api/pipelines/<uuid:pipeline_run_id>", pipeline_api_views.pipeline_status),
    path("api/pipelines/<uuid:pipeline_run_id>/cancel", pipeline_api_views.pipeline_cancel),

    path("api/admin/summary", admin_api_views.admin_summary),
    path("api/admin/users", admin_api_views.admin_users),
    path("api/admin/datasets", admin_api_views.admin_datasets),
    path("api/admin/users/<int:user_id>/block", admin_api_views.admin_block_user),
    path("api/admin/users/<int:user_id>/unblock", admin_api_views.admin_unblock_user),
    path("api/admin/users/<int:user_id>", admin_api_views.admin_delete_user),

    path("admin/", admin.site.urls),
]