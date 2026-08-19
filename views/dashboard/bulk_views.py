from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse
from django.shortcuts import redirect
from datetime import datetime

from utils.decorators import custom_login_required
from decorators.role_decorator import role_permission_required
from helpers.allowed_models import get_allowed_models
from helpers.exports import export_to_pdf, export_to_excel
from constants.message import DELETE


# model_name -> (list of [column_label], row -> [values])  ဆိုပြီး export column config
EXPORT_CONFIG = {
    "employermodel": {
        "headers": ["No", "Employer Code", "Name", "Phone", "Status"],
        "row": lambda idx, e: [idx, e.employer_code or "", e.name_en, e.phone or "", e.status.title()],
    },
    "employeemodel": {
        "headers": ["No", "Name", "Employer", "Passport No.", "Work Permit No.", "Status"],
        "row": lambda idx, e: [
            idx, e.full_name_en,
            e.employer.name_en if e.employer else "",
            e.passport_number or "", e.work_permit_number or "",
            e.get_status_display(),
        ],
    },
}


def _resolve_model(model_name):
    """model_name string ('employermodel'/'employeemodel') ကို allowed_models whitelist
    နဲ့ စစ်ပြီး Model class ကို ပြန်ပေး — arbitrary model access ကို ကာကွယ်ဖို့"""
    if model_name not in get_allowed_models():
        return None
    return ContentType.objects.get(app_label="core", model=model_name).model_class()


# ========================
# Bulk Delete (soft delete)
# ========================
@custom_login_required("dashboard_login")
def bulk_delete(request, model_name):
    model_class = _resolve_model(model_name)
    if model_class is None:
        messages.error(request, "Invalid module.")
        return redirect("dashboard")

    if not request.user.has_perm(f"core.delete_{model_name}"):
        messages.error(request, "You don't have permission to delete this module.")
        return redirect(f"{model_name.replace('model', '')}_list")

    if request.method == "POST":
        ids = request.POST.getlist("selected_ids")
        if not ids:
            messages.error(request, "No item selected.")
            return redirect(f"{model_name.replace('model', '')}_list")

        queryset = model_class.objects.filter(id__in=ids)
        count = queryset.count()

        for obj in queryset:
            if hasattr(obj, "soft_delete"):
                obj.soft_delete(user=request.user)
            else:
                obj.delete()

        messages.success(request, f"{count} record(s) — {DELETE}")

    return redirect(f"{model_name.replace('model', '')}_list")


# ========================
# Bulk Export (selected rows only)
# ========================
@custom_login_required("dashboard_login")
def bulk_export(request, model_name, file_format):
    model_class = _resolve_model(model_name)
    config = EXPORT_CONFIG.get(model_name)

    if model_class is None or config is None:
        messages.error(request, "Export not supported for this module.")
        return redirect("dashboard")

    ids = request.POST.getlist("selected_ids") or request.GET.getlist("selected_ids")
    queryset = model_class.objects.filter(id__in=ids) if ids else model_class.objects.all()

    rows = [config["row"](idx, obj) for idx, obj in enumerate(queryset, start=1)]
    filename = f"{model_name}_{datetime.now().strftime('%b-%d-%Y')}.{file_format}"

    if file_format == "pdf":
        return export_to_pdf(filename, config["headers"], rows)
    return export_to_excel(filename, config["headers"], rows)