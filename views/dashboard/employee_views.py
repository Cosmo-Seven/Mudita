from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from datetime import date, datetime, timedelta
from uuid import UUID
from django.db import models
from django.db import transaction
from django.db.models import Prefetch
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.contrib.auth.password_validation import validate_password
from django.http import Http404
from django.urls import reverse
from django.utils import timezone
from utils.decorators import custom_login_required
from decorators.role_decorator import role_permission_required
from helpers.filters import filter_querysets
from helpers.exports import export_to_pdf, export_to_excel, filter_queryset_for_export
from helpers.employee_import import import_employees, read_employee_rows
from helpers.phone import format_mm_phone
from constants.message import CREATE, UPDATE, DELETE
from core.models import (
    EmployeeModel,
    EmployerModel,
    NationalityModel,
    AddressModel,
    DocumentTypeModel,
    EmployeeRequestModel,
    Employee90DayReportModel,
    UserModel,
)
from django.core.paginator import Paginator
from django.core.cache import cache
from django.utils.dateparse import parse_date


def _worker_account_input(request, employee=None):
    email = request.POST.get("login_email", "").strip()
    password = request.POST.get("worker_password", "")
    user = employee.user if employee else None
    if user and not email:
        email = user.email
    if not email:
        if password:
            messages.error(request, "Enter a login email to set a worker password.")
            return None
        return "", ""

    try:
        validate_email(email)
    except ValidationError:
        messages.error(request, "Enter a valid worker login email.")
        return None

    duplicate_users = UserModel.objects.filter(email__iexact=email)
    if user:
        duplicate_users = duplicate_users.exclude(pk=user.pk)
    if duplicate_users.exists():
        messages.error(request, "That email address is already used by another account.")
        return None
    if not user and not password:
        messages.error(request, "Set an initial password to create the worker login.")
        return None
    if password:
        account = UserModel(
            username=employee.full_name_en if employee else request.POST.get("full_name_en", "")
        )
        try:
            validate_password(password, user=account)
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
            return None
    return email, password


def _save_worker_account(employee, email, password):
    if not email:
        return
    if employee.user:
        user = employee.user
        user.email = email
        user.username = employee.full_name_en
        if password:
            user.set_password(password)
        user.save()
    else:
        user = UserModel.objects.create_user(
            email=email,
            username=employee.full_name_en,
            password=password,
            is_active=True,
            is_staff=False,
            is_superuser=False,
        )
        employee.user = user
    employee.login_email = email
    employee.save(update_fields=["user", "login_email", "updated_at"])


def _save_employee_home_address(request, employee):
    fields = ("address_line", "province", "district", "sub_district", "postal_code")
    if not any(field in request.POST for field in fields):
        return

    address_data = {field: request.POST.get(field, "").strip() for field in fields}
    address = (
        employee.addresses.filter(address_type="home")
        .order_by("created_at")
        .first()
    )
    if address:
        for field, value in address_data.items():
            setattr(address, field, value)
        address.updated_by = request.user
        address.save()
    elif any(address_data.values()):
        employee.addresses.create(
            address_type="home",
            created_by=request.user,
            **address_data,
        )


NINETY_DAY_INTERVAL = timedelta(days=90)


def _record_90day_report(request, employee):
    """Edit form မှ 90-day report ရက်စွဲ အသစ် ထည့်ပါက record သိမ်းပြီး
    နောက်တစ်ကြိမ် report ရက် (အသစ်ဆုံးရက်စွဲ + 90 ရက်) ကို အလိုအလျောက် တွက်သည်."""
    raw_date = (request.POST.get("report_90day_new_date") or "").strip()
    if raw_date:
        report_date = parse_date(raw_date)
        if report_date:
            Employee90DayReportModel.objects.get_or_create(
                employee=employee,
                report_date=report_date,
                defaults={"created_by": request.user},
            )

    latest = (
        employee.report_90day_records.order_by("-report_date")
        .values_list("report_date", flat=True)
        .first()
    )
    if latest:
        employee.report_90day_date = latest + NINETY_DAY_INTERVAL


@custom_login_required("dashboard_login")
@role_permission_required("view_employeemodel")
def employee_preview(request, pk):
    employee = get_object_or_404(EmployeeModel, id=pk)
    doc_types = DocumentTypeModel.objects.filter(applies_to__in=["employee", "both"]).order_by("created_at")

    # doc_type.code -> uploaded DocumentModel (upload ရှိရင်ပဲ dict ထဲ ပါမယ်)
    documents = {d.doc_type.code: d for d in employee.documents.select_related("doc_type")}

    context = {
        "employee": employee,
        "doc_types": doc_types,
        "documents": documents,
        "report_90day_records": employee.report_90day_records.order_by("-report_date"),
    }
    return render(request, "dashboard/components/employee_preview_modal_content.html", context)

# ========================
# Employee List
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("view_employeemodel")
def employee_list(request):
    employees = (
        EmployeeModel.objects.filter(is_deleted=False)
        .select_related("employer", "nationality")
        .prefetch_related("addresses")
    )

    search = request.GET.get("search", "")
    nationality_id = request.GET.get("nationality", "")
    insurance_type = request.GET.get("insurance_type", "")
    pink_card = request.GET.get("pink_card", "")          # "yes" / "no"
    passport_status = request.GET.get("passport_status", "")   # valid/expiring_soon/expired
    visa_status = request.GET.get("visa_status", "")
    bank_status = request.GET.get("bank_status", "")       # "yes" / "no"
    employer_id = request.GET.get("employer", "")
    passport_country = request.GET.get("passport_country", "")
    province = request.GET.get("province", "")
    district = request.GET.get("district", "")
    sub_district = request.GET.get("sub_district", "")
    if employer_id:
        try:
            employer_id = UUID(employer_id)
        except ValueError:
            messages.error(request, "Select a valid employer.")
            employer_id = ""

    expiry_date_filters = {
        "work_permit_expiry_range": "work_permit_expiry_date",
        "visa_expiry_range": "visa_expiry_date",
    }
    expiry_dates = {}
    for parameter, field in expiry_date_filters.items():
        raw_value = request.GET.get(parameter, "")
        if not raw_value:
            continue

        date_parts = [part.strip() for part in raw_value.split(" to ")]
        parsed_dates = [parse_date(part) for part in date_parts]
        if len(parsed_dates) not in (1, 2) or any(parsed_date is None for parsed_date in parsed_dates):
            messages.error(request, f"Invalid date for {parameter.replace('_', ' ')}.")
            continue
        if len(parsed_dates) == 2 and parsed_dates[0] > parsed_dates[1]:
            messages.error(request, f"Invalid date range for {parameter.replace('_', ' ')}.")
            continue

        expiry_dates[parameter] = raw_value
        lookup = "range" if len(parsed_dates) == 2 else "exact"
        value = parsed_dates if lookup == "range" else parsed_dates[0]
        employees = employees.filter(**{f"{field}__{lookup}": value})

    view_mode = request.GET.get("view", "table")
    per_page = int(request.GET.get("per_page", 25))

    if search:
        employees = employees.filter(
            models.Q(full_name_en__icontains=search)
            | models.Q(name_th__icontains=search)
            | models.Q(employee_number__icontains=search)
            | models.Q(passport_number__icontains=search)
            | models.Q(work_permit_number__icontains=search)
            | models.Q(employer__name_en__icontains=search)
        )

    if nationality_id:
        employees = employees.filter(nationality_id=nationality_id)

    if employer_id:
        employees = employees.filter(employer_id=employer_id)

    if passport_country == "myanmar":
        employees = employees.filter(
            models.Q(nationality__name__icontains="Myanmar")
            | models.Q(nationality__name__icontains="Burma")
            | models.Q(nationality__country_code__iexact="MM")
            | models.Q(nationality__country_code__iexact="MMR")
        )
    elif passport_country == "cambodia":
        employees = employees.filter(
            models.Q(nationality__name__icontains="Cambodia")
            | models.Q(nationality__country_code__iexact="KH")
            | models.Q(nationality__country_code__iexact="KHM")
        )

    if insurance_type:
        employees = employees.filter(insurance_type=insurance_type)

    if pink_card == "yes":
        employees = (
            employees.exclude(pink_card_number__isnull=True)
            .exclude(pink_card_number="")
            .exclude(pink_card_number__iexact="false")
        )
    elif pink_card == "no":
        employees = employees.filter(
            models.Q(pink_card_number__isnull=True)
            | models.Q(pink_card_number="")
            | models.Q(pink_card_number__iexact="false")
        )

    if bank_status == "yes":
        employees = employees.exclude(bank_account_number__isnull=True).exclude(bank_account_number="")
    elif bank_status == "no":
        employees = employees.filter(models.Q(bank_account_number__isnull=True) | models.Q(bank_account_number=""))

    if passport_status:
        today = date.today()
        if passport_status == "expired":
            employees = employees.filter(passport_expiry_date__lt=today)
        elif passport_status == "expiring_soon":
            employees = employees.filter(
                passport_expiry_date__gte=today,
                passport_expiry_date__lte=today + timedelta(days=90),
            )
        elif passport_status == "valid":
            employees = employees.filter(passport_expiry_date__gt=today + timedelta(days=90))

    if visa_status:
        today = date.today()
        if visa_status == "expired":
            employees = employees.filter(visa_expiry_date__lt=today)
        elif visa_status == "expiring_soon":
            employees = employees.filter(
                visa_expiry_date__gte=today,
                visa_expiry_date__lte=today + timedelta(days=90),
            )
        elif visa_status == "valid":
            employees = employees.filter(visa_expiry_date__gt=today + timedelta(days=90))

    if province:
        employees = employees.filter(addresses__address_type="home", addresses__province=province)
    if district:
        employees = employees.filter(addresses__address_type="home", addresses__district=district)
    if sub_district:
        employees = employees.filter(addresses__address_type="home", addresses__sub_district=sub_district)

    employees = employees.distinct().order_by("-created_at")

    paginator = Paginator(employees, per_page)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    current = page_obj.number
    total_pages = paginator.num_pages
    if total_pages <= 5:
        page_range = range(1, total_pages + 1)
    elif current <= 3:
        page_range = [1, 2, 3, 4, "...", total_pages]
    elif current >= total_pages - 2:
        page_range = [1, "...", total_pages - 3, total_pages - 2, total_pages - 1, total_pages]
    else:
        page_range = [1, "...", current - 1, current, current + 1, "...", total_pages]

    query_params = request.GET.copy()
    query_params.pop("page", None)

    context = {
        "employees": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "page_range": page_range,
        "page_query": query_params.urlencode(),
        "total_count": paginator.count,
        "nationalities": cache.get_or_set(
            "filter_opts:nationalities",
            lambda: list(NationalityModel.objects.all().order_by("name")),
            300,
        ),
        "employers": cache.get_or_set(
            "filter_opts:employers",
            lambda: list(EmployerModel.objects.filter(is_deleted=False).order_by("name_en")),
            300,
        ),
        "insurance_types": cache.get_or_set(
            "filter_opts:insurance_types",
            lambda: list(EmployeeModel.objects.exclude(insurance_type="")
                         .values_list("insurance_type", flat=True).distinct()),
            300,
        ),
        "view_mode": view_mode,
        "per_page": per_page,
        "search": search,
        "expiry_dates": {
            parameter: request.GET.get(parameter, "")
            for parameter in expiry_date_filters
        },
        "querystring": request.GET.urlencode(),
    }

    context["provinces"] = cache.get_or_set(
        "filter_opts:provinces",
        lambda: list(AddressModel.objects.filter(address_type="home").exclude(province="")
                     .values_list("province", flat=True).distinct().order_by("province")),
        300,
    )
    context["districts"] = cache.get_or_set(
        "filter_opts:districts",
        lambda: list(AddressModel.objects.filter(address_type="home").exclude(district="")
                     .values_list("district", flat=True).distinct().order_by("district")),
        300,
    )
    context["sub_districts"] = cache.get_or_set(
        "filter_opts:sub_districts",
        lambda: list(AddressModel.objects.filter(address_type="home").exclude(sub_district="")
                     .values_list("sub_district", flat=True).distinct().order_by("sub_district")),
        300,
    )

    return render(request, "dashboard/employee_list.html", context)


# ========================
# Resignation Requests (admin review → terminate)
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("view_employeemodel")
def resignation_list(request):
    resignations = (
        EmployeeRequestModel.objects.filter(
            is_deleted=False,
            request_type="resignation",
            employee__is_deleted=False,
        )
        .select_related("employee", "employee__employer")
    )

    if request.method == "POST":
        try:
            request_id = UUID(request.POST.get("request_id", ""))
        except (TypeError, ValueError):
            raise Http404("Resignation request not found.")

        resignation = get_object_or_404(resignations, id=request_id)
        action = request.POST.get("action", "")
        if action not in ("terminate", "reject"):
            messages.error(request, "Choose a valid action.")
            return redirect("resignation_list")

        resignation.staff_note = request.POST.get("staff_note", "").strip()
        resignation.reviewed_at = timezone.now()
        resignation.updated_by = request.user
        resignation.status = "approved" if action == "terminate" else "rejected"
        resignation.save(
            update_fields=[
                "status",
                "staff_note",
                "reviewed_at",
                "updated_by",
                "updated_at",
            ]
        )

        if action == "terminate":
            employee = resignation.employee
            employee.status = "terminated"
            employee.updated_by = request.user
            employee.save(update_fields=["status", "updated_by", "updated_at"])
            messages.success(request, f"{employee.full_name_en} has been terminated.")
        else:
            messages.success(request, "The resignation request has been rejected.")

        return redirect("resignation_list")

    status = request.GET.get("status", "")
    if status in dict(EmployeeRequestModel.STATUS_CHOICES):
        resignations = resignations.filter(status=status)

    context = {
        "resignations": resignations.order_by("-created_at"),
        "total_count": resignations.count(),
        "status_filter": status,
        "status_choices": EmployeeRequestModel.STATUS_CHOICES,
    }
    return render(request, "dashboard/resignation_list.html", context)


# ========================
# Terminated Employees
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("view_employeemodel")
def termination_list(request):
    employees = (
        EmployeeModel.objects.filter(is_deleted=False, status="terminated")
        .select_related("employer", "nationality")
        .prefetch_related(
            Prefetch(
                "requests",
                queryset=EmployeeRequestModel.objects.filter(
                    request_type="resignation", status="approved"
                ).order_by("-reviewed_at"),
                to_attr="approved_resignations",
            )
        )
    )

    search = request.GET.get("search", "")
    employer_id = request.GET.get("employer", "")
    if employer_id:
        try:
            employer_id = UUID(employer_id)
        except ValueError:
            messages.error(request, "Select a valid employer.")
            employer_id = ""

    if search:
        employees = employees.filter(
            models.Q(full_name_en__icontains=search)
            | models.Q(name_th__icontains=search)
            | models.Q(passport_number__icontains=search)
            | models.Q(employer__name_en__icontains=search)
        )
    if employer_id:
        employees = employees.filter(employer_id=employer_id)

    employees = employees.order_by("-updated_at")

    per_page = 25
    paginator = Paginator(employees, per_page)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    current = page_obj.number
    total_pages = paginator.num_pages
    if total_pages <= 5:
        page_range = range(1, total_pages + 1)
    elif current <= 3:
        page_range = [1, 2, 3, 4, "...", total_pages]
    elif current >= total_pages - 2:
        page_range = [1, "...", total_pages - 3, total_pages - 2, total_pages - 1, total_pages]
    else:
        page_range = [1, "...", current - 1, current, current + 1, "...", total_pages]

    query_params = request.GET.copy()
    query_params.pop("page", None)

    context = {
        "employees": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "page_range": page_range,
        "page_query": query_params.urlencode(),
        "total_count": paginator.count,
        "search": search,
        "employers": EmployerModel.objects.filter(is_deleted=False).order_by("name_en"),
    }
    return render(request, "dashboard/termination_list.html", context)


# ========================
# Employee Create
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("add_employeemodel")
@transaction.atomic
def employee_create(request):
    if request.method == "POST":
        account_input = _worker_account_input(request)
        if account_input is None:
            return redirect("employee_create")
        account_email, account_password = account_input

        employer = None
        employer_id = (request.POST.get("employer") or "").strip()
        if employer_id:
            employer = get_object_or_404(EmployerModel, id=employer_id)

        employee = EmployeeModel.objects.create(
            employer=employer,
            title_th=request.POST.get("title_th"),
            name_th=request.POST.get("name_th"),
            prefix_en=request.POST.get("prefix_en"),
            full_name_en=request.POST.get("full_name_en"),
            name_suffix_en=request.POST.get("name_suffix_en"),
            height_cm=request.POST.get("height_cm") or None,
            weight_kg=request.POST.get("weight_kg") or None,
            father_name=request.POST.get("father_name"),
            mother_name=request.POST.get("mother_name"),
            gender=request.POST.get("gender"),
            date_of_birth=request.POST.get("date_of_birth") or None,
            phone=format_mm_phone(request.POST.get("phone")),
            nationality_id=request.POST.get("nationality") or None,
            passport_number=request.POST.get("passport_number"),
            new_passport_number=request.POST.get("new_passport_number"),
            passport_issue_place=request.POST.get("passport_issue_place"),
            passport_issue_date=request.POST.get("passport_issue_date") or None,
            passport_expiry_date=request.POST.get("passport_expiry_date") or None,
            new_passport_expiry_date=request.POST.get("new_passport_expiry_date") or None,
            pink_card_number=request.POST.get("pink_card_number"),
            visa_type=request.POST.get("visa_type"),
            visa_issue_place=request.POST.get("visa_issue_place"),
            visa_issue_date=request.POST.get("visa_issue_date") or None,
            visa_expiry_date=request.POST.get("visa_expiry_date") or None,
            visa_stamp_date=request.POST.get("visa_stamp_date") or None,
            visa_number=request.POST.get("visa_number"),
            job_position=request.POST.get("job_position"),
            job_description=request.POST.get("job_description"),
            start_date=request.POST.get("start_date") or None,
            employee_number=request.POST.get("employee_number"),
            work_permit_number=request.POST.get("work_permit_number"),
            work_permit_issue_date=request.POST.get("work_permit_issue_date") or None,
            work_permit_expiry_date=request.POST.get("work_permit_expiry_date") or None,
            report_90day_date=request.POST.get("report_90day_date") or None,
            report_90day_start_date=request.POST.get("report_90day_start_date") or None,
            work_permit_type=request.POST.get("work_permit_type"),
            ra_number=request.POST.get("ra_number"),
            pakan_number=request.POST.get("pakan_number"),
            application_number=request.POST.get("application_number"),
            identification_number=request.POST.get("identification_number"),
            tax_id_number=request.POST.get("tax_id_number"),
            worker_employer_code=request.POST.get("worker_employer_code"),
            work_department=request.POST.get("work_department"),
            bank_name=request.POST.get("bank_name"),
            bank_account_number=request.POST.get("bank_account_number"),
            worker_reference_number=request.POST.get("worker_reference_number"),
            insurance_type=request.POST.get("insurance_type"),
            diagnosed_hospital=request.POST.get("diagnosed_hospital"),
            internal_note=request.POST.get("internal_note"),
            login_email=account_email,
            created_by=request.user,
        )

        _save_employee_home_address(request, employee)
        _save_worker_account(employee, account_email, account_password)
        if request.FILES.get("photo"):
            employee.photo = request.FILES.get("photo")
            employee.save()

        messages.success(request, CREATE)
        return redirect("employee_list")

    context = {
        "employers": EmployerModel.objects.filter(is_deleted=False).order_by("name_en"),
        "nationalities": NationalityModel.objects.all().order_by("name"),
    }
    return render(request, "dashboard/employee_create.html", context)


# ========================
# Employee Update
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("change_employeemodel")
@transaction.atomic
def employee_update(request, pk):
    employee = get_object_or_404(EmployeeModel, id=pk)

    if request.method == "POST":
        account_input = _worker_account_input(request, employee)
        if account_input is None:
            return redirect("employee_update", pk=employee.id)
        account_email, account_password = account_input

        if "employer" in request.POST:
            employee.employer_id = request.POST.get("employer") or None
        employee.title_th = request.POST.get("title_th")
        employee.name_th = request.POST.get("name_th")
        employee.prefix_en = request.POST.get("prefix_en")
        employee.full_name_en = request.POST.get("full_name_en")
        employee.name_suffix_en = request.POST.get("name_suffix_en")
        employee.height_cm = request.POST.get("height_cm") or None
        employee.weight_kg = request.POST.get("weight_kg") or None
        employee.father_name = request.POST.get("father_name")
        employee.mother_name = request.POST.get("mother_name")
        employee.gender = request.POST.get("gender")
        employee.date_of_birth = request.POST.get("date_of_birth") or None
        employee.phone = format_mm_phone(request.POST.get("phone"))
        employee.nationality_id = request.POST.get("nationality") or None
        employee.passport_number = request.POST.get("passport_number")
        employee.new_passport_number = request.POST.get("new_passport_number")
        employee.passport_issue_place = request.POST.get("passport_issue_place")
        employee.passport_issue_date = request.POST.get("passport_issue_date") or None
        employee.passport_expiry_date = request.POST.get("passport_expiry_date") or None
        employee.new_passport_expiry_date = request.POST.get("new_passport_expiry_date") or None
        employee.pink_card_number = request.POST.get("pink_card_number")
        employee.visa_type = request.POST.get("visa_type")
        employee.visa_issue_place = request.POST.get("visa_issue_place")
        employee.visa_issue_date = request.POST.get("visa_issue_date") or None
        employee.visa_expiry_date = request.POST.get("visa_expiry_date") or None
        employee.visa_stamp_date = request.POST.get("visa_stamp_date") or None
        employee.visa_number = request.POST.get("visa_number")
        employee.job_position = request.POST.get("job_position")
        employee.job_description = request.POST.get("job_description")
        employee.start_date = request.POST.get("start_date") or None
        employee.employee_number = request.POST.get("employee_number")
        employee.work_permit_number = request.POST.get("work_permit_number")
        employee.work_permit_issue_date = request.POST.get("work_permit_issue_date") or None
        employee.work_permit_expiry_date = request.POST.get("work_permit_expiry_date") or None
        employee.report_90day_start_date = request.POST.get("report_90day_start_date") or None
        employee.work_permit_type = request.POST.get("work_permit_type")
        employee.ra_number = request.POST.get("ra_number")
        employee.pakan_number = request.POST.get("pakan_number")
        employee.application_number = request.POST.get("application_number")
        employee.identification_number = request.POST.get("identification_number")
        employee.tax_id_number = request.POST.get("tax_id_number")
        employee.worker_employer_code = request.POST.get("worker_employer_code")
        employee.work_department = request.POST.get("work_department")
        employee.bank_name = request.POST.get("bank_name")
        employee.bank_account_number = request.POST.get("bank_account_number")
        employee.worker_reference_number = request.POST.get("worker_reference_number")
        employee.insurance_type = request.POST.get("insurance_type")
        employee.diagnosed_hospital = request.POST.get("diagnosed_hospital")
        employee.internal_note = request.POST.get("internal_note")
        employee.login_email = account_email
        employee.status = request.POST.get("status", employee.status)

        if request.FILES.get("photo"):
            if employee.photo:
                employee.photo.delete(save=False)
            employee.photo = request.FILES.get("photo")

        employee.updated_by = request.user
        _record_90day_report(request, employee)
        employee.save()
        _save_employee_home_address(request, employee)
        _save_worker_account(employee, account_email, account_password)
        messages.success(request, UPDATE)
        return redirect("employee_list")

    context = {
        "employee": employee,
        "home_address": employee.addresses.filter(address_type="home")
        .order_by("created_at")
        .first(),
        "employers": EmployerModel.objects.filter(is_deleted=False).order_by("name_en"),
        "nationalities": NationalityModel.objects.all().order_by("name"),
        "report_90day_records": employee.report_90day_records.order_by("-report_date"),
    }
    return render(request, "dashboard/employee_update.html", context)


# ========================
# Employee Detail
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("view_employeemodel")
def employee_detail(request, pk):
    employee = get_object_or_404(EmployeeModel, id=pk)
    context = {
        "employee": employee,
        "addresses": employee.addresses.all(),
        "documents": employee.documents.all(),
    }
    return render(request, "dashboard/employee_detail.html", context)


# ========================
# Employee Employment History (sidebar)
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("view_employeemodel")
def employee_employment_history(request, pk):
    employee = get_object_or_404(EmployeeModel, id=pk)
    history = employee.employment_history.order_by("-effective_date")
    return render(
        request,
        "dashboard/employee_employment_history.html",
        {"employee": employee, "history": history},
    )


# ========================
# Employee Delete
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("delete_employeemodel")
def employee_delete(request, pk):
    employee = get_object_or_404(EmployeeModel, id=pk)
    if request.method == "POST":
        if employee.photo:
            employee.photo.delete(save=False)

        employee.soft_delete(user=request.user)
        messages.success(request, DELETE)

        next_query = request.POST.get("next", "").lstrip("?")
        if next_query:
            return redirect(f"{reverse('employee_list')}?{next_query}")
        return redirect("employee_list")


# ========================
# Employee Export PDF / Excel
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("view_employeemodel")
def employee_export_pdf(request):
    search = request.GET.get("search", "")
    date = request.GET.get("date", "")
    date_range = request.GET.get("date_range", "")

    employees = filter_queryset_for_export(
        EmployeeModel.objects.select_related("employer"),
        search=search,
        date=date,
        date_range=date_range,
        search_fields=["full_name_en", "passport_number"],
        date_field="created_at",
    )

    rows = [
        [
            idx,
            e.full_name_en,
            e.employer.name_en if e.employer else "",
            e.passport_number or "",
            e.work_permit_number or "",
            e.get_status_display(),
        ]
        for idx, e in enumerate(employees, start=1)
    ]

    filename = f"employee_{datetime.now().strftime('%b-%d-%Y')}.pdf"
    return export_to_pdf(
        filename,
        ["No", "Name", "Employer", "Passport No.", "Work Permit No.", "Status"],
        rows,
    )


@custom_login_required("dashboard_login")
@role_permission_required("view_employeemodel")
def employee_export_excel(request):
    search = request.GET.get("search", "")
    date = request.GET.get("date", "")
    date_range = request.GET.get("date_range", "")

    employees = filter_queryset_for_export(
        EmployeeModel.objects.select_related("employer", "nationality", "team__group"),
        search=search,
        date=date,
        date_range=date_range,
        search_fields=["full_name_en", "employee_number", "passport_number"],
        date_field="created_at",
    )

    def fmt_date(value):
        return value.strftime("%d %b %Y") if value else ""

    columns = [
        "No", "Employee No", "Prefix", "Name (EN)", "Name Suffix", "Name (TH)",
        "Gender", "Date of Birth", "Age", "Height (cm)", "Weight (kg)",
        "Father Name", "Mother Name", "Nationality", "Phone", "Employer",
        "Group", "Team", "Job Position", "Job Description", "Work Department",
        "Start Date", "Passport No.", "New Passport No.", "Passport Issue Place",
        "Passport Issue Date", "Passport Expiry Date", "New Passport Expiry Date",
        "Pink Card", "Visa Type", "Visa No.", "Visa Issue Place", "Visa Issue Date",
        "Visa Expiry Date", "Visa Stamp Date", "Work Permit No.", "Work Permit Type",
        "Work Permit Issue Date", "Work Permit Expiry Date", "90-Day Report Date",
        "90-Day Start Date", "RA No.", "Pakan No.", "Application No.",
        "Identification No.", "Tax ID No.", "Worker Employer Code",
        "Worker Reference No.", "Bank Name", "Bank Account No.", "Insurance Type",
        "Diagnosed Hospital", "Login Email", "Internal Note", "Status",
    ]

    rows = [
        [
            idx,
            e.employee_number or "",
            e.prefix_en or "",
            e.full_name_en or "",
            e.name_suffix_en or "",
            f"{e.title_th or ''} {e.name_th or ''}".strip(),
            e.get_gender_display() or "",
            fmt_date(e.date_of_birth),
            e.age if e.age is not None else "",
            float(e.height_cm) if e.height_cm is not None else "",
            float(e.weight_kg) if e.weight_kg is not None else "",
            e.father_name or "",
            e.mother_name or "",
            e.nationality.name if e.nationality else "",
            e.phone or "",
            e.employer.name_en if e.employer else "",
            e.team.group.name if e.team else "",
            e.team.name if e.team else "",
            e.job_position or "",
            e.job_description or "",
            e.work_department or "",
            fmt_date(e.start_date),
            e.passport_number or "",
            e.new_passport_number or "",
            e.passport_issue_place or "",
            fmt_date(e.passport_issue_date),
            fmt_date(e.passport_expiry_date),
            fmt_date(e.new_passport_expiry_date),
            e.pink_card_number or "",
            e.visa_type or "",
            e.visa_number or "",
            e.visa_issue_place or "",
            fmt_date(e.visa_issue_date),
            fmt_date(e.visa_expiry_date),
            fmt_date(e.visa_stamp_date),
            e.work_permit_number or "",
            e.work_permit_type or "",
            fmt_date(e.work_permit_issue_date),
            fmt_date(e.work_permit_expiry_date),
            fmt_date(e.report_90day_date),
            fmt_date(e.report_90day_start_date),
            e.ra_number or "",
            e.pakan_number or "",
            e.application_number or "",
            e.identification_number or "",
            e.tax_id_number or "",
            e.worker_employer_code or "",
            e.worker_reference_number or "",
            e.bank_name or "",
            e.bank_account_number or "",
            e.insurance_type or "",
            e.diagnosed_hospital or "",
            e.login_email or "",
            e.internal_note or "",
            e.get_status_display() or "",
        ]
        for idx, e in enumerate(employees, start=1)
    ]

    filename = f"employee_{datetime.now().strftime('%b-%d-%Y')}.xlsx"
    return export_to_excel(filename, columns, rows)


# ========================
# Employee Import (Excel)
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("add_employeemodel")
def employee_import(request):
    if request.method != "POST":
        return redirect("employee_list")

    upload = request.FILES.get("file")
    if not upload:
        messages.error(request, "Excel ဖိုင် ရွေးပေးပါ။")
        return redirect("employee_list")
    if not upload.name.lower().endswith((".xlsx", ".xlsm")):
        messages.error(request, "Excel ဖိုင် (.xlsx) ပဲ တင်လို့ရပါတယ်။")
        return redirect("employee_list")

    employer = None
    employer_id = request.POST.get("employer", "").strip()
    if employer_id:
        employer = EmployerModel.objects.filter(
            id=employer_id, is_deleted=False
        ).first()
        if employer is None:
            messages.error(request, "ရွေးထားတဲ့ အလုပ်ရှင် မတွေ့ပါ။")
            return redirect("employee_list")

    with_accounts = request.POST.get("create_accounts") == "on"

    try:
        rows, meta = read_employee_rows(upload)
    except Exception as error:  # noqa: BLE001 - ဖိုင်ဖတ်လို့မရရင် အသိပေးရန်
        messages.error(request, f"Excel ဖိုင် ဖတ်လို့မရပါ: {error}")
        return redirect("employee_list")

    if meta.get("error"):
        messages.error(request, meta["error"])
        return redirect("employee_list")
    if not rows:
        messages.error(request, "Excel ထဲမှာ အလုပ်သမား data မတွေ့ပါ။")
        return redirect("employee_list")

    created, skipped, errors = import_employees(
        rows, employer=employer, created_by=request.user, with_accounts=with_accounts
    )

    request.session["employee_import_created"] = created
    context = {
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "total_rows": len(rows),
        "employer": employer,
        "with_accounts": with_accounts,
        "header_row": meta.get("header_row"),
    }
    return render(request, "dashboard/employee_import_result.html", context)


@custom_login_required("dashboard_login")
@role_permission_required("view_employeemodel")
def employee_import_credentials(request):
    created = request.session.get("employee_import_created") or []
    rows = [
        (
            item["employee_number"],
            item["name"],
            item["passport_number"],
            item["login_email"],
            item["password"],
        )
        for item in created
    ]
    filename = f"employee_logins_{datetime.now().strftime('%b-%d-%Y-%H%M')}.xlsx"
    return export_to_excel(
        filename,
        ["Emp. No.", "Name", "Passport No.", "Login email", "Password"],
        rows,
    )