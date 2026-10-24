from django.contrib import messages
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.models import EmployeeModel, GroupModel, TeamModel
from decorators.role_decorator import role_permission_required
from utils.decorators import custom_login_required


@custom_login_required("dashboard_login")
@role_permission_required("view_employermodel")
def independent_group_list(request):
    active_teams = TeamModel.objects.filter(is_deleted=False).prefetch_related(
        Prefetch(
            "employees",
            queryset=EmployeeModel.objects.filter(is_deleted=False).select_related(
                "employer"
            ).order_by("employer__name_en", "full_name_en"),
        )
    )
    groups = (
        GroupModel.objects.filter(is_deleted=False)
        .prefetch_related(Prefetch("teams", queryset=active_teams))
        .order_by("name")
    )
    available_employees = (
        EmployeeModel.objects.filter(is_deleted=False, team__isnull=True)
        .select_related("employer")
        .order_by("employer__name_en", "full_name_en")
    )
    return render(
        request,
        "dashboard/independent_group_list.html",
        {
            "groups": groups,
            "available_employees": available_employees,
        },
    )


@custom_login_required("dashboard_login")
@role_permission_required("add_groupmodel")
@require_POST
def group_create(request):
    name = request.POST.get("name", "").strip()
    if not name:
        messages.error(request, "Group name is required.")
        return redirect("independent_group_list")

    GroupModel.objects.create(name=name, created_by=request.user)
    messages.success(request, "Group created successfully.")
    return redirect("independent_group_list")


@custom_login_required("dashboard_login")
@role_permission_required("change_groupmodel")
@require_POST
def group_update(request, pk):
    group = get_object_or_404(GroupModel, pk=pk, is_deleted=False)
    name = request.POST.get("name", "").strip()
    if not name:
        messages.error(request, "Group name is required.")
        return redirect("independent_group_list")

    group.name = name
    group.updated_by = request.user
    group.save()
    messages.success(request, "Group updated successfully.")
    return redirect("independent_group_list")


@custom_login_required("dashboard_login")
@role_permission_required("delete_groupmodel")
@require_POST
def group_delete(request, pk):
    group = get_object_or_404(GroupModel, pk=pk, is_deleted=False)
    group.delete()
    messages.success(
        request, "Group deleted. Its teams were deleted and their employees unassigned."
    )
    return redirect("independent_group_list")


@custom_login_required("dashboard_login")
@role_permission_required("add_teammodel")
@require_POST
def team_create(request, group_id):
    group = get_object_or_404(GroupModel, pk=group_id, is_deleted=False)
    name = request.POST.get("name", "").strip()
    if not name:
        messages.error(request, "Team name is required.")
        return redirect("independent_group_list")

    TeamModel.objects.create(group=group, name=name, created_by=request.user)
    messages.success(request, "Team created successfully.")
    return redirect("independent_group_list")


@custom_login_required("dashboard_login")
@role_permission_required("change_teammodel")
@require_POST
def team_update(request, pk):
    team = get_object_or_404(TeamModel, pk=pk, is_deleted=False)
    name = request.POST.get("name", "").strip()
    if not name:
        messages.error(request, "Team name is required.")
        return redirect("independent_group_list")

    team.name = name
    team.updated_by = request.user
    team.save()
    messages.success(request, "Team updated successfully.")
    return redirect("independent_group_list")


@custom_login_required("dashboard_login")
@role_permission_required("delete_teammodel")
@require_POST
def team_delete(request, pk):
    team = get_object_or_404(TeamModel, pk=pk, is_deleted=False)
    team.delete()
    messages.success(request, "Team deleted. Its employees are now unassigned.")
    return redirect("independent_group_list")


@custom_login_required("dashboard_login")
@role_permission_required("change_employeemodel")
@require_POST
def team_add_employee(request, pk):
    team = get_object_or_404(TeamModel, pk=pk, is_deleted=False)
    employee = get_object_or_404(
        EmployeeModel, pk=request.POST.get("employee"), is_deleted=False
    )
    if employee.team_id:
        messages.error(request, "This employee is already assigned to a team.")
        return redirect("independent_group_list")

    employee.team = team
    employee.updated_by = request.user
    employee.save(update_fields=["team", "updated_by", "updated_at"])
    messages.success(request, "Employee added to the team.")
    return redirect("independent_group_list")


@custom_login_required("dashboard_login")
@role_permission_required("change_employeemodel")
@require_POST
def team_remove_employee(request, pk, employee_id):
    team = get_object_or_404(TeamModel, pk=pk, is_deleted=False)
    employee = get_object_or_404(
        EmployeeModel, pk=employee_id, team=team, is_deleted=False
    )
    employee.team = None
    employee.updated_by = request.user
    employee.save(update_fields=["team", "updated_by", "updated_at"])
    messages.success(request, "Employee removed from the team.")
    return redirect("independent_group_list")
