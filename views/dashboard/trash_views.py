from urllib.parse import urlencode

from django.apps import apps
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.utils import timezone

from constants.message import DELETE
from decorators.role_decorator import role_permission_required
from models.base_models import BaseModel
from utils.decorators import custom_login_required


def get_soft_delete_models():
    """BaseModel (soft-delete ရှိတဲ့) model အားလုံးကို ပြန်ပေးတယ်။"""
    soft_models = []
    for model in apps.get_app_config("core").get_models():
        if model._meta.abstract or not issubclass(model, BaseModel):
            continue
        try:
            model._meta.get_field("is_deleted")
        except Exception:
            continue
        soft_models.append(model)
    return soft_models


def _object_label(obj):
    label = str(obj)
    if "object (" in label:
        return f"{obj._meta.verbose_name.title()} — {obj.pk}"
    return label


def _page_range(page_obj, paginator):
    total = paginator.num_pages
    current = page_obj.number
    if total <= 5:
        return range(1, total + 1)
    if current <= 3:
        return [1, 2, 3, 4, "...", total]
    if current >= total - 2:
        return [1, "...", total - 3, total - 2, total - 1, total]
    return [1, "...", current - 1, current, current + 1, "...", total]


def _resolve_trashed_object(content_type_id, object_id):
    try:
        model = ContentType.objects.get_for_id(content_type_id).model_class()
    except ContentType.DoesNotExist:
        return None
    if model is None or model not in get_soft_delete_models():
        return None
    return model.objects.filter(pk=object_id, is_deleted=True).first()


# ========================
# Trash List
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("view_trashmodel")
def trash_list(request):
    search = request.GET.get("search", "").strip()
    model_filter = request.GET.get("model", "").strip()
    entries_raw = request.GET.get("entries", "10")
    try:
        entries = int(entries_raw)
    except (TypeError, ValueError):
        entries = 10

    items = []
    model_options = []
    for model in get_soft_delete_models():
        model_name = model._meta.model_name
        model_options.append(
            {"value": model_name, "label": model._meta.verbose_name.title()}
        )
        if model_filter and model_name != model_filter:
            continue

        content_type = ContentType.objects.get_for_model(model)
        for obj in model.objects.filter(is_deleted=True):
            label = _object_label(obj)
            if search and search.lower() not in label.lower():
                continue
            items.append(
                {
                    "content_type_id": content_type.id,
                    "model_name": model_name,
                    "model_label": model._meta.verbose_name.title(),
                    "object_id": str(obj.pk),
                    "label": label,
                    "deleted_at": obj.deleted_at,
                    "deleted_by": obj.deleted_by,
                }
            )

    items.sort(
        key=lambda item: (
            item["deleted_at"] is not None,
            item["deleted_at"] or timezone.now(),
        ),
        reverse=True,
    )

    paginator = Paginator(items, entries)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    query = {
        key: value
        for key, value in {
            "search": search,
            "model": model_filter,
            "entries": entries_raw if entries_raw else "",
        }.items()
        if value
    }

    context = {
        "items": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "page_range": _page_range(page_obj, paginator),
        "search": search,
        "model_filter": model_filter,
        "model_options": model_options,
        "entries": entries,
        "entries_options": [10, 20, 30, 50, 100],
        "date": "",
        "date_range": "",
        "page_query": urlencode(query),
        "total_count": len(items),
    }
    return render(request, "dashboard/trash_list.html", context)


# ========================
# Trash Restore
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("restore_trashmodel")
def trash_restore(request, content_type_id, object_id):
    if request.method == "POST":
        obj = _resolve_trashed_object(content_type_id, object_id)
        if obj is None:
            messages.error(request, "Item not found in trash.")
        else:
            obj.restore()
            messages.success(request, "Record restored successfully!")
    return redirect("trash_list")


# ========================
# Trash Permanent Delete
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("delete_trashmodel")
def trash_delete(request, content_type_id, object_id):
    if request.method == "POST":
        obj = _resolve_trashed_object(content_type_id, object_id)
        if obj is None:
            messages.error(request, "Item not found in trash.")
        else:
            obj.delete()
            messages.success(request, DELETE)
    return redirect("trash_list")
