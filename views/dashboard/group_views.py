from uuid import UUID

from django.contrib import messages
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.models import (
    EmployeeModel,
    EmployerModel,
    GroupModel,
    NationalityModel,
    TeamModel,
)
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
        GroupModel.objects.filter(is_deleted=False, employer__isnull=True)
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
@role_permission_required("view_employermodel")
def employer_group_list(request, employer_id):
    employer = get_object_or_404(
        EmployerModel, pk=employer_id, is_deleted=False
    )
    employer_employees = EmployeeModel.objects.filter(
        employer=employer, is_deleted=False
    ).select_related("employer", "nationality")
    employees = employer_employees

    filters = {
        "search": request.GET.get("search", "").strip(),
        "nationality": request.GET.get("nationality", "").strip(),
        "pink_card": request.GET.get("pink_card", "").strip(),
        "passport_country": request.GET.get("passport_country", "").strip(),
        "province": request.GET.get("province", "").strip(),
        "district": request.GET.get("district", "").strip(),
        "sub_district": request.GET.get("sub_district", "").strip(),
    }
    if filters["search"]:
        employees = employees.filter(
            Q(full_name_en__icontains=filters["search"])
            | Q(name_th__icontains=filters["search"])
            | Q(passport_number__icontains=filters["search"])
        )
    if filters["nationality"]:
        try:
            filters["nationality"] = str(UUID(filters["nationality"]))
        except ValueError:
            messages.error(request, "Select a valid nationality.")
            filters["nationality"] = ""
        else:
            employees = employees.filter(nationality_id=filters["nationality"])
    if filters["pink_card"] == "yes":
        employees = employees.exclude(pink_card_number__isnull=True).exclude(
            pink_card_number=""
        )
    elif filters["pink_card"] == "no":
        employees = employees.filter(
            Q(pink_card_number__isnull=True) | Q(pink_card_number="")
        )
    if filters["passport_country"] == "myanmar":
        employees = employees.filter(
            Q(nationality__name__icontains="Myanmar")
            | Q(nationality__name__icontains="Burma")
            | Q(nationality__country_code__iexact="MM")
            | Q(nationality__country_code__iexact="MMR")
        )
    elif filters["passport_country"] == "cambodia":
        employees = employees.filter(
            Q(nationality__name__icontains="Cambodia")
            | Q(nationality__country_code__iexact="KH")
            | Q(nationality__country_code__iexact="KHM")
        )
    address_filters = {
        f"addresses__{field}": filters[field]
        for field in ("province", "district", "sub_district")
        if filters[field]
    }
    if address_filters:
        employees = employees.filter(**address_filters)
    employees = employees.distinct()

    active_teams = TeamModel.objects.filter(is_deleted=False).prefetch_related(
        Prefetch("employees", queryset=employees.order_by("full_name_en"))
    )
    groups = (
        GroupModel.objects.filter(
            employer=employer,
            is_deleted=False,
        )
        .prefetch_related(Prefetch("teams", queryset=active_teams))
        .order_by("name")
    )
    context = {
        "employer": employer,
        "groups": groups,
        "available_employees": employees.filter(team__isnull=True).order_by(
            "full_name_en"
        ),
        "nationalities": NationalityModel.objects.filter(is_deleted=False).order_by(
            "name"
        ),
        "filters": filters,
        "provinces": employer_employees
        .exclude(addresses__province__isnull=True)
        .exclude(addresses__province="")
        .values_list("addresses__province", flat=True)
        .distinct()
        .order_by("addresses__province"),
        "districts": employer_employees.exclude(
            addresses__district__isnull=True
        )
        .exclude(addresses__district="")
        .values_list("addresses__district", flat=True)
        .distinct()
        .order_by("addresses__district"),
        "sub_districts": employer_employees.exclude(
            addresses__sub_district__isnull=True
        )
        .exclude(addresses__sub_district="")
        .values_list("addresses__sub_district", flat=True)
        .distinct()
        .order_by("addresses__sub_district"),
    }
    return render(request, "dashboard/employer_group_list.html", context)


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
@role_permission_required("view_employermodel")
@role_permission_required("add_groupmodel")
@require_POST
def employer_group_create(request, employer_id):
    employer = get_object_or_404(
        EmployerModel, pk=employer_id, is_deleted=False
    )
    name = request.POST.get("name", "").strip()
    if not name:
        messages.error(request, "Group name is required.")
        return redirect("employer_group_list", employer_id=employer.id)

    GroupModel.objects.create(
        name=name,
        employer=employer,
        created_by=request.user,
    )
    messages.success(request, "Group created successfully.")
    return redirect("employer_group_list", employer_id=employer.id)


def _group_list_redirect(group):
    if group.employer_id:
        return redirect("employer_group_list", employer_id=group.employer_id)
    return redirect("independent_group_list")


@custom_login_required("dashboard_login")
@role_permission_required("change_groupmodel")
@require_POST
def group_update(request, pk):
    group = get_object_or_404(GroupModel, pk=pk, is_deleted=False)
    name = request.POST.get("name", "").strip()
    if not name:
        messages.error(request, "Group name is required.")
        return _group_list_redirect(group)

    group.name = name
    group.updated_by = request.user
    group.save()
    messages.success(request, "Group updated successfully.")
    return _group_list_redirect(group)


@custom_login_required("dashboard_login")
@role_permission_required("delete_groupmodel")
@require_POST
def group_delete(request, pk):
    group = get_object_or_404(GroupModel, pk=pk, is_deleted=False)
    destination = _group_list_redirect(group)
    group.delete()
    messages.success(
        request, "Group deleted. Its teams were deleted and their employees unassigned."
    )
    return destination


@custom_login_required("dashboard_login")
@role_permission_required("add_teammodel")
@require_POST
def team_create(request, group_id):
    group = get_object_or_404(GroupModel, pk=group_id, is_deleted=False)
    name = request.POST.get("name", "").strip()
    if not name:
        messages.error(request, "Team name is required.")
        return _group_list_redirect(group)

    TeamModel.objects.create(group=group, name=name, created_by=request.user)
    messages.success(request, "Team created successfully.")
    return _group_list_redirect(group)


@custom_login_required("dashboard_login")
@role_permission_required("change_teammodel")
@require_POST
def team_update(request, pk):
    team = get_object_or_404(TeamModel, pk=pk, is_deleted=False)
    destination = _group_list_redirect(team.group)
    name = request.POST.get("name", "").strip()
    if not name:
        messages.error(request, "Team name is required.")
        return destination

    team.name = name
    team.updated_by = request.user
    team.save()
    messages.success(request, "Team updated successfully.")
    return destination


@custom_login_required("dashboard_login")
@role_permission_required("delete_teammodel")
@require_POST
def team_delete(request, pk):
    team = get_object_or_404(TeamModel, pk=pk, is_deleted=False)
    destination = _group_list_redirect(team.group)
    team.delete()
    messages.success(request, "Team deleted. Its employees are now unassigned.")
    return destination


@custom_login_required("dashboard_login")
@role_permission_required("change_employeemodel")
@require_POST
def team_add_employee(request, pk):
    team = get_object_or_404(TeamModel, pk=pk, is_deleted=False)
    employee = get_object_or_404(
        EmployeeModel, pk=request.POST.get("employee"), is_deleted=False
    )
    if team.group.employer_id and employee.employer_id != team.group.employer_id:
        messages.error(request, "Select an employee from this employer.")
        return _group_list_redirect(team.group)
    if employee.team_id:
        messages.error(request, "This employee is already assigned to a team.")
        return _group_list_redirect(team.group)

    employee.team = team
    employee.updated_by = request.user
    employee.save(update_fields=["team", "updated_by", "updated_at"])
    messages.success(request, "Employee added to the team.")
    return _group_list_redirect(team.group)


@custom_login_required("dashboard_login")
@role_permission_required("change_employeemodel")
@require_POST
def team_remove_employee(request, pk, employee_id):
    team = get_object_or_404(TeamModel, pk=pk, is_deleted=False)
    destination = _group_list_redirect(team.group)
    employee = get_object_or_404(
        EmployeeModel, pk=employee_id, team=team, is_deleted=False
    )
    employee.team = None
    employee.updated_by = request.user
    employee.save(update_fields=["team", "updated_by", "updated_at"])
    messages.success(request, "Employee removed from the team.")
    return destination
