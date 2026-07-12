from django.db import models
from models.base_models import BaseModel


class TextKeyModel(BaseModel):
    key = models.CharField(max_length=200, unique=True)
    default_text = models.CharField(max_length=255)

    def __str__(self):
        return self.key

    class Meta:
        app_label = "core"
        db_table = "text_keys"
        verbose_name = "Text Key"
        verbose_name_plural = "Text Keys"
