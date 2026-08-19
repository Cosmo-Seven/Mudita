from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from datetime import date, timedelta
from django.db import models
from utils.decorators import custom_login_required
from decorators.role_decorator import role_permission_required
from helpers.filters import filter_querysets
from helpers.exports import export_to_pdf, export_to_excel, filter_queryset_for_export
from helpers.phone import format_mm_phone
from constants.message import CREATE, UPDATE, DELETE
from core.models import EmployeeModel, EmployerModel, NationalityModel, AddressModel, DocumentTypeModel
from django.core.paginator import Paginator

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
    }
    return render(request, "dashboard/components/employee_preview_modal_content.html", context)

# ========================
# Employee List
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("view_employeemodel")
def employee_list(request):
    employees = EmployeeModel.objects.select_related("employer", "nationality").prefetch_related("addresses")

    search = request.GET.get("search", "")
    nationality_id = request.GET.get("nationality", "")
    work_permit_type = request.GET.get("work_permit_type", "")
    insurance_type = request.GET.get("insurance_type", "")
    pink_card = request.GET.get("pink_card", "")          # "yes" / "no"
    passport_status = request.GET.get("passport_status", "")   # valid/expiring_soon/expired
    visa_status = request.GET.get("visa_status", "")
    bank_status = request.GET.get("bank_status", "")       # "yes" / "no"
    province = request.GET.get("province", "")
    district = request.GET.get("district", "")
    sub_district = request.GET.get("sub_district", "")
    view_mode = request.GET.get("view", "card")
    per_page = int(request.GET.get("per_page", 25))

    if search:
        employees = employees.filter(
            models.Q(full_name_en__icontains=search)
            | models.Q(name_th__icontains=search)
            | models.Q(passport_number__icontains=search)
            | models.Q(work_permit_number__icontains=search)
            | models.Q(employer__name_en__icontains=search)
        )

    if nationality_id:
        employees = employees.filter(nationality_id=nationality_id)

    if work_permit_type:
        employees = employees.filter(work_permit_type=work_permit_type)

    if insurance_type:
        employees = employees.filter(insurance_type=insurance_type)

    if pink_card == "yes":
        employees = employees.exclude(pink_card_number__isnull=True).exclude(pink_card_number="")
    elif pink_card == "no":
        employees = employees.filter(models.Q(pink_card_number__isnull=True) | models.Q(pink_card_number=""))

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

    context = {
        "employees": page_obj,
        "page_obj": page_obj,
        "total_count": paginator.count,
        "nationalities": NationalityModel.objects.all().order_by("name"),
        "work_permit_types": EmployeeModel.objects.exclude(work_permit_type="").values_list(
            "work_permit_type", flat=True
        ).distinct(),
        "insurance_types": EmployeeModel.objects.exclude(insurance_type="").values_list(
            "insurance_type", flat=True
        ).distinct(),
        "view_mode": view_mode,
        "per_page": per_page,
        "search": search,
        "querystring": request.GET.urlencode(),
    }

    context["provinces"] = (AddressModel.objects.filter(address_type="home")
    .exclude(province="").values_list("province", flat=True).distinct().order_by("province")
    )
    context["districts"] = (AddressModel.objects.filter(address_type="home").exclude(district="").values_list("district", flat=True).distinct().order_by("district")
    )
    context["sub_districts"] = (AddressModel.objects.filter(address_type="home")
    .exclude(sub_district="").values_list("sub_district", flat=True).distinct().order_by("sub_district")
    )

    return render(request, "dashboard/employee_list.html", context)

# ========================
# Employee Create
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("add_employeemodel")
def employee_create(request):
    if request.method == "POST":
        employer_id = request.POST.get("employer")
        if not employer_id:
            messages.error(request, "Please choose an employer.")
            return redirect("employee_create")

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
            passport_issue_place=request.POST.get("passport_issue_place"),
            passport_issue_date=request.POST.get("passport_issue_date") or None,
            passport_expiry_date=request.POST.get("passport_expiry_date") or None,
            pink_card_number=request.POST.get("pink_card_number"),
            visa_type=request.POST.get("visa_type"),
            visa_issue_place=request.POST.get("visa_issue_place"),
            visa_expiry_date=request.POST.get("visa_expiry_date") or None,
            visa_stamp_date=request.POST.get("visa_stamp_date") or None,
            visa_number=request.POST.get("visa_number"),
            job_position=request.POST.get("job_position"),
            job_description=request.POST.get("job_description"),
            start_date=request.POST.get("start_date") or None,
            work_permit_number=request.POST.get("work_permit_number"),
            work_permit_issue_date=request.POST.get("work_permit_issue_date") or None,
            work_permit_expiry_date=request.POST.get("work_permit_expiry_date") or None,
            report_90day_date=request.POST.get("report_90day_date") or None,
            work_permit_type=request.POST.get("work_permit_type"),
            ra_number=request.POST.get("ra_number"),
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
            login_email=request.POST.get("login_email"),
            created_by=request.user,
        )

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
def employee_update(request, pk):
    employee = get_object_or_404(EmployeeModel, id=pk)

    if request.method == "POST":
        employee.employer_id = request.POST.get("employer") or employee.employer_id
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
        employee.passport_issue_place = request.POST.get("passport_issue_place")
        employee.passport_issue_date = request.POST.get("passport_issue_date") or None
        employee.passport_expiry_date = request.POST.get("passport_expiry_date") or None
        employee.pink_card_number = request.POST.get("pink_card_number")
        employee.visa_type = request.POST.get("visa_type")
        employee.visa_issue_place = request.POST.get("visa_issue_place")
        employee.visa_expiry_date = request.POST.get("visa_expiry_date") or None
        employee.visa_stamp_date = request.POST.get("visa_stamp_date") or None
        employee.visa_number = request.POST.get("visa_number")
        employee.job_position = request.POST.get("job_position")
        employee.job_description = request.POST.get("job_description")
        employee.start_date = request.POST.get("start_date") or None
        employee.work_permit_number = request.POST.get("work_permit_number")
        employee.work_permit_issue_date = request.POST.get("work_permit_issue_date") or None
        employee.work_permit_expiry_date = request.POST.get("work_permit_expiry_date") or None
        employee.report_90day_date = request.POST.get("report_90day_date") or None
        employee.work_permit_type = request.POST.get("work_permit_type")
        employee.ra_number = request.POST.get("ra_number")
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
        employee.login_email = request.POST.get("login_email")
        employee.status = request.POST.get("status", employee.status)

        if request.FILES.get("photo"):
            if employee.photo:
                employee.photo.delete(save=False)
            employee.photo = request.FILES.get("photo")

        employee.updated_by = request.user
        employee.save()
        messages.success(request, UPDATE)
        return redirect("employee_list")

    context = {
        "employee": employee,
        "employers": EmployerModel.objects.filter(is_deleted=False).order_by("name_en"),
        "nationalities": NationalityModel.objects.all().order_by("name"),
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

    filename = f"employee_{datetime.now().strftime('%b-%d-%Y')}.xlsx"
    return export_to_excel(
        filename,
        ["No", "Name", "Employer", "Passport No.", "Work Permit No.", "Status"],
        rows,
    )