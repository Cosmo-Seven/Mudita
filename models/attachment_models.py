from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from models.base_models import BaseModel

class DocumentTypeModel(BaseModel):
    code = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=150)
    applies_to = models.CharField(
        max_length=10,
        choices=(("employer", "Employer"), ("employee", "Employee"), ("both", "Both")),
        default="both",
    )
    is_required = models.BooleanField(default=False)
    has_expiry = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    class Meta:
        app_label = "core"
        db_table = "document_types"
        verbose_name = "Document Type"

class AddressModel(BaseModel):
    ADDRESS_TYPES = (("registered", "Registered"), ("workplace", "Workplace"), ("home", "Home"))

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    owner = GenericForeignKey("content_type", "object_id")

    address_type = models.CharField(max_length=20, choices=ADDRESS_TYPES)
    address_line = models.TextField()
    province = models.CharField(max_length=100, null=True, blank=True)
    district = models.CharField(max_length=100, null=True, blank=True)
    sub_district = models.CharField(max_length=100, null=True, blank=True)
    postal_code = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        app_label = "core"
        db_table = "addresses"
        verbose_name = "Address"


class DocumentModel(BaseModel):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    owner = GenericForeignKey("content_type", "object_id")

    doc_type = models.ForeignKey(DocumentTypeModel, on_delete=models.PROTECT)
    file = models.FileField(upload_to="documents/%Y/%m/")
    description = models.TextField(null=True, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)

    class Meta:
        app_label = "core"
        db_table = "documents"
        verbose_name = "Document"
