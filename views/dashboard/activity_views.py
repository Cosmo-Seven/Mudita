from urllib.parse import urlencode

from django.shortcuts import render

from core.models import ActivityLogModel
from decorators.role_decorator import role_permission_required
from helpers.filters import filter_querysets
from utils.decorators import custom_login_required


ACTION_CHOICES = [
    ("view", "View"),
    ("create", "Create"),
    ("update", "Update"),
    ("delete", "Delete"),
    ("restore", "Restore"),
    ("login", "Login"),
    ("logout", "Logout"),
    ("action", "Other"),
]

METHOD_CHOICES = ["GET", "POST", "PUT", "PATCH", "DELETE"]


# ========================
# Activity Log List
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("view_activitylogmodel")
def activity_log_list(request):
    action = request.GET.get("action", "").strip()
    method = request.GET.get("method", "").strip().upper()

    logs = ActivityLogModel.objects.select_related("user").all()
    if action:
        logs = logs.filter(action=action)
    if method:
        logs = logs.filter(method=method)

    filters = filter_querysets(
        request,
        logs,
        search_fields=["user_email", "path", "route_name", "action"],
        date_field="created_at",
        order="-created_at",
    )

    query = {
        key: value
        for key, value in {
            "search": filters["search"],
            "action": action,
            "method": method,
            "entries": request.GET.get("entries", ""),
            "date": filters["date"],
            "date_range": filters["date_range"],
        }.items()
        if value
    }

    context = {
        "logs": filters["page_obj"],
        "action": action,
        "method": method,
        "action_choices": ACTION_CHOICES,
        "method_choices": METHOD_CHOICES,
        "page_query": urlencode(query),
        **filters,
    }
    return render(request, "dashboard/activity_log_list.html", context)
