from django.db import models
from models.base_models import BaseModel
from django.utils.text import slugify


class SiteModel(BaseModel):
    name = models.CharField(max_length=255)
    email = models.CharField(max_length=255, null=True)
    phone = models.CharField(max_length=255, null=True)
    address = models.TextField(null=True)
    favicon = models.ImageField(upload_to="favicon")
    logo = models.ImageField(upload_to="logo", null=True)

    def __str__(self):
        return self.name

    class Meta:
        app_label = "core"
        db_table = "sites"
        verbose_name = "Site"
        verbose_name_plural = "Sites"


    @property
    def translation_key(self):
        return slugify(self.name).replace("-", "_").lower()
