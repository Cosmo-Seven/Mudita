from django.db import models
from models.base_models import BaseModel
from django.utils.text import slugify
from helpers.translation import register_key


class RoleModel(BaseModel):
    name = models.CharField(max_length=255, unique=True)
    permissions = models.ManyToManyField("auth.Permission")

    def __str__(self):
        return self.name

    class Meta:
        app_label = "core"
        db_table = "roles"
        verbose_name = "Role"
        verbose_name_plural = "Roles"

    def save(self, *args, **kwargs):
        key = slugify(self.name).replace("-", "_").lower()
        register_key(key, self.name)
        super().save(*args, **kwargs)

    @property
    def translation_key(self):
        return slugify(self.name).replace("-", "_").lower()
