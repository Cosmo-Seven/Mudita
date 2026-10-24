from django.shortcuts import render, get_object_or_404
from django.db import models
from django.db.models import Count, Q
from django import forms
from datetime import date
from django.db import transaction
from django.utils.text import slugify

from utils.decorators import custom_login_required
from decorators.role_decorator import role_permission_required
from core.models import (
    EmployeeModel, EmployerModel, NationalityModel, WorkflowTypeModel,
    WorkflowStageModel, WorkflowJobModel, EmployeeWorkflowModel,
    EmployeeWorkflowStageLogModel,
)

from django.http import HttpResponseForbidden, JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from core.models import WorkflowStageModel
from views.dashboard.workflow_job_views import ensure_default_workflow_types


class WorkflowEmployeeCreateForm(forms.ModelForm):
    class Meta:
        model = EmployeeModel
        fields = [
            "employer",
            "title_th",
            "name_th",
            "prefix_en",
            "full_name_en",
            "name_suffix_en",
            "photo",
            "height_cm",
            "weight_kg",
            "father_name",
            "mother_name",
            "gender",
            "date_of_birth",
            "phone",
            "nationality",
            "passport_number",
            "passport_issue_place",
            "passport_issue_date",
            "passport_expiry_date",
            "pink_card_number",
            "visa_type",
            "visa_issue_place",
            "visa_expiry_date",
            "visa_stamp_date",
            "visa_number",
            "job_position",
            "job_description",
            "start_date",
            "work_permit_number",
            "work_permit_issue_date",
            "work_permit_expiry_date",
            "report_90day_date",
            "work_permit_type",
            "ra_number",
            "application_number",
            "identification_number",
            "tax_id_number",
            "worker_employer_code",
            "work_department",
            "worker_reference_number",
            "bank_name",
            "bank_account_number",
            "insurance_type",
            "diagnosed_hospital",
            "login_email",
        ]
        widgets = {
            "employer": forms.Select(),
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "passport_issue_date": forms.DateInput(attrs={"type": "date"}),
            "passport_expiry_date": forms.DateInput(attrs={"type": "date"}),
            "visa_expiry_date": forms.DateInput(attrs={"type": "date"}),
            "visa_stamp_date": forms.DateInput(attrs={"type": "date"}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "work_permit_issue_date": forms.DateInput(attrs={"type": "date"}),
            "work_permit_expiry_date": forms.DateInput(attrs={"type": "date"}),
            "report_90day_date": forms.DateInput(attrs={"type": "date"}),
            "job_description": forms.Textarea(attrs={"rows": 2}),
            "height_cm": forms.NumberInput(attrs={"step": "0.1", "min": "0"}),
            "weight_kg": forms.NumberInput(attrs={"step": "0.1", "min": "0"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employer"].queryset = EmployerModel.objects.filter(
            is_deleted=False
        ).order_by("name_en")
        self.fields["nationality"].queryset = NationalityModel.objects.all().order_by("name")
        for field in self.fields.values():
            css_class = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            field.widget.attrs["class"] = css_class
        self.fields["employer"].label = "Employer"
        self.fields["full_name_en"].label = "Full name (English)"
        self.fields["login_email"].label = "Email"
        for field_name, field in self.fields.items():
            if field.required:
                field.label = f"{field.label} *"


def _add_employee_modal_context(request, workflow_type, employer_id, search, workflow_job_id=""):
    workflow_job = WorkflowJobModel.objects.filter(
        pk=workflow_job_id,
        workflow_type=workflow_type,
        is_deleted=False,
    ).select_related("employer").first() if workflow_job_id else None
    if workflow_job:
        employer_id = str(workflow_job.employer_id)

    already_enrolled_ids = EmployeeWorkflowModel.objects.filter(
        workflow_type=workflow_type
    ).values_list("employee_id", flat=True)

    employees = EmployeeModel.objects.filter(
        is_deleted=False,
    ).exclude(id__in=already_enrolled_ids).select_related("employer")
    is_employer_change = workflow_type.code == "employer_entry_change"
    if employer_id and not is_employer_change:
        employees = employees.filter(employer_id=employer_id)
    if search:
        employees = employees.filter(
            Q(full_name_en__icontains=search) | Q(employer__name_en__icontains=search)
        )
    employees = employees.order_by("full_name_en")[:100]  # keep the modal light

    return {
        "workflow_type": workflow_type,
        "employees": employees,
        "employer_options": EmployerModel.objects.filter(is_deleted=False).order_by("name_en"),
        "selected_employer_id": employer_id,
        "workflow_job": workflow_job,
        "workflow_job_id": str(workflow_job.id) if workflow_job else "",
        "search": search,
        "can_create_employee": request.user.has_permission("add_employeemodel"),
        "manual_form": WorkflowEmployeeCreateForm(initial={"employer": employer_id}),
        "active_tab": "existing",
        "is_employer_change": is_employer_change,
    }


@custom_login_required("dashboard_login")
@role_permission_required("add_employeeworkflowmodel")
def workflow_add_employee_modal(request, workflow_type_code):
    """Opens the 'Add Employee' modal — lists employees not yet enrolled in this
    workflow type, optionally pre-filtered by employer (when opened from an
    employer row's own +Add button) and/or a live search box."""
    workflow_type = get_object_or_404(WorkflowTypeModel, code=workflow_type_code)
    employer_id = request.GET.get("employer_id", "")
    workflow_job_id = request.GET.get("workflow_job_id", "")
    search = request.GET.get("search", "").strip()

    context = _add_employee_modal_context(
        request, workflow_type, employer_id, search, workflow_job_id
    )
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
    mode = request.POST.get("mode", "existing")
    employee_ids = request.POST.getlist("employee_ids")
    employer_id = request.POST.get("employer_id", "")
    workflow_job_id = request.POST.get("workflow_job_id", "")
    search = request.POST.get("search", "").strip()
    workflow_job = WorkflowJobModel.objects.filter(
        pk=workflow_job_id,
        workflow_type=workflow_type,
        is_deleted=False,
    ).select_related("employer").first() if workflow_job_id else None

    if mode == "manual":
        if not request.user.has_permission("add_employeemodel"):
            return HttpResponseForbidden("You do not have permission to create employees.")

        form = WorkflowEmployeeCreateForm(request.POST, request.FILES)
        if form.is_valid():
            employee_employer_id = form.cleaned_data["employer"].id
            if workflow_job_id and (
                not workflow_job or workflow_job.employer_id != employee_employer_id
            ):
                context = _add_employee_modal_context(
                    request, workflow_type, str(employee_employer_id), search, workflow_job_id
                )
                context.update({
                    "active_tab": "manual",
                    "manual_form": form,
                    "selection_error": "Choose a work set for the selected employer.",
                })
                return render(request, "dashboard/components/workflow_add_employee_modal_content.html", context)

            with transaction.atomic():
                employee = form.save(commit=False)
                employee.created_by = request.user
                employee.save()
                EmployeeWorkflowModel.get_or_start(
                    employee,
                    workflow_type,
                    user=request.user,
                    workflow_job=workflow_job,
                )

            employer_id = str(employee.employer_id)
            context = _add_employee_modal_context(
                request, workflow_type, employer_id, "", workflow_job_id
            )
            context.update({
                "active_tab": "manual",
                "manual_form": WorkflowEmployeeCreateForm(initial={"employer": employer_id}),
                "created_employee": employee,
            })
            response = render(request, "dashboard/components/workflow_add_employee_modal_content.html", context)
            response["HX-Trigger"] = "workflowEmployeesAdded"
            return response

        employer_id = request.POST.get("employer", "")
        context = _add_employee_modal_context(
            request, workflow_type, employer_id, search, workflow_job_id
        )
        context.update({
            "active_tab": "manual",
            "manual_form": form,
        })
        return render(request, "dashboard/components/workflow_add_employee_modal_content.html", context)

    is_employer_change = workflow_type.code == "employer_entry_change"
    target_employer = None
    if is_employer_change:
        target_employer = EmployerModel.objects.filter(
            id=employer_id, is_deleted=False
        ).first()
        if not target_employer:
            context = _add_employee_modal_context(request, workflow_type, employer_id, search)
            context["selection_error"] = "Choose the new employer before adding employees."
            return render(request, "dashboard/components/workflow_add_employee_modal_content.html", context)

    selected_employer_id = target_employer.id if target_employer else employer_id
    if workflow_job_id and (
        not workflow_job or str(workflow_job.employer_id) != str(selected_employer_id)
    ):
        context = _add_employee_modal_context(
            request, workflow_type, employer_id, search, workflow_job_id
        )
        context["selection_error"] = "Choose a work set for the selected employer."
        return render(request, "dashboard/components/workflow_add_employee_modal_content.html", context)

    unique_employee_ids = set(employee_ids)
    if not unique_employee_ids:
        context = _add_employee_modal_context(
            request, workflow_type, employer_id, search, workflow_job_id
        )
        context["selection_error"] = "Choose at least one employee."
        return render(request, "dashboard/components/workflow_add_employee_modal_content.html", context)

    eligible_employees = EmployeeModel.objects.filter(
        id__in=employee_ids,
        is_deleted=False,
    ).exclude(
        id__in=EmployeeWorkflowModel.objects.filter(
            workflow_type=workflow_type
        ).values_list("employee_id", flat=True)
    )
    if not is_employer_change and employer_id:
        eligible_employees = eligible_employees.filter(employer_id=employer_id)

    eligible_employee_ids = {
        str(employee_id) for employee_id in eligible_employees.values_list("id", flat=True)
    }
    if eligible_employee_ids != unique_employee_ids:
        context = _add_employee_modal_context(
            request, workflow_type, employer_id, search, workflow_job_id
        )
        context["selection_error"] = "Some selected employees are unavailable or already added."
        return render(request, "dashboard/components/workflow_add_employee_modal_content.html", context)

    added = 0
    with transaction.atomic():
        for employee in eligible_employees.select_related("employer"):
            if target_employer:
                employee.employer = target_employer
                employee.updated_by = request.user
                employee.save(update_fields=["employer", "updated_by", "updated_at"])
            _, created = EmployeeWorkflowModel.get_or_start(
                employee,
                workflow_type,
                user=request.user,
                workflow_job=workflow_job,
            )
            if created:
                added += 1

    context = _add_employee_modal_context(
        request, workflow_type, employer_id, search, workflow_job_id
    )
    context["added_count"] = added
    response = render(request, "dashboard/components/workflow_add_employee_modal_content.html", context)
    if added:
        response["HX-Trigger"] = "workflowEmployeesAdded"
    return response


@custom_login_required("dashboard_login")
@role_permission_required("view_employeeworkflowmodel")
def workflow_dashboard(request, workflow_type_code="employer_entry_change"):
    ensure_default_workflow_types()
    workflow_type = get_object_or_404(WorkflowTypeModel, code=workflow_type_code)
    stages = workflow_type.stages.order_by("order")

    sibling_types = WorkflowTypeModel.objects.filter(is_deleted=False).order_by("order", "name")

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
    workflow_jobs = WorkflowJobModel.objects.filter(
        workflow_type=workflow_type,
        is_deleted=False,
    )
    if search:
        workflow_jobs = workflow_jobs.filter(
            Q(employer__name_en__icontains=search)
            | Q(project_name__icontains=search)
        )
    if employer_id:
        workflow_jobs = workflow_jobs.filter(employer_id=employer_id)

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
        EmployerModel.objects.filter(
            Q(employees__workflows__in=workflows)
            | Q(workflow_jobs__in=workflow_jobs)
        )
        .annotate(
            total_count=Count("employees__workflows", filter=Q(employees__workflows__workflow_type=workflow_type), distinct=True),
            pending_count=Count("employees__workflows", filter=Q(employees__workflows__workflow_type=workflow_type, employees__workflows__status="in_progress"), distinct=True),
            done_count=Count("employees__workflows", filter=Q(employees__workflows__workflow_type=workflow_type, employees__workflows__status="finished"), distinct=True),
            cancel_count=Count("employees__workflows", filter=Q(employees__workflows__workflow_type=workflow_type, employees__workflows__status="cancelled"), distinct=True),
        )
        .distinct()
        .order_by("name_en", "id")
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
        "can_add_job": request.user.has_permission("add_employeeworkflowmodel"),
        "show_create_job_button": (
            workflow_type.code in {"mou_import", "social_security"}
            or slugify(workflow_type.name) == "social-security-submission"
        ),
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
    workflow_jobs = WorkflowJobModel.objects.filter(
        workflow_type=workflow_type,
        employer=employer,
        is_deleted=False,
    ).annotate(employee_count=Count("workflows", distinct=True)).order_by("created_at")

    template_name = (
        "dashboard/components/workflow_employee_cards_preparation.html"
        if workflow_type.group == "pre_production"
        else "dashboard/components/workflow_employee_cards.html"
    )

    context = {
        "workflows": workflows,
        "workflow_jobs": workflow_jobs,
        "stages": stages,
        "employer": employer,
        "workflow_type": workflow_type,
    }
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
@require_POST
def workflow_stage_delete(request, pk):
    if not request.user.has_permission("delete_workflowstagemodel"):
        return HttpResponseForbidden("You do not have permission to delete workflow steps.")

    stage = get_object_or_404(WorkflowStageModel, id=pk)

    stage_is_in_use = (
        EmployeeWorkflowModel.objects.filter(current_stage=stage).exists()
        or EmployeeWorkflowStageLogModel.objects.filter(stage=stage).exists()
    )
    if stage_is_in_use:
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
    if direction not in {"up", "down"}:
        return HttpResponseBadRequest("Invalid direction.")

    stage = get_object_or_404(WorkflowStageModel, id=pk)
    workflow_type = stage.workflow_type
    with transaction.atomic():
        stages = list(
            WorkflowStageModel.objects.select_for_update()
            .filter(workflow_type=workflow_type)
            .order_by("order", "id")
        )
        current_index = next(index for index, item in enumerate(stages) if item.pk == stage.pk)
        target_index = current_index + (-1 if direction == "up" else 1)
        if target_index < 0 or target_index >= len(stages):
            can_move = False
        else:
            can_move = True
            stages[current_index], stages[target_index] = stages[target_index], stages[current_index]
            _save_workflow_stage_order(stages, request.user)

    if not can_move:
        if request.headers.get("HX-Request"):
            return _render_workflow_steps_modal(request, workflow_type, "Cannot move further.")
        return JsonResponse({"success": False, "error": "Cannot move further."})

    if request.headers.get("HX-Request"):
        return _render_workflow_steps_modal(request, workflow_type)
    return JsonResponse({"success": True})


def _save_workflow_stage_order(stages, user):
    if not stages:
        return

    temporary_order = max(stage.order for stage in stages) + len(stages) + 1
    for index, stage in enumerate(stages):
        stage.order = temporary_order + index
        stage.updated_by = user
        stage.save(update_fields=["order", "updated_by", "updated_at"])

    for order, stage in enumerate(stages, start=1):
        stage.order = order
        stage.save(update_fields=["order", "updated_at"])


@custom_login_required("dashboard_login")
@role_permission_required("change_workflowstagemodel")
@require_POST
def workflow_stage_move(request, pk, position):
    stage = get_object_or_404(WorkflowStageModel, id=pk)
    workflow_type = stage.workflow_type

    with transaction.atomic():
        stages = list(
            WorkflowStageModel.objects.select_for_update()
            .filter(workflow_type=workflow_type)
            .order_by("order", "id")
        )
        current_index = next(index for index, item in enumerate(stages) if item.pk == stage.pk)
        target_index = position - 1
        if target_index < 0 or target_index >= len(stages):
            return HttpResponseBadRequest("Invalid workflow step position.")

        moved_stage = stages.pop(current_index)
        stages.insert(target_index, moved_stage)
        if current_index != target_index:
            _save_workflow_stage_order(stages, request.user)

    if request.headers.get("HX-Request"):
        return _render_workflow_steps_modal(request, workflow_type)
    return JsonResponse({"success": True, "order": position})