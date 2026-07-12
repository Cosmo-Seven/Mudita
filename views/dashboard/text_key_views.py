from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from core.models import LanguageModel, TextKeyModel, TranslationModel
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from utils.decorators import custom_login_required
from decorators.role_decorator import role_permission_required
from constants.message import CREATE, UPDATE, DELETE
from django.core.paginator import Paginator


@custom_login_required("dashboard_login")
@role_permission_required("view_textkeymodel")
def text_key_list(request):
    languages = LanguageModel.objects.all()
    text_keys = TextKeyModel.objects.all().order_by("key")

    missing_lang = request.GET.get("missing_lang")

    if missing_lang:
        # language object
        language = LanguageModel.objects.get(code=missing_lang)

        # translated keys (non-empty)
        translated_key_ids = (
            TranslationModel.objects.filter(language=language)
            .exclude(translated_text__isnull=True)
            .exclude(translated_text="")
            .values_list("text_key_id", flat=True)
        )

        # show only missing ones
        text_keys = text_keys.exclude(id__in=translated_key_ids)

    translations = {
        f"{t.text_key_id}|{t.language.code}": t.translated_text
        for t in TranslationModel.objects.all()
    }

    search = request.GET.get("search", "")
    if search:
        text_keys = text_keys.filter(key__icontains=search)

    page_number = request.GET.get("page", 1)
    paginator = Paginator(text_keys, 10)
    page_obj = paginator.get_page(page_number)

    current = page_obj.number
    total = paginator.num_pages

    if total <= 5:
        page_range = range(1, total + 1)

    else:
        if current <= 3:
            # 1 2 3 4 ... last
            page_range = [1, 2, 3, 4, "...", total]

        elif current >= total - 2:
            # 1 ... last-3 last-2 last-1 last
            page_range = [1, "...", total - 3, total - 2, total - 1, total]

        else:
            # 1 ... current-1 current current+1 ... last
            page_range = [1, "...", current - 1, current, current + 1, "...", total]

    context = {
        "languages": languages,
        "text_keys": page_obj,
        "page_obj": page_obj,
        "translations": translations,
        "paginator": paginator,
        "page_range": page_range,
    }
    return render(request, "dashboard/text_key_list.html", context)


@csrf_exempt
@custom_login_required("dashboard_login")
def save_translation(request):
    if request.method != "POST":
        return JsonResponse({"saved": False}, status=400)

    data = json.loads(request.body)
    text_key_id = data["key"]
    lang_code = data["lang"]
    value = data["value"]

    language = LanguageModel.objects.get(code=lang_code)

    translation, _ = TranslationModel.objects.get_or_create(
        text_key_id=text_key_id,
        language=language,
    )
    translation.translated_text = value
    translation.save()

    return JsonResponse({"saved": True})


# ========================
# Text_key Create
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("add_textkeymodel")
def text_key_create(request):
    if request.method == "POST":
        key = request.POST.get("key")

        if TextKeyModel.objects.filter(key=key).exists():
            messages.warning(request, "Text key already exists!")
            return redirect("text_key_list")
        default_text = request.POST.get("default_text")

        text_key = TextKeyModel.objects.create(
            key=key,
            default_text=default_text,
        )
        text_key.save()

        messages.success(request, CREATE)
        return redirect("text_key_list")


# ========================
# Text_key Update
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("change_textkeymodel")
def text_key_update(request, pk):
    text_key = get_object_or_404(TextKeyModel, id=pk)

    if request.method == "POST":
        key = request.POST.get("key")
        default_text = request.POST.get("default_text")

        text_key.key = key
        text_key.default_text = default_text
        text_key.save()
        messages.success(request, UPDATE)
        return redirect("text_key_list")


# ========================
# Text_key Delete
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("delete_textkeymodel")
def text_key_delete(request, pk):
    text_key = get_object_or_404(TextKeyModel, id=pk)
    text_key.delete()
    messages.success(request, DELETE)
    return redirect("text_key_list")
