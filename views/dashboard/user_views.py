from django.conf import settings
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from utils.decorators import custom_login_required
from helpers.filters import filter_querysets
from helpers.exports import export_to_pdf, export_to_excel, filter_queryset_for_export
from decorators.role_decorator import role_permission_required
from core.models import UserModel, RoleModel
from datetime import datetime
from helpers.phone import format_mm_phone
from constants.message import CREATE, UPDATE, DELETE


# ========================
# User List
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("view_usermodel")
def user_list(request):
    if request.user.role.name == settings.HYPER:
        users = UserModel.objects.all().order_by("-created_at")
        roles = RoleModel.objects.all().order_by("-created_at")
    else:
        roles = RoleModel.objects.exclude(name=settings.HYPER).order_by("-created_at")
        role = RoleModel.objects.get(name=settings.HYPER)
        users = UserModel.objects.exclude(role=role).order_by("-created_at")

    filters = filter_querysets(
        request,
        users,
        search_fields=["username", "email", "role__name", "phone"],
        date_field="created_at",
        order="-created_at",
    )

    context = {
        "users": filters["page_obj"],
        "roles": roles,
        **filters,
    }
    if request.headers.get('HX-Request'):
        return render(request, 'dashboard/user_list.html', context)

    return render(request, "dashboard/user_list.html", context)


# ========================
# User Create
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("add_usermodel")
def user_create(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        profile = request.FILES.get("profile")
        phone = format_mm_phone(request.POST.get("phone"))
        is_active = "is_active" in request.POST
        is_staff = "is_staff" in request.POST
        is_superuser = "is_superuser" in request.POST
        role_id = request.POST.get("role")

        if UserModel.objects.filter(email=email).exists():
            messages.error(request, "Email has already been used!")
            return redirect("user_list")

        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")
        if password != confirm_password:
            messages.error(request, "Password does not match! Please check again!")
            return redirect("user_list")

        user = UserModel.objects.create_user(
            username=username,
            email=email,
            profile=profile,
            password=password,
            phone=phone,
            role_id=role_id,
            is_active=is_active,
            is_staff=is_staff,
            is_superuser=is_superuser,
        )
        user.save()
        messages.success(request, CREATE)
        return redirect("user_list")


# ========================
# User Update
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("change_usermodel")
def user_update(request, pk):
    user = get_object_or_404(UserModel, id=pk)

    if request.method == "POST":
        confirm_password = request.POST.get("confirm_password")
        password = request.POST.get("password")
        user.username = request.POST.get("username")
        user.email = request.POST.get("email")
        user.phone = format_mm_phone(request.POST.get("phone"))

        if request.FILES.get("profile"):
            if user.profile:
                user.profile.delete(save=False)
            user.profile = request.FILES.get("profile")

        if UserModel.objects.filter(email=user.email).exclude(id=user.id).exists():
            messages.error(request, "Email has already been used!")
            return redirect("user_list")

        user.is_active = "is_active" in request.POST
        user.is_staff = "is_staff" in request.POST
        user.is_superuser = "is_superuser" in request.POST
        user.role_id = request.POST.get("role")

        if password != confirm_password:
            messages.error(request, "Password does not match! Please check again!")
            return redirect("user_list")

        if password:
            user.set_password(password)

        user.save()
        messages.success(request, UPDATE)
        return redirect("user_list")


# ========================
# User Delete
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("delete_usermodel")
def user_delete(request, pk):
    user = get_object_or_404(UserModel, id=pk)
    if request.method == "POST":
        if user.profile:
            user.profile.delete(save=False)

        user.delete()
        messages.success(request, DELETE)
        return redirect("user_list")


# ========================
# User Export PDF
# ========================
@custom_login_required("dashboard_login")
def user_export_pdf(request):
    search = request.GET.get("search", "")
    date = request.GET.get("date", "")
    date_range = request.GET.get("date_range", "")
    role = RoleModel.objects.get(name=settings.HYPER)

    users = filter_queryset_for_export(
        UserModel.objects.exclude(role=role),
        search=search,
        date=date,
        date_range=date_range,
        search_fields=["username", "email", "role__name"],
        date_field="created_at",
    )

    rows = [
        [
            idx,
            user.username,
            user.email,
            user.phone or "",
            user.role.name if user.role else "",
            "Active" if user.is_active else "Inactive",
        ]
        for idx, user in enumerate(users, start=1)
    ]

    filename = f"user_{datetime.now().strftime('%b-%d-%Y')}.pdf"
    return export_to_pdf(
        filename, ["No", "Username", "Email", "Phone", "Role", "Status"], rows
    )


# ========================
# User Export Excel
# ========================
@custom_login_required("dashboard_login")
def user_export_excel(request):
    search = request.GET.get("search", "")
    date = request.GET.get("date", "")
    date_range = request.GET.get("date_range", "")
    role = RoleModel.objects.get(name=settings.HYPER)

    users = filter_queryset_for_export(
        UserModel.objects.exclude(role=role),
        search=search,
        date=date,
        date_range=date_range,
        search_fields=["username", "email", "role__name"],
        date_field="created_at",
    )

    rows = [
        [
            idx,
            user.username,
            user.email,
            user.phone or "",
            user.role.name if user.role else "",
            "Active" if user.is_active else "Inactive",
        ]
        for idx, user in enumerate(users, start=1)
    ]

    filename = f"user_{datetime.now().strftime('%b-%d-%Y')}.xlsx"
    return export_to_excel(
        filename, ["No", "Username", "Email", "Phone", "Role", "Status"], rows
    )
