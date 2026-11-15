from uuid import UUID

from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.models import EmployeeModel, EmployeeRequestModel
from decorators.role_decorator import role_permission_required
from utils.decorators import custom_login_required


def _employee_for_user(user):
    return EmployeeModel.objects.filter(
        user=user, is_deleted=False
    ).select_related("employer").first()


@custom_login_required("dashboard_login")
def worker_portal(request):
    employee = _employee_for_user(request.user)
    if employee is None or request.user.is_staff:
        return redirect("dashboard")

    requests = employee.requests.filter(is_deleted=False)
    days_until_report = employee.days_until_90day_report
    return render(
        request,
        "worker/portal.html",
        {
            "employee": employee,
            "requests": requests,
            "days_until_report": days_until_report,
            "report_reminder": (
                employee.report_90day_date is not None
                and days_until_report is not None
                and days_until_report <= 14
            ),
        },
    )


@custom_login_required("dashboard_login")
def worker_profile(request):
    employee = _employee_for_user(request.user)
    if employee is None or request.user.is_staff:
        return redirect("dashboard")
    return render(request, "worker/profile.html", {"employee": employee})


@custom_login_required("dashboard_login")
def submit_employee_request(request):
    employee = _employee_for_user(request.user)
    if employee is None or request.user.is_staff:
        return redirect("dashboard")
    if request.method != "POST":
        return redirect("worker_portal")

    request_type = request.POST.get("request_type", "")
    reason = request.POST.get("reason", "").strip()
    desired_job = request.POST.get("desired_job", "").strip()
    valid_types = dict(EmployeeRequestModel.TYPE_CHOICES)
    if request_type not in valid_types or not reason:
        messages.error(request, "Please choose a request type and enter a reason.")
        return redirect("worker_portal")
    if request_type == "job_change" and not desired_job:
        messages.error(request, "Please enter your preferred job or employer.")
        return redirect("worker_portal")

    EmployeeRequestModel.objects.create(
        employee=employee,
        request_type=request_type,
        reason=reason,
        desired_job=desired_job if request_type == "job_change" else "",
        created_by=request.user,
    )
    messages.success(request, "Your request has been submitted.")
    return redirect("worker_portal")


@custom_login_required("dashboard_login")
@role_permission_required("view_employeemodel")
def employee_request_list(request):
    requests = EmployeeRequestModel.objects.filter(
        is_deleted=False, employee__is_deleted=False
    ).select_related("employee", "employee__employer")

    if request.method == "POST":
        try:
            request_id = UUID(request.POST.get("request_id", ""))
        except (TypeError, ValueError):
            raise Http404("Employee request not found.")
        employee_request = get_object_or_404(requests, id=request_id)
        status = request.POST.get("status", "")
        if status not in dict(EmployeeRequestModel.STATUS_CHOICES):
            messages.error(request, "Please choose a valid request status.")
            return redirect("employee_request_list")
        employee_request.status = status
        employee_request.staff_note = request.POST.get("staff_note", "").strip()
        employee_request.reviewed_at = timezone.now()
        employee_request.updated_by = request.user
        employee_request.save(
            update_fields=[
                "status", "staff_note", "reviewed_at", "updated_by", "updated_at"
            ]
        )
        messages.success(request, "The request status has been updated.")
        return redirect("employee_request_list")

    return render(
        request,
        "dashboard/employee_request_list.html",
        {"employee_requests": requests.order_by("-created_at")},
    )
