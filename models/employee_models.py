from django.db import models
from django.utils.text import slugify
from models.base_models import BaseModel
from models.employer_models import EmployerModel
from models.attachment_models import AddressModel, DocumentModel
from helpers.translation import register_key
from django.contrib.contenttypes.fields import GenericRelation
from datetime import date

class NationalityModel(BaseModel):
    name = models.CharField(max_length=100)
    country_code = models.CharField(max_length=3, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        app_label = "core"
        db_table = "nationalities"
        verbose_name = "Nationality"
        verbose_name_plural = "Nationalities"


class EmployeeModel(BaseModel):
    STATUS_CHOICES = (
        ("registration_pending", "Registration Pending"),
        ("active", "Active (Confirmed)"),
        ("renewal_pending", "Renewal Pending"),
        ("terminated", "Terminated/Resigned"),
    )
    GENDER_CHOICES = (("male", "Male"), ("female", "Female"))

    employer = models.ForeignKey(
        EmployerModel, on_delete=models.PROTECT, related_name="employees"
    )
    user = models.OneToOneField(
        "core.UserModel", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="employee_profile",
    )

    # --- Personal Information ---
    title_th = models.CharField(max_length=20, null=True, blank=True)
    name_th = models.CharField(max_length=255, null=True, blank=True)
    prefix_en = models.CharField(max_length=20, null=True, blank=True)
    full_name_en = models.CharField(max_length=255)
    name_suffix_en = models.CharField(max_length=100, null=True, blank=True)
    photo = models.ImageField(upload_to="employee_photos", null=True, blank=True)
    height_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    father_name = models.CharField(max_length=255, null=True, blank=True)
    mother_name = models.CharField(max_length=255, null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)

    # --- Contact & Nationality ---
    phone = models.CharField(max_length=50, null=True, blank=True)
    nationality = models.ForeignKey(NationalityModel, on_delete=models.SET_NULL, null=True, blank=True)

    # --- Passport & Visa ---
    passport_number = models.CharField(max_length=50, null=True, blank=True)
    passport_issue_place = models.CharField(max_length=255, null=True, blank=True)
    passport_issue_date = models.DateField(null=True, blank=True)
    passport_expiry_date = models.DateField(null=True, blank=True)
    pink_card_number = models.CharField(max_length=50, null=True, blank=True)
    visa_type = models.CharField(max_length=100, null=True, blank=True)
    visa_issue_place = models.CharField(max_length=255, null=True, blank=True)
    visa_expiry_date = models.DateField(null=True, blank=True)
    visa_stamp_date = models.DateField(null=True, blank=True)
    visa_number = models.CharField(max_length=50, null=True, blank=True)

    # --- Employment Info & Documents ---
    job_position = models.CharField(max_length=255, null=True, blank=True)
    job_description = models.TextField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    work_permit_number = models.CharField(max_length=50, null=True, blank=True)
    work_permit_issue_date = models.DateField(null=True, blank=True)
    work_permit_expiry_date = models.DateField(null=True, blank=True)
    report_90day_date = models.DateField(null=True, blank=True)
    work_permit_type = models.CharField(max_length=100, null=True, blank=True)
    ra_number = models.CharField(max_length=50, null=True, blank=True)
    application_number = models.CharField(max_length=50, null=True, blank=True)
    identification_number = models.CharField(max_length=50, null=True, blank=True)
    tax_id_number = models.CharField(max_length=50, null=True, blank=True)
    worker_employer_code = models.CharField(max_length=50, null=True, blank=True)
    work_department = models.CharField(max_length=255, null=True, blank=True)
    bank_name = models.CharField(max_length=255, null=True, blank=True)
    bank_account_number = models.CharField(max_length=50, null=True, blank=True)
    worker_reference_number = models.CharField(max_length=50, null=True, blank=True)

    # --- Health Insurance ---
    insurance_type = models.CharField(max_length=100, null=True, blank=True)
    diagnosed_hospital = models.CharField(max_length=255, null=True, blank=True)

    # --- Login Info (outsource system) ---
    login_email = models.EmailField(null=True, blank=True)

    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="registration_pending")

    addresses = GenericRelation(AddressModel)
    documents = GenericRelation(DocumentModel)

    def __str__(self):
        return self.full_name_en

    class Meta:
        app_label = "core"
        db_table = "employees"
        verbose_name = "Employee"
        verbose_name_plural = "Employees"

    def save(self, *args, **kwargs):
        key = slugify(self.full_name_en).replace("-", "_").lower()
        register_key(key, self.full_name_en)
        super().save(*args, **kwargs)

    @property
    def translation_key(self):
        return slugify(self.full_name_en).replace("-", "_").lower()

    @property
    def age(self):
        from datetime import date
        if not self.date_of_birth:
            return None
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    def _expiry_status(self, expiry_date, warn_days=90):
        if not expiry_date:
            return "unknown"
        days_left = (expiry_date - date.today()).days
        if days_left < 0:
            return "expired"
        if days_left <= warn_days:
            return "expiring_soon"
        return "valid"

    @property
    def passport_status(self):
        return self._expiry_status(self.passport_expiry_date)

    @property
    def visa_status(self):
        return self._expiry_status(self.visa_expiry_date)

    @property
    def work_permit_status(self):
        return self._expiry_status(self.work_permit_expiry_date)

    @property
    def has_bank_account(self):
        return bool(self.bank_name and self.bank_account_number)

    @property
    def has_pink_card(self):
        return bool(self.pink_card_number)

    @property
    def days_until_90day_report(self):
        if not self.report_90day_date:
            return None
        return (self.report_90day_date - date.today()).days