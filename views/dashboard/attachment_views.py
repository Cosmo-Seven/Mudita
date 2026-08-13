from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.contenttypes.models import ContentType

from utils.decorators import custom_login_required
from decorators.role_decorator import role_permission_required
from helpers.allowed_models import get_allowed_models
from constants.message import CREATE, UPDATE, DELETE
from core.models import AddressModel, DocumentModel, DocumentTypeModel


def _resolve_owner(model_name, object_id):
    """
    'employer' / 'employee' စတဲ့ model_name string ကနေ
    ContentType + object instance ကို ရှာပေးတဲ့ helper.
    ALLOWED_MODELS ထဲ ပါမှသာ ခွင့်ပြုတယ် (helpers/allowed_models.py) —
    ဒါမှသာ URL parameter ကနေ ကျပန်း model ကို attack မလုပ်နိုင်အောင်။
    """
    if model_name not in get_allowed_models():
        return None, None

    content_type = get_object_or_404(ContentType, app_label="core", model=model_name)
    owner = get_object_or_404(content_type.model_class(), id=object_id)
    return content_type, owner


# ========================
# Address Add
# ========================
@custom_login_required("dashboard_login")
def address_add(request, model_name, object_id):
    content_type, owner = _resolve_owner(model_name, object_id)
    if owner is None:
        messages.error(request, "Invalid target for address.")
        return redirect("dashboard")

    redirect_name = f"{model_name}_detail"

    if request.method == "POST":
        AddressModel.objects.create(
            content_type=content_type,
            object_id=owner.id,
            address_type=request.POST.get("address_type"),
            address_line=request.POST.get("address_line"),
            province=request.POST.get("province"),
            district=request.POST.get("district"),
            sub_district=request.POST.get("sub_district"),
            postal_code=request.POST.get("postal_code"),
            created_by=request.user,
        )
        messages.success(request, CREATE)
        return redirect(redirect_name, pk=owner.id)

    return redirect(redirect_name, pk=owner.id)


# ========================
# Address Update
# ========================
@custom_login_required("dashboard_login")
def address_update(request, pk):
    address = get_object_or_404(AddressModel, id=pk)
    owner = address.owner
    redirect_name = f"{address.content_type.model}_detail"

    if request.method == "POST":
        address.address_type = request.POST.get("address_type")
        address.address_line = request.POST.get("address_line")
        address.province = request.POST.get("province")
        address.district = request.POST.get("district")
        address.sub_district = request.POST.get("sub_district")
        address.postal_code = request.POST.get("postal_code")
        address.updated_by = request.user
        address.save()
        messages.success(request, UPDATE)

    return redirect(redirect_name, pk=owner.id)


# ========================
# Address Delete
# ========================
@custom_login_required("dashboard_login")
def address_delete(request, pk):
    address = get_object_or_404(AddressModel, id=pk)
    owner_id = address.object_id
    redirect_name = f"{address.content_type.model}_detail"

    if request.method == "POST":
        address.delete()
        messages.success(request, DELETE)

    return redirect(redirect_name, pk=owner_id)


# ========================
# Document Upload
# ========================
@custom_login_required("dashboard_login")
def document_upload(request, model_name, object_id):
    content_type, owner = _resolve_owner(model_name, object_id)
    if owner is None:
        messages.error(request, "Invalid target for document.")
        return redirect("dashboard")

    redirect_name = f"{model_name}_detail"

    if request.method == "POST":
        file = request.FILES.get("file")
        doc_type_id = request.POST.get("doc_type")

        if not file or not doc_type_id:
            messages.error(request, "Please choose a document type and a file.")
            return redirect(redirect_name, pk=owner.id)

        DocumentModel.objects.create(
            content_type=content_type,
            object_id=owner.id,
            doc_type_id=doc_type_id,
            file=file,
            description=request.POST.get("description"),
            issue_date=request.POST.get("issue_date") or None,
            expiry_date=request.POST.get("expiry_date") or None,
            created_by=request.user,
        )
        messages.success(request, CREATE)

    return redirect(redirect_name, pk=owner.id)


# ========================
# Document Delete
# ========================
@custom_login_required("dashboard_login")
def document_delete(request, pk):
    document = get_object_or_404(DocumentModel, id=pk)
    owner_id = document.object_id
    redirect_name = f"{document.content_type.model}_detail"

    if request.method == "POST":
        if document.file:
            document.file.delete(save=False)
        document.delete()
        messages.success(request, DELETE)

    return redirect(redirect_name, pk=owner_id)


# ========================
# Document Type — List / Create (lookup management, settings menu)
# ========================
@custom_login_required("dashboard_login")
@role_permission_required("view_documenttypemodel")
def document_type_list(request):
    doc_types = DocumentTypeModel.objects.all().order_by("name")
    return render(request, "dashboard/document_type_list.html", {"doc_types": doc_types})


@custom_login_required("dashboard_login")
@role_permission_required("add_documenttypemodel")
def document_type_create(request):
    if request.method == "POST":
        DocumentTypeModel.objects.create(
            name=request.POST.get("name"),
            applies_to=request.POST.get("applies_to", "both"),
            is_required="is_required" in request.POST,
            has_expiry="has_expiry" in request.POST,
            created_by=request.user,
        )
        messages.success(request, CREATE)
        return redirect("document_type_list")

    return redirect("document_type_list")