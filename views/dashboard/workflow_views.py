from django.shortcuts import render, get_object_or_404
from django.db import models
from django.db.models import Count, Q
from datetime import date, timedelta

from utils.decorators import custom_login_required
from decorators.role_decorator import role_permission_required
from core.models import (
    EmployeeModel, EmployerModel, WorkflowTypeModel,
    WorkflowStageModel, EmployeeWorkflowModel, EmployeeWorkflowStageLogModel,
)

from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from core.models import WorkflowStageModel


def _add_employee_modal_context(request, workflow_type, employer_id, search):
    already_enrolled_ids = EmployeeWorkflowModel.objects.filter(
        workflow_type=workflow_type
    ).values_list("employee_id", flat=True)

    employees = (
        EmployeeModel.objects.filter(status="active")
        .exclude(id__in=already_enrolled_ids)
        .select_related("employer")
    )
    if employer_id:
        employees = employees.filter(employer_id=employer_id)
    if search:
        employees = employees.filter(
            Q(full_name_en__icontains=search) | Q(employer__name_en__icontains=search)
        )
    employees = employees.order_by("full_name_en")[:100]  # keep the modal light

    return {
        "workflow_type": workflow_type,
        "employees": employees,
        "employer_options": EmployerModel.objects.order_by("name_en"),
        "selected_employer_id": employer_id,
        "search": search,
    }


@custom_login_required("dashboard_login")
@role_permission_required("add_employeeworkflowmodel")
def workflow_add_employee_modal(request, workflow_type_code):
    """Opens the 'Add Employee' modal — lists employees not yet enrolled in this
    workflow type, optionally pre-filtered by employer (when opened from an
    employer row's own +Add button) and/or a live search box."""
    workflow_type = get_object_or_404(WorkflowTypeModel, code=workflow_type_code)
    employer_id = request.GET.get("employer_id", "")
    search = request.GET.get("search", "").strip()

    context = _add_employee_modal_context(request, workflow_type, employer_id, search)
    return render(request, "dashboard/components/workflow_add_employee_modal_content.html", context)


@custom_login_required("dashboard_login")
@role_permission_required("add_employeeworkflowmodel")
@require_POST
def workflow_add_employee(request, workflow_type_code):
    """Submits the checked employees from the modal — enrolls each one into
    this workflow type (creates EmployeeWorkflowModel rows) and re-renders the
    same modal with an updated (now-shorter) list, plus an HX-Trigger so the
    page behind it can refresh the employer counts/rows without a full reload."""
    workflow_type = get_object_or_404(WorkflowTypeModel, code=workflow_type_code)
    employee_ids = request.POST.getlist("employee_ids")
    employer_id = request.POST.get("employer_id", "")
    search = request.POST.get("search", "").strip()

    added = 0
    for emp_id in employee_ids:
        employee = EmployeeModel.objects.filter(id=emp_id).first()
        if not employee:
            continue
        _, created = EmployeeWorkflowModel.get_or_start(employee, workflow_type, user=request.user)
        if created:
            added += 1

    context = _add_employee_modal_context(request, workflow_type, employer_id, search)
    context["added_count"] = added
    response = render(request, "dashboard/components/workflow_add_employee_modal_content.html", context)
    if added:
        response["HX-Trigger"] = "workflowEmployeesAdded"
    return response


@custom_login_required("dashboard_login")
@role_permission_required("view_employeeworkflowmodel")
def workflow_dashboard(request, workflow_type_code="employer_entry_change"):
    workflow_type = get_object_or_404(WorkflowTypeModel, code=workflow_type_code)
    stages = workflow_type.stages.order_by("order")

    sibling_types = WorkflowTypeModel.objects.filter(group=workflow_type.group).order_by("order")

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
        "workflow_types": sibling_types,
        "show_tabs": sibling_types.count() > 1,
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

    template_name = (
        "dashboard/components/workflow_employee_cards_preparation.html"
        if workflow_type.group == "pre_production"
        else "dashboard/components/workflow_employee_cards.html"
    )

    context = {"workflows": workflows, "stages": stages, "employer": employer, "workflow_type": workflow_type}
    return render(request, template_name, context)


def _employee_workflow_card_context(workflow, workflow_type, stages):
    """Re-fetches the workflow with every relation the card partial needs, so a
    single HTMX POST can swap just that one card in place (no page reload)."""
    workflow = (
        EmployeeWorkflowModel.objects
        .select_related("employee", "employee__nationality", "employee__employer", "current_stage")
        .prefetch_related("stage_logs")
        .get(pk=workflow.pk)
    )
    return {
        "wf": workflow,
        "stages": stages,
        "employer": workflow.employee.employer,
        "workflow_type": workflow_type,
    }


@custom_login_required("dashboard_login")
@role_permission_required("change_employeeworkflowmodel")
@require_POST
def employee_workflow_stage_toggle(request, workflow_type_code, employee_id, stage_id):
    """Click on a stage chip (e.g. 'Pink Card Registration'): marks it done (and
    everything before it) or, if it's already done, undoes it. Employees are
    lazily enrolled into the workflow the first time a stage is touched."""
    workflow_type = get_object_or_404(WorkflowTypeModel, code=workflow_type_code)
    employee = get_object_or_404(EmployeeModel, id=employee_id)
    stage = get_object_or_404(WorkflowStageModel, id=stage_id, workflow_type=workflow_type)
    stages = list(workflow_type.stages.order_by("order"))

    workflow, _ = EmployeeWorkflowModel.get_or_start(employee, workflow_type, user=request.user)
    workflow.toggle_stage(stage, user=request.user)

    context = _employee_workflow_card_context(workflow, workflow_type, stages)
    return render(request, "dashboard/components/_workflow_employee_card.html", context)


@custom_login_required("dashboard_login")
@role_permission_required("change_employeeworkflowmodel")
@require_POST
def employee_workflow_set_status(request, workflow_type_code, employee_id, status):
    """Finish / Cancel / Reopen buttons — sets the overall status directly,
    independent of individual stage chips."""
    valid_statuses = dict(EmployeeWorkflowModel.STATUS_CHOICES)
    if status not in valid_statuses:
        return HttpResponseBadRequest("Invalid status.")

    workflow_type = get_object_or_404(WorkflowTypeModel, code=workflow_type_code)
    employee = get_object_or_404(EmployeeModel, id=employee_id)
    stages = list(workflow_type.stages.order_by("order"))

    workflow, _ = EmployeeWorkflowModel.get_or_start(employee, workflow_type, user=request.user)

    workflow.status = status
    workflow.updated_by = request.user
    if status == "finished" and stages:
        workflow.current_stage = stages[-1]
        for s in stages:
            EmployeeWorkflowStageLogModel.objects.get_or_create(workflow=workflow, stage=s)
    workflow.save()

    context = _employee_workflow_card_context(workflow, workflow_type, stages)
    return render(request, "dashboard/components/_workflow_employee_card.html", context)


@custom_login_required("dashboard_login")
@role_permission_required("view_workflowstagemodel")
def workflow_steps_modal(request, workflow_type_code):
    workflow_type = get_object_or_404(WorkflowTypeModel, code=workflow_type_code)
    stages = workflow_type.stages.order_by("order")
    context = {"workflow_type": workflow_type, "stages": stages}
    return render(request, "dashboard/components/workflow_steps_modal_content.html", context)


def _render_workflow_steps_modal(request, workflow_type, error_message=None):
    context = {"workflow_type": workflow_type, "stages": workflow_type.stages.order_by("order"), "error_message": error_message}
    return render(request, "dashboard/components/workflow_steps_modal_content.html", context)


@custom_login_required("dashboard_login")
@role_permission_required("add_workflowstagemodel")
@require_POST
def workflow_stage_create(request, workflow_type_code):
    workflow_type = get_object_or_404(WorkflowTypeModel, code=workflow_type_code)
    name = request.POST.get("name", "").strip()

    if not name:
        if request.headers.get("HX-Request"):
            return _render_workflow_steps_modal(request, workflow_type, "Step name is required.")
        return JsonResponse({"success": False, "error": "Step name is required."})

    last_order = workflow_type.stages.aggregate(models.Max("order"))["order__max"] or 0
    stage = WorkflowStageModel.objects.create(
        workflow_type=workflow_type, name=name, order=last_order + 1, created_by=request.user
    )
    if request.headers.get("HX-Request"):
        return _render_workflow_steps_modal(request, workflow_type)
    return JsonResponse({"success": True, "id": str(stage.id), "name": stage.name, "order": stage.order})


@custom_login_required("dashboard_login")
@role_permission_required("change_workflowstagemodel")
@require_POST
def workflow_stage_update(request, pk):
    stage = get_object_or_404(WorkflowStageModel, id=pk)
    name = request.POST.get("name", "").strip()

    if not name:
        if request.headers.get("HX-Request"):
            return _render_workflow_steps_modal(request, stage.workflow_type, "Step name is required.")
        return JsonResponse({"success": False, "error": "Step name is required."})

    stage.name = name
    stage.updated_by = request.user
    stage.save()
    if request.headers.get("HX-Request"):
        return _render_workflow_steps_modal(request, stage.workflow_type)
    return JsonResponse({"success": True, "name": stage.name})


@custom_login_required("dashboard_login")
@role_permission_required("delete_workflowstagemodel")
@require_POST
def workflow_stage_delete(request, pk):
    stage = get_object_or_404(WorkflowStageModel, id=pk)

    if stage.workflow_logs.exists() if hasattr(stage, "workflow_logs") else False:
        if request.headers.get("HX-Request"):
            return _render_workflow_steps_modal(request, stage.workflow_type, "This step is already in use and cannot be deleted.")
        return JsonResponse({"success": False, "error": "This step is already in use and cannot be deleted."})

    workflow_type = stage.workflow_type
    stage.delete()
    if request.headers.get("HX-Request"):
        return _render_workflow_steps_modal(request, workflow_type)
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
        if request.headers.get("HX-Request"):
            return _render_workflow_steps_modal(request, stage.workflow_type, "Cannot move further.")
        return JsonResponse({"success": False, "error": "Cannot move further."})

    stage.order, neighbor.order = neighbor.order, stage.order
    stage.save(update_fields=["order"])
    neighbor.save(update_fields=["order"])
    if request.headers.get("HX-Request"):
        return _render_workflow_steps_modal(request, stage.workflow_type)
    return JsonResponse({"success": True})