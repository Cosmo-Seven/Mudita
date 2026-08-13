from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from datetime import datetime

from utils.decorators import custom_login_required
from decorators.role_decorator import role_permission_required
from helpers.filters import filter_querysets
from helpers.exports import export_to_pdf, export_to_excel, filter_queryset_for_export
from helpers.phone import format_mm_phone
from constants.message import CREATE, UPDATE, DELETE
from core.models import EmployerModel, BusinessTypeModel, UserModel
from core.models import DocumentTypeModel, DocumentModel
from django.contrib.contenttypes.models import ContentType


ATTACHMENT_FIELDS = [
    "company_registration_certificate",
    "house_rental_agreement",
    "construction_contract_map",
    "employer_other_document_1",
    "employer_other_document_2",
    "employer_other_document_3",
]

def _save_employer_attachments(request, employer):
    for code in ATTACHMENT_FIELDS:
        file = request.FILES.get(f"{code}_file") or request.FILES.get(f"{code}_camera")
        if not file:
            continue

        doc_type = DocumentTypeModel.objects.filter(code=code).first()
        if not doc_type:
            continue  # seed migration မလုပ်ရသေးရင် skip (error မတက်စေရန်)

        DocumentModel.objects.create(
            content_type=ContentType.objects.get_for_model(EmployerModel),
            object_id=employer.id,
            doc_type=doc_type,
            file=file,
            description=request.POST.get(f"{code}_description", ""),
            expiry_date=request.POST.get(f"{code}_expiry_date") or None,
            created_by=request.user,
        )

# ========================
# Employer List
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("view_employermodel")
def employer_list(request):
    employers = EmployerModel.objects.select_related(
        "business_type", "responsible_person", "parent_employer"
    ).order_by("-created_at")

    filters = filter_querysets(
        request,
        employers,
        search_fields=["name_th", "name_en", "employer_code", "employer_id_number"],
        date_field="created_at",
        order="-created_at",
    )

    context = {
        "employers": filters["page_obj"],
        "business_types": BusinessTypeModel.objects.all().order_by("name_en"),
        "responsible_persons": UserModel.objects.filter(is_active=True).order_by(
            "username"
        ),
        **filters,
    }

    if request.headers.get("HX-Request"):
        return render(request, "dashboard/employer_list.html", context)

    return render(request, "dashboard/employer_list.html", context)


# ========================
# Employer Create
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("add_employermodel")
def employer_create(request):
    if request.method == "POST":
        name_en = request.POST.get("name_en")
        name_th = request.POST.get("name_th")

        if EmployerModel.objects.filter(name_en=name_en).exists():
            messages.error(request, "Employer name has already been used!")
            return redirect("employer_list")

        employer = EmployerModel.objects.create(
            name_th=name_th,
            name_en=name_en,
            name_suffix_en=request.POST.get("name_suffix_en") or None,
            parent_employer_id=request.POST.get("parent_employer") or None,
            responsible_person_id=request.POST.get("responsible_person") or None,
            employer_id_number=request.POST.get("employer_id_number"),
            business_type_id=request.POST.get("business_type") or None,
            business_type_th=request.POST.get("business_type_th"),
            business_type_en=request.POST.get("business_type_en"),
            phone=format_mm_phone(request.POST.get("phone")),
            social_security_hospital=request.POST.get("social_security_hospital"),
            portal_email=request.POST.get("portal_email"),
            re_code=request.POST.get("re_code"),
            authorized_signatory_1_th=request.POST.get("authorized_signatory_1_th"),
            authorized_signatory_1_en=request.POST.get("authorized_signatory_1_en"),
            authorized_signatory_2_th=request.POST.get("authorized_signatory_2_th"),
            authorized_signatory_2_en=request.POST.get("authorized_signatory_2_en"),
            registered_capital=request.POST.get("registered_capital") or None,
            registration_date=request.POST.get("registration_date") or None,
            minimum_wage=request.POST.get("minimum_wage") or None,
            created_by=request.user,
        )

        if request.FILES.get("stamp"):
            employer.stamp = request.FILES.get("stamp")
            employer.save()

        _save_employer_attachments(request, employer)

        messages.success(request, CREATE)
        return redirect("employer_list")

    context = {
        "business_types": BusinessTypeModel.objects.all().order_by("name_en"),
        "responsible_persons": UserModel.objects.filter(is_active=True).order_by(
            "username"
        ),
        "employers": EmployerModel.objects.all().order_by("name_en"),
    }
    return render(request, "dashboard/employer_create.html", context)


# ========================
# Employer Update
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("change_employermodel")
def employer_update(request, pk):
    employer = get_object_or_404(EmployerModel, id=pk)

    if request.method == "POST":
        name_en = request.POST.get("name_en")

        if (
            EmployerModel.objects.filter(name_en=name_en)
            .exclude(id=employer.id)
            .exists()
        ):
            messages.error(request, "Employer name has already been used!")
            return redirect("employer_list")

        employer.name_th = request.POST.get("name_th")
        employer.name_en = name_en
        employer.name_suffix_en = request.POST.get("name_suffix_en") or None
        employer.parent_employer_id = request.POST.get("parent_employer") or None
        employer.responsible_person_id = request.POST.get("responsible_person") or None
        employer.employer_id_number = request.POST.get("employer_id_number")
        employer.business_type_id = request.POST.get("business_type") or None
        employer.business_type_th = request.POST.get("business_type_th")
        employer.business_type_en = request.POST.get("business_type_en")
        employer.phone = format_mm_phone(request.POST.get("phone"))
        employer.social_security_hospital = request.POST.get("social_security_hospital")
        employer.portal_email = request.POST.get("portal_email")
        employer.re_code = request.POST.get("re_code")
        employer.authorized_signatory_1_th = request.POST.get(
            "authorized_signatory_1_th"
        )
        employer.authorized_signatory_1_en = request.POST.get(
            "authorized_signatory_1_en"
        )
        employer.authorized_signatory_2_th = request.POST.get(
            "authorized_signatory_2_th"
        )
        employer.authorized_signatory_2_en = request.POST.get(
            "authorized_signatory_2_en"
        )
        employer.registered_capital = request.POST.get("registered_capital") or None
        employer.registration_date = request.POST.get("registration_date") or None
        employer.minimum_wage = request.POST.get("minimum_wage") or None
        employer.status = request.POST.get("status", employer.status)

        if request.FILES.get("stamp"):
            if employer.stamp:
                employer.stamp.delete(save=False)
            employer.stamp = request.FILES.get("stamp")

        employer.updated_by = request.user
        employer.save()
        messages.success(request, UPDATE)
        return redirect("employer_list")

    context = {
        "employer": employer,
        "business_types": BusinessTypeModel.objects.all().order_by("name_en"),
        "responsible_persons": UserModel.objects.filter(is_active=True).order_by(
            "username"
        ),
        "employers": EmployerModel.objects.exclude(id=employer.id).order_by("name_en"),
    }
    return render(request, "dashboard/employer_update.html", context)


# ========================
# Employer Detail (addresses + documents + employees list)
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("view_employermodel")
def employer_detail(request, pk):
    employer = get_object_or_404(EmployerModel, id=pk)
    context = {
        "employer": employer,
        "addresses": employer.addresses.all(),
        "documents": employer.documents.all(),
        "employees": employer.employees.order_by("-created_at")[:20],
    }
    return render(request, "dashboard/employer_detail.html", context)


# ========================
# Employer Delete
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("delete_employermodel")
def employer_delete(request, pk):
    employer = get_object_or_404(EmployerModel, id=pk)
    if request.method == "POST":
        if employer.employees.exists():
            messages.error(
                request, "Cannot delete an employer that still has employees attached."
            )
            return redirect("employer_list")

        if employer.stamp:
            employer.stamp.delete(save=False)

        employer.soft_delete(user=request.user)  # BaseModel ရဲ့ soft delete သုံးထားတယ်
        messages.success(request, DELETE)
        return redirect("employer_list")


# ========================
# Employer Search (Employee create form ရဲ့ "Choose an employer" autocomplete)
# ========================
@custom_login_required("dashboard_login")
def employer_search(request):
    q = request.GET.get("q", "")
    employers = EmployerModel.objects.filter(is_deleted=False)
    if q:
        employers = employers.filter(name_en__icontains=q) | employers.filter(
            name_th__icontains=q
        )

    data = [
        {"id": str(e.id), "text": f"{e.name_en} ({e.employer_code or '-'})"}
        for e in employers.order_by("name_en")[:20]
    ]
    return JsonResponse({"results": data})


# ========================
# Employer Export PDF / Excel
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("view_employermodel")
def employer_export_pdf(request):
    search = request.GET.get("search", "")
    date = request.GET.get("date", "")
    date_range = request.GET.get("date_range", "")

    employers = filter_queryset_for_export(
        EmployerModel.objects.all(),
        search=search,
        date=date,
        date_range=date_range,
        search_fields=["name_en", "employer_code"],
        date_field="created_at",
    )

    rows = [
        [idx, e.employer_code or "", e.name_en, e.phone or "", e.status.title()]
        for idx, e in enumerate(employers, start=1)
    ]

    filename = f"employer_{datetime.now().strftime('%b-%d-%Y')}.pdf"
    return export_to_pdf(
        filename, ["No", "Employer Code", "Name", "Phone", "Status"], rows
    )


@custom_login_required("dashboard_login")
@role_permission_required("view_employermodel")
def employer_export_excel(request):
    search = request.GET.get("search", "")
    date = request.GET.get("date", "")
    date_range = request.GET.get("date_range", "")

    employers = filter_queryset_for_export(
        EmployerModel.objects.all(),
        search=search,
        date=date,
        date_range=date_range,
        search_fields=["name_en", "employer_code"],
        date_field="created_at",
    )

    rows = [
        [idx, e.employer_code or "", e.name_en, e.phone or "", e.status.title()]
        for idx, e in enumerate(employers, start=1)
    ]

    filename = f"employer_{datetime.now().strftime('%b-%d-%Y')}.xlsx"
    return export_to_excel(
        filename, ["No", "Employer Code", "Name", "Phone", "Status"], rows
    )


@custom_login_required("dashboard_login")
def business_type_quick_add(request):
    if request.method == "POST":
        name_en = request.POST.get("name_en", "").strip()
        name_th = request.POST.get("name_th", "").strip()

        if not name_en:
            return JsonResponse({"success": False, "error": "Name (EN) is required."})

        if BusinessTypeModel.objects.filter(name_en__iexact=name_en).exists():
            return JsonResponse(
                {"success": False, "error": "Business type already exists."}
            )

        bt = BusinessTypeModel.objects.create(
            name_en=name_en, name_th=name_th, created_by=request.user
        )
        return JsonResponse({"success": True, "id": str(bt.id), "text": bt.name_en})

    return JsonResponse({"success": False, "error": "Invalid request."})


@custom_login_required("dashboard_login")
def employer_quick_add(request):
    if request.method == "POST":
        name_en = request.POST.get("name_en", "").strip()
        name_th = request.POST.get("name_th", "").strip()

        if not name_en:
            return JsonResponse({"success": False, "error": "Name (EN) is required."})

        if EmployerModel.objects.filter(name_en__iexact=name_en).exists():
            return JsonResponse({"success": False, "error": "Employer already exists."})

        employer = EmployerModel.objects.create(
            name_en=name_en, name_th=name_th, created_by=request.user
        )
        return JsonResponse(
            {
                "success": True,
                "id": str(employer.id),
                "text": f"{employer.name_en} ({employer.employer_code or '-'})",
            }
        )

    return JsonResponse({"success": False, "error": "Invalid request."})
