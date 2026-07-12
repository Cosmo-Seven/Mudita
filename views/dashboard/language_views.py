from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from utils.decorators import custom_login_required
from helpers.filters import filter_querysets
from decorators.role_decorator import role_permission_required
from core.models import LanguageModel
from constants.message import CREATE, UPDATE, DELETE


def set_language(request):
    language = request.GET.get("language")
    request.session["language"] = language
    return redirect(request.META.get("HTTP_REFERER", "/"))


# ========================
# Language List
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("view_languagemodel")
def language_list(request):
    languages = LanguageModel.objects.all().order_by("created_at")

    filters = filter_querysets(
        request,
        languages,
        date_field="created_at",
        order="created_at",
    )

    context = {
        "languages": filters["page_obj"],
        **filters,
    }
    return render(request, "dashboard/language_list.html", context)


# ========================
# Language Create
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("add_languagemodel")
def language_create(request):
    if request.method == "POST":
        name = request.POST.get("name")
        code = request.POST.get("code")
        flag = request.FILES.get("flag")

        language = LanguageModel.objects.create(
            name=name,
            code=code,
            flag=flag,
        )
        language.save()
        messages.success(request, CREATE)
        return redirect("language_list")


# ========================
# Language Update
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("change_languagemodel")
def language_update(request, pk):
    language = get_object_or_404(LanguageModel, id=pk)

    if request.method == "POST":
        name = request.POST.get("name")
        code = request.POST.get("code")
        flag = request.FILES.get("flag")

        language.name = name
        language.code = code
        if flag:
            if language.flag:
                language.flag.delete()
            language.flag = flag
        language.save()
        messages.success(request, UPDATE)
        return redirect("language_list")


# ========================
# Language Delete
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("delete_languagemodel")
def language_delete(request, pk):
    language = get_object_or_404(LanguageModel, id=pk)
    if language.flag:
        language.flag.delete()
    language.delete()
    messages.success(request, DELETE)
    return redirect("language_list")
