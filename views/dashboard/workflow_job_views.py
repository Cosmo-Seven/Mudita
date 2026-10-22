"""Workflow type management and employee workflow job creation."""
from datetime import date, timedelta
from uuid import UUID

from django.db.models import Count
from django.shortcuts import render, get_object_or_404
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from utils.decorators import custom_login_required
from decorators.role_decorator import role_permission_required
from core.models import (
    EmployeeWorkflowModel,
    EmployerModel,
    WorkflowJobModel,
    WorkflowTypeModel,
)

GROUP_CHOICES = [
    ("employer_notification", "Processing (documents after employer change)"),
    ("pre_production", "Preparation (getting ready to change employer)"),
    ("employer_transfer", "Employer Transfer"),
]

def _build_default_stage_names(name):
    """Create a workflow-specific stage set for new/custom workflow types so each
    job type keeps its own independent step list instead of reusing a shared
    generic template."""
    return (
        f"Start {name}",
        f"Review {name}",
        f"Complete {name}",
    )


DEFAULT_WORKFLOW_TYPES = (
    {
        "code": "employer_entry_change",
        "name": "Employer Entry / Change",
        "group": "employer_notification",
        "icon": "ti ti-user-plus",
        "subtitle": "Entry and change notification workflow",
        "order": 1,
        "stages": ("Applied", "Review", "Completed"),
    },
    {
        "code": "employer_exit_notice",
        "name": "Employer Exit Notice",
        "group": "employer_notification",
        "icon": "ti ti-user-minus",
        "subtitle": "Departure notification workflow",
        "order": 2,
        "stages": ("Document check", "Approval", "Closed"),
    },
    {
        "code": "pre_production_preparation",
        "name": "Pre-Production Preparation",
        "group": "pre_production",
        "icon": "ti ti-clipboard-check",
        "subtitle": "Preparation before transfer or change",
        "order": 3,
        "stages": ("Prepare docs", "Review", "Ready"),
    },
    {
        "code": "employer_transfer_package",
        "name": "Employer Transfer Package",
        "group": "employer_transfer",
        "icon": "ti ti-arrows-right-left",
        "subtitle": "Transfer package workflow",
        "order": 4,
        "stages": ("Package check", "Transfer", "Completed"),
    },
    {
        "code": "mou_import",
        "name": "MOU Import",
        "group": "employer_notification",
        "icon": "ti ti-file-import",
        "subtitle": "Import MOU registration flow",
        "order": 5,
        "stages": ("Collect documents", "Review", "Completed"),
    },
    {
        "code": "renewal_mou",
        "name": "Renewal MOU",
        "group": "employer_notification",
        "icon": "ti ti-refresh",
        "subtitle": "Renewal workflow for active MOU",
        "order": 6,
        "stages": ("Collect renewal docs", "Review", "Completed"),
    },
)


def _seed_workflow_type_stages(workflow_type, stage_names=None):
    """Ensure the workflow type has its own step list and does not inherit or
    overwrite stages from another type."""
    stage_names = list(stage_names or [])
    existing_names = list(workflow_type.stages.order_by("order").values_list("name", flat=True))
    if existing_names:
        return
    if not stage_names:
        stage_names = _build_default_stage_names(workflow_type.name)
    for stage_order, stage_name in enumerate(stage_names, start=1):
        workflow_type.stages.get_or_create(
            order=stage_order,
            defaults={"name": stage_name},
        )


def ensure_default_workflow_types():
    """Create the built-in workflow templates the app expects to exist."""
    for workflow in DEFAULT_WORKFLOW_TYPES:
        workflow_type, _ = WorkflowTypeModel.objects.get_or_create(
            code=workflow["code"],
            defaults={
                "name": workflow["name"],
                "group": workflow["group"],
                "icon": workflow["icon"],
                "subtitle": workflow["subtitle"],
                "order": workflow["order"],
            },
        )
        _seed_workflow_type_stages(workflow_type, workflow["stages"])
    return WorkflowTypeModel.objects.filter(is_deleted=False).order_by("order", "name")


def _jobs_queryset():
    ensure_default_workflow_types()
    return (
        WorkflowTypeModel.objects
        .annotate(stage_count=Count("stages", distinct=True),
                  employee_count=Count("workflows", distinct=True))
        .order_by("order", "name")
    )


def _unique_code(name, exclude_pk=None):
    base = slugify(name).replace("-", "_") or "job"
    code, i = base, 2
    while WorkflowTypeModel.objects.filter(code=code).exclude(pk=exclude_pk).exists():
        code = f"{base}_{i}"
        i += 1
    return code


def _render_table(request, message=None, error=None):
    return render(request, "dashboard/components/workflow_job_table.html",
                  {
                      "jobs": _jobs_queryset(),
                      "message": message,
                      "error": error,
                      "can_add_job": request.user.has_permission("add_employeeworkflowmodel"),
                  })


def _render_form(request, job=None, errors=None, values=None):
    return render(request, "dashboard/components/workflow_job_form.html", {
        "job": job, "errors": errors or {}, "values": values or {},
        "group_choices": GROUP_CHOICES,
    })


def _render_create_job_form(request, errors=None, values=None):
    ensure_default_workflow_types()
    values = values or {}
    return render(request, "dashboard/components/workflow_job_create_form.html", {
        "errors": errors or {},
        "values": values,
        "workflow_types": WorkflowTypeModel.objects.filter(is_deleted=False).order_by("order", "name"),
        "employers": EmployerModel.objects.filter(status="active").order_by("name_en"),
    })


@custom_login_required("dashboard_login")
@role_permission_required("view_workflowtypemodel")
def workflow_job_list(request):
    today = date.today()
    calendar_month = today.replace(day=1)
    requested_month = request.GET.get("month", "")
    if requested_month:
        try:
            calendar_month = date.fromisoformat(f"{requested_month}-01")
        except ValueError:
            pass

    calendar_start = calendar_month - timedelta(
        days=(calendar_month.weekday() + 1) % 7
    )
    calendar_dates = [
        calendar_start + timedelta(days=offset) for offset in range(42)
    ]
    calendar_counts = dict(
        EmployeeWorkflowModel.objects.filter(
            workflow_type__is_deleted=False,
            appointment_date__range=(calendar_start, calendar_dates[-1]),
        )
        .exclude(status="cancelled")
        .values("appointment_date")
        .annotate(count=Count("id"))
        .values_list("appointment_date", "count")
    )
    calendar_days = [
        {
            "date": calendar_date,
            "is_current_month": (
                calendar_date.month == calendar_month.month
                and calendar_date.year == calendar_month.year
            ),
            "is_today": calendar_date == today,
            "appointment_count": calendar_counts.get(calendar_date, 0),
        }
        for calendar_date in calendar_dates
    ]
    upcoming_appointments = (
        EmployeeWorkflowModel.objects.filter(
            workflow_type__is_deleted=False,
            appointment_date__range=(today, today + timedelta(days=6)),
        )
        .exclude(status="cancelled")
        .select_related("employee", "workflow_type")
        .order_by("appointment_date", "employee__full_name_en")
    )
    previous_month = (calendar_month - timedelta(days=1)).replace(day=1)
    next_month = (calendar_month.replace(day=28) + timedelta(days=4)).replace(day=1)

    return render(request, "dashboard/workflow_job_list.html", {
        "jobs": _jobs_queryset(),
        "can_add_job": request.user.has_permission("add_employeeworkflowmodel"),
        "can_add_workflow_type": request.user.has_permission("add_workflowtypemodel"),
        "calendar_month": calendar_month,
        "calendar_weekdays": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        "calendar_days": calendar_days,
        "calendar_previous_month": previous_month.strftime("%Y-%m"),
        "calendar_next_month": next_month.strftime("%Y-%m"),
        "upcoming_appointments": upcoming_appointments,
    })


@custom_login_required("dashboard_login")
@role_permission_required("add_employeeworkflowmodel")
def workflow_job_create(request):
    if request.method == "GET":
        return _render_create_job_form(request, values={
            "workflow_type_id": request.GET.get("workflow_type_id", ""),
            "employer_id": request.GET.get("employer_id", ""),
            "project_name": request.GET.get("project_name", ""),
        })

    values = {
        "workflow_type_id": request.POST.get("workflow_type_id", "").strip(),
        "employer_id": request.POST.get("employer_id", "").strip(),
        "project_name": request.POST.get("project_name", "").strip(),
    }
    errors = {}

    try:
        workflow_type_id = UUID(values["workflow_type_id"])
    except (ValueError, TypeError):
        workflow_type_id = None
    workflow_type = WorkflowTypeModel.objects.filter(
        pk=workflow_type_id, is_deleted=False
    ).first()
    if not workflow_type:
        errors["workflow_type_id"] = "Choose a work type."

    try:
        employer_id = UUID(values["employer_id"])
    except (ValueError, TypeError):
        employer_id = None
    employer = EmployerModel.objects.filter(pk=employer_id, status="active").first()
    if not employer:
        errors["employer_id"] = "Choose an active employer."

    if len(values["project_name"]) > 255:
        errors["project_name"] = "Project name must be 255 characters or fewer."

    if errors:
        return _render_create_job_form(request, errors=errors, values=values)

    WorkflowJobModel.objects.create(
        workflow_type=workflow_type,
        employer=employer,
        project_name=values["project_name"],
        created_by=request.user,
    )

    response = render(request, "dashboard/components/workflow_job_create_form.html", {
        "saved": True,
        "workflow_type": workflow_type,
        "employer": employer,
        "project_name": values["project_name"],
    })
    response["HX-Refresh"] = "true"
    return response


@custom_login_required("dashboard_login")
@role_permission_required("add_workflowtypemodel")
def workflow_type_create(request):
    if request.method == "GET":
        return _render_form(request)

    name = request.POST.get("name", "").strip()
    values = {k: request.POST.get(k, "").strip() for k in ("name", "code", "group", "icon", "subtitle", "order")}
    errors = {}
    if not name:
        errors["name"] = "Job name is required."
    code = values["code"] or _unique_code(name)
    if WorkflowTypeModel.objects.filter(code=code).exists():
        errors["code"] = "This code is already used."
    if values["group"] not in dict(GROUP_CHOICES):
        errors["group"] = "Choose a group."
    if errors:
        return _render_form(request, errors=errors, values=values)

    next_order = (WorkflowTypeModel.objects.order_by("-order").values_list("order", flat=True).first() or 0) + 1
    workflow_type = WorkflowTypeModel.objects.create(
        code=code, name=name, group=values["group"],
        icon=values["icon"] or "ti ti-chart-bar", subtitle=values["subtitle"],
        order=int(values["order"]) if values["order"].isdigit() else next_order,
        created_by=request.user,
    )
    _seed_workflow_type_stages(workflow_type, _build_default_stage_names(name))
    response = render(request, "dashboard/components/workflow_job_form.html",
                      {"job": None, "saved": True, "group_choices": GROUP_CHOICES, "errors": {}, "values": {}})
    response["HX-Refresh"] = "true"
    return response


@custom_login_required("dashboard_login")
@role_permission_required("change_workflowtypemodel")
def workflow_job_update(request, pk):
    job = get_object_or_404(WorkflowTypeModel, pk=pk)
    if request.method == "GET":
        return _render_form(request, job=job)

    values = {k: request.POST.get(k, "").strip() for k in ("name", "group", "icon", "subtitle", "order")}
    errors = {}
    if not values["name"]:
        errors["name"] = "Job name is required."
    if values["group"] not in dict(GROUP_CHOICES):
        errors["group"] = "Choose a group."
    if errors:
        return _render_form(request, job=job, errors=errors, values=values)

    job.name = values["name"]
    job.group = values["group"]
    job.icon = values["icon"] or job.icon
    job.subtitle = values["subtitle"]
    if values["order"].isdigit():
        job.order = int(values["order"])
    job.updated_by = request.user
    job.save()   # `code` is intentionally NOT editable: urls/sidebar reference it
    response = render(request, "dashboard/components/workflow_job_form.html",
                      {"job": job, "saved": True, "group_choices": GROUP_CHOICES, "errors": {}, "values": {}})
    response["HX-Refresh"] = "true"
    return response


@custom_login_required("dashboard_login")
@role_permission_required("delete_workflowtypemodel")
@require_POST
def workflow_job_delete(request, pk):
    job = get_object_or_404(WorkflowTypeModel, pk=pk)
    if EmployeeWorkflowModel.objects.filter(workflow_type=job).exists():
        return _render_table(request, error=f"'{job.name}' still has employees in it. Remove them first.")
    name = job.name
    job.delete()   # its steps cascade
    return _render_table(request, message=f"'{name}' deleted.")