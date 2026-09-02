from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Q
from datetime import date, timedelta

from utils.decorators import custom_login_required
from decorators.role_decorator import role_permission_required
from core.models import (
    EmployeeModel, EmployerModel, WorkflowTypeModel,
    WorkflowStageModel, EmployeeWorkflowModel,
)

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from core.models import WorkflowStageModel


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

    # ===== Employer data for filters and grouped list =====
    employer_options = EmployerModel.objects.order_by("name_en")

    employers = (
        EmployerModel.objects.filter(employees__workflows__in=workflows)
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
        "employer_options": employer_options,
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


@custom_login_required("dashboard_login")
@role_permission_required("view_workflowstagemodel")
def workflow_steps_modal(request, workflow_type_code):
    workflow_type = get_object_or_404(WorkflowTypeModel, code=workflow_type_code)
    stages = workflow_type.stages.order_by("order")
    context = {"workflow_type": workflow_type, "stages": stages}
    return render(request, "dashboard/components/workflow_steps_modal_content.html", context)


@custom_login_required("dashboard_login")
@role_permission_required("add_workflowstagemodel")
@require_POST
def workflow_stage_create(request, workflow_type_code):
    workflow_type = get_object_or_404(WorkflowTypeModel, code=workflow_type_code)
    name = request.POST.get("name", "").strip()

    if not name:
        return JsonResponse({"success": False, "error": "Step name is required."})

    last_order = workflow_type.stages.aggregate(models.Max("order"))["order__max"] or 0
    stage = WorkflowStageModel.objects.create(
        workflow_type=workflow_type, name=name, order=last_order + 1, created_by=request.user
    )
    return JsonResponse({"success": True, "id": str(stage.id), "name": stage.name, "order": stage.order})


@custom_login_required("dashboard_login")
@role_permission_required("change_workflowstagemodel")
@require_POST
def workflow_stage_update(request, pk):
    stage = get_object_or_404(WorkflowStageModel, id=pk)
    name = request.POST.get("name", "").strip()

    if not name:
        return JsonResponse({"success": False, "error": "Step name is required."})

    stage.name = name
    stage.updated_by = request.user
    stage.save()
    return JsonResponse({"success": True, "name": stage.name})


@custom_login_required("dashboard_login")
@role_permission_required("delete_workflowstagemodel")
@require_POST
def workflow_stage_delete(request, pk):
    stage = get_object_or_404(WorkflowStageModel, id=pk)

    if stage.workflow_logs.exists() if hasattr(stage, "workflow_logs") else False:
        return JsonResponse({"success": False, "error": "This step is already in use and cannot be deleted."})

    stage.delete()
    return JsonResponse({"success": True})


@custom_login_required("dashboard_login")
@role_permission_required("change_workflowstagemodel")
@require_POST
def workflow_stage_reorder(request, pk, direction):
    stage = get_object_or_404(WorkflowStageModel, id=pk)

    if direction == "up":
        neighbor = (
            WorkflowStageModel.objects.filter(workflow_type=stage.workflow_type, order__lt=stage.order)
            .order_by("-order").first()
        )
    else:
        neighbor = (
            WorkflowStageModel.objects.filter(workflow_type=stage.workflow_type, order__gt=stage.order)
            .order_by("order").first()
        )

    if not neighbor:
        return JsonResponse({"success": False, "error": "Cannot move further."})

    stage.order, neighbor.order = neighbor.order, stage.order
    stage.save(update_fields=["order"])
    neighbor.save(update_fields=["order"])
    return JsonResponse({"success": True})