from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.hashers import check_password
from core.models import UserModel
from utils.decorators import custom_login_required


# ========================
# Dashboard Login
# ========================
def dashboard_login(request):
    if request.user.is_authenticated:
        return redirect("dashboard_welcome")

    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        try:
            user = UserModel.objects.get(email=email)
            if check_password(password, user.password):
                login(request, user)
                messages.success(request, f"Welcome {user.username}")
                return redirect("dashboard_welcome")
            else:
                messages.error(request, "Email or Password is incorrect!")
                return redirect("dashboard_login")
        except UserModel.DoesNotExist:
            messages.error(request, "Email or Password is incorrect!")
            return redirect("dashboard_login")

    return render(request, "dashboard/login.html")


# ========================
# Dashboard Logout
# ========================
def dashboard_logout(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect("dashboard_login")


# ========================
# Dashboard Welcome
# ========================
@custom_login_required("dashboard_login")
def dashboard_welcome(request):
    return render(request, "dashboard/dashboard_welcome.html")


# ========================
# User Profile
# ========================
@custom_login_required("dashboard_login")
def profile(request):
    user = get_object_or_404(UserModel, id=request.user.id)

    if request.method == "POST":
        username = request.POST.get("username")
        phone = request.POST.get("phone")
        password = request.POST.get("password")
        profile = request.FILES.get("profile")

        user.username = username
        user.phone = phone

        if profile:
            if user.profile:
                user.profile.delete(save=False)
            user.profile = profile

        if password:
            user.set_password(password)
            update_session_auth_hash(request, user)
            messages.success(request, "Password updated successfully!")

        user.save()
        messages.success(request, "Profile updated successfully.")
        return redirect("dashboard_profile")

    context = {"user": user}
    return render(request, "dashboard/profile.html", context)
