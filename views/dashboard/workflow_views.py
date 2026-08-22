from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Q
from datetime import date, timedelta

from utils.decorators import custom_login_required
from decorators.role_decorator import role_permission_required
from core.models import (
    EmployeeModel, EmployerModel, WorkflowTypeModel,
    WorkflowStageModel, EmployeeWorkflowModel,
)


@custom_login_required("dashboard_login")
@role_permission_required("view_employeeworkflowmodel")
def workflow_dashboard(request, workflow_type_code="employer_entry_change"):
    workflow_type = get_object_or_404(WorkflowTypeModel, code=workflow_type_code)
    stages = workflow_type.stages.order_by("order")

    workflows = EmployeeWorkflowModel.objects.filter(workflow_type=workflow_type).select_related(
        "employee", "employee__employer", "current_stage"
    )

    employer_id = request.GET.get("employer", "")
    search = request.GET.get("search", "")
    if search:
        workflows = workflows.filter(
            Q(employee__full_name_en__icontains=search) | Q(employee__employer__name_en__icontains=search)
        )
    if employer_id:
        workflows = workflows.filter(employee__employer_id=employer_id)

    # ===== Top stat cards =====
    today = date.today()
    stat_cards = {
        "total_employees": EmployeeModel.objects.filter(status="active").count(),
        "daily_check": workflows.filter(updated_at__date=today).count(),
        "not_started": workflows.filter(current_stage__isnull=True).count(),
        "cancelled": workflows.filter(status="cancelled").count(),
        "completed": workflows.filter(status="finished").count(),
        "active_projects": workflows.filter(status="in_progress").values("employee__employer").distinct().count(),
    }

    stage_counts = {
        stage.id: workflows.filter(current_stage=stage).count() for stage in stages
    }

    # ===== Employer-grouped list =====
    employers = (
        EmployerModel.objects.filter(employees__workflows__workflow_type=workflow_type)
        .annotate(
            total_count=Count("employees__workflows", filter=Q(employees__workflows__workflow_type=workflow_type), distinct=True),
            pending_count=Count("employees__workflows", filter=Q(employees__workflows__workflow_type=workflow_type, employees__workflows__status="in_progress"), distinct=True),
            done_count=Count("employees__workflows", filter=Q(employees__workflows__workflow_type=workflow_type, employees__workflows__status="finished"), distinct=True),
            cancel_count=Count("employees__workflows", filter=Q(employees__workflows__workflow_type=workflow_type, employees__workflows__status="cancelled"), distinct=True),
        )
        .distinct()
        .order_by("-employees__workflows__updated_at")
    )

    context = {
        "workflow_type": workflow_type,
        "workflow_types": WorkflowTypeModel.objects.order_by("order"),
        "stages": stages,
        "stat_cards": stat_cards,
        "stage_counts": stage_counts,
        "employers": employers,
        "search": search,
    }
    return render(request, "dashboard/workflow_dashboard.html", context)


@custom_login_required("dashboard_login")
@role_permission_required("view_employeeworkflowmodel")
def workflow_employer_employees(request, employer_id, workflow_type_code):
    workflow_type = get_object_or_404(WorkflowTypeModel, code=workflow_type_code)
    employer = get_object_or_404(EmployerModel, id=employer_id)
    stages = workflow_type.stages.order_by("order")

    workflows = EmployeeWorkflowModel.objects.filter(
        workflow_type=workflow_type, employee__employer=employer
    ).select_related("employee", "employee__nationality", "current_stage").prefetch_related("stage_logs")

    context = {"workflows": workflows, "stages": stages, "employer": employer}
    return render(request, "dashboard/components/workflow_employee_cards.html", context)