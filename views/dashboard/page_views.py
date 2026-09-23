from datetime import date, timedelta
import json

from django.contrib import messages
from django.shortcuts import render, redirect
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.contrib.auth.hashers import check_password

from models.user_models import UserModel
from utils.decorators import custom_login_required
from core.models import (
    SiteModel,
    EmployeeModel,
    EmployerModel,
    EmployeeWorkflowModel,
    WorkflowTypeModel,
)
from constants.message import UPDATE


# ========================
# Dashboard
# ========================
@custom_login_required("dashboard_login")
def dashboard(request):
    today = date.today()
    soon = today + timedelta(days=90)
    report_window = today + timedelta(days=14)

    employees = EmployeeModel.objects.filter(is_deleted=False)
    employers = EmployerModel.objects.filter(is_deleted=False)
    workflows = EmployeeWorkflowModel.objects.filter(is_deleted=False)
    users = UserModel.objects.filter(is_deleted=False)

    stats = {
        "employer_count": employers.count(),
        "employer_active": employers.filter(status="active").count(),
        "employee_count": employees.count(),
        "employee_active": employees.filter(status="active").count(),
        "employee_pending": employees.filter(status="registration_pending").count(),
        "employee_renewal": employees.filter(status="renewal_pending").count(),
        "employee_terminated": employees.filter(status="terminated").count(),
        "workflow_in_progress": workflows.filter(status="in_progress").count(),
        "workflow_finished": workflows.filter(status="finished").count(),
        "workflow_cancelled": workflows.filter(status="cancelled").count(),
        "user_count": users.filter(is_active=True).count(),
    }

    alerts = {
        "passport_expired": employees.filter(passport_expiry_date__lt=today).count(),
        "passport_expiring": employees.filter(
            passport_expiry_date__gte=today, passport_expiry_date__lte=soon
        ).count(),
        "visa_expired": employees.filter(visa_expiry_date__lt=today).count(),
        "visa_expiring": employees.filter(
            visa_expiry_date__gte=today, visa_expiry_date__lte=soon
        ).count(),
        "work_permit_expired": employees.filter(work_permit_expiry_date__lt=today).count(),
        "work_permit_expiring": employees.filter(
            work_permit_expiry_date__gte=today, work_permit_expiry_date__lte=soon
        ).count(),
        "report_90day_due": employees.filter(
            report_90day_date__gte=today, report_90day_date__lte=report_window
        ).count(),
        "report_90day_overdue": employees.filter(report_90day_date__lt=today).count(),
    }

    workflow_types = (
        WorkflowTypeModel.objects.filter(is_deleted=False)
        .annotate(
            in_progress=Count(
                "workflows",
                filter=Q(workflows__status="in_progress", workflows__is_deleted=False),
            ),
            finished=Count(
                "workflows",
                filter=Q(workflows__status="finished", workflows__is_deleted=False),
            ),
            cancelled=Count(
                "workflows",
                filter=Q(workflows__status="cancelled", workflows__is_deleted=False),
            ),
            total=Count("workflows", filter=Q(workflows__is_deleted=False)),
        )
        .order_by("order")
    )

    recent_employees = employees.select_related("employer").order_by("-created_at")[:8]
    recent_employers = employers.annotate(
        employee_count=Count("employees", filter=Q(employees__is_deleted=False))
    ).order_by("-created_at")[:8]

    attention_qs = employees.filter(
        Q(passport_expiry_date__isnull=False, passport_expiry_date__lte=soon)
        | Q(visa_expiry_date__isnull=False, visa_expiry_date__lte=soon)
        | Q(work_permit_expiry_date__isnull=False, work_permit_expiry_date__lte=soon)
        | Q(report_90day_date__isnull=False, report_90day_date__lte=report_window)
    ).select_related("employer")[:80]

    attention_rows = []
    for employee in attention_qs:
        items = []
        for label, expiry, window in (
            ("passport", employee.passport_expiry_date, 90),
            ("visa", employee.visa_expiry_date, 90),
            ("work_permit", employee.work_permit_expiry_date, 90),
            ("90day_report", employee.report_90day_date, 14),
        ):
            if not expiry:
                continue
            days = (expiry - today).days
            if days <= window:
                items.append({"label": label, "date": expiry, "days": days})
        if not items:
            continue
        soonest = min(items, key=lambda item: item["days"])
        attention_rows.append({"employee": employee, **soonest})
    attention_rows.sort(key=lambda row: row["days"])
    attention_rows = attention_rows[:8]

    six_months_ago = today.replace(day=1) - timedelta(days=160)
    monthly_raw = {}
    for row in (
        employees.filter(created_at__date__gte=six_months_ago)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(c=Count("id"))
    ):
        month = row["month"]
        if month:
            monthly_raw[(month.year, month.month)] = row["c"]
    chart_labels = []
    chart_data = []
    month_cursor = date(today.year, today.month, 1)
    months = []
    for _ in range(6):
        months.append(month_cursor)
        year, month = (
            (month_cursor.year, month_cursor.month - 1)
            if month_cursor.month > 1
            else (month_cursor.year - 1, 12)
        )
        month_cursor = date(year, month, 1)
    for month_start in reversed(months):
        chart_labels.append(month_start.strftime("%b"))
        chart_data.append(monthly_raw.get((month_start.year, month_start.month), 0))

    context = {
        "stats": stats,
        "alerts": alerts,
        "workflow_types": workflow_types,
        "recent_employees": recent_employees,
        "recent_employers": recent_employers,
        "attention_rows": attention_rows,
        "chart_labels": json.dumps(chart_labels),
        "chart_data": json.dumps(chart_data),
    }
    return render(request, "dashboard/index.html", context)


# ========================
# Site Settings
# ========================
@custom_login_required("dashboard_login")
def site_settings(request):
    site = SiteModel.objects.first()
    if request.method == "GET":
        context = {"site": site}
        return render(request, "dashboard/site_settings.html", context)
    if request.method == "POST":
        name = request.POST.get("name")
        phone = request.POST.get("phone")
        address = request.POST.get("address")
        email = request.POST.get("email")
        favicon = request.FILES.get("favicon")
        logo = request.FILES.get("logo")
        if not site:
            site = SiteModel.objects.create(
                name=name,
                favicon=favicon,
                logo=logo,
                phone=phone,
                address=address,
                email=email,
            )
            site.save()
        else:
            site.name = name
            site.phone = phone
            site.address = address
            site.email = email
            if favicon:
                if site.favicon:
                    site.favicon.delete(save=False)
                site.favicon = favicon
            if logo:
                if site.logo:
                    site.logo.delete(save=False)
                site.logo = logo
            site.save()
            messages.success(request, UPDATE)
        return redirect("site_settings")


# ========================
# Page Not Found
# ========================
def page_not_found(request):
    return render(request, "dashboard/page_not_found.html", status=404)


# ========================
# Internal Server Error
# ========================
def internal_server_error(request):
    return render(request, "dashboard/internal_server_error.html", status=500)


# ========================
# Under Maintenance
# ========================
def under_maintenance(request):
    return render(request, "dashboard/under_maintenance.html", status=503)


# ========================
# Lock Screen
# ========================
def locked(request):
    request.session["is_locked"] = True
    return redirect("lock_screen")


def lock_screen(request):
    return render(request, "dashboard/lock_screen.html")


def unlock(request):
    if request.method == "POST":
        password = request.POST.get("password")

        user = UserModel.objects.get(email=request.user.email)
        if check_password(password, user.password):
            request.session["is_locked"] = False
            return redirect("dashboard")
        else:
            messages.error(request, "Incorrect password. Please try again.")
            return redirect("lock_screen")
    return redirect("lock_screen")
