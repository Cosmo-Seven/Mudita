from django.db import models
from django.utils.text import slugify
from models.base_models import BaseModel
from models.attachment_models import AddressModel, DocumentModel
from helpers.translation import register_key
from django.contrib.contenttypes.fields import GenericRelation

class BusinessTypeModel(BaseModel):
    name_th = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255)

    def __str__(self):
        return self.name_en

    class Meta:
        app_label = "core"
        db_table = "business_types"
        verbose_name = "Business Type"
        verbose_name_plural = "Business Types"


class EmployerModel(BaseModel):
    STATUS_CHOICES = (
        ("active", "Active"),
        ("inactive", "Inactive"),
    )

    name_th = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255)
    name_suffix_en = models.CharField(max_length=100, null=True, blank=True)
    employer_code = models.CharField(max_length=50, unique=True, null=True, blank=True)

    parent_employer = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="branches"
    )
    responsible_person = models.ForeignKey(
        "core.UserModel", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="employers_responsible",
    )

    employer_id_number = models.CharField(max_length=50, null=True, blank=True)
    business_type = models.ForeignKey(
        BusinessTypeModel, on_delete=models.SET_NULL, null=True, blank=True
    )
    business_type_th = models.CharField(max_length=255, null=True, blank=True)
    business_type_en = models.CharField(max_length=255, null=True, blank=True)

    phone = models.CharField(max_length=50, null=True, blank=True)
    social_security_hospital = models.CharField(max_length=255, null=True, blank=True)

    portal_email = models.EmailField(null=True, blank=True)
    re_code = models.CharField(max_length=100, null=True, blank=True)

    authorized_signatory_1_th = models.CharField(max_length=255, null=True, blank=True)
    authorized_signatory_1_en = models.CharField(max_length=255, null=True, blank=True)
    authorized_signatory_2_th = models.CharField(max_length=255, null=True, blank=True)
    authorized_signatory_2_en = models.CharField(max_length=255, null=True, blank=True)

    stamp = models.ImageField(upload_to="employer_stamps", null=True, blank=True)
    registered_capital = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    registration_date = models.DateField(null=True, blank=True)
    minimum_wage = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    addresses = GenericRelation(AddressModel)
    documents = GenericRelation(DocumentModel)

    def __str__(self):
        return self.name_en

    class Meta:
        app_label = "core"
        db_table = "employers"
        verbose_name = "Employer"
        verbose_name_plural = "Employers"

    def save(self, *args, **kwargs):
        if not self.employer_code:
            self.employer_code = self._generate_code()
        key = slugify(self.name_en).replace("-", "_").lower()
        register_key(key, self.name_en)
        super().save(*args, **kwargs)

    def _generate_code(self):
        last = EmployerModel.objects.order_by("-created_at").first()
        n = 1
        if last and last.employer_code and last.employer_code.startswith("EMP"):
            try:
                n = int(last.employer_code.replace("EMP", "")) + 1
            except ValueError:
                pass
        return f"EMP{n:05d}"

    @property
    def translation_key(self):
        return slugify(self.name_en).replace("-", "_").lower()