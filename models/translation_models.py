from django.db import models
from models.base_models import BaseModel


class TranslationModel(BaseModel):
    language = models.ForeignKey("core.LanguageModel", on_delete=models.CASCADE)
    text_key = models.ForeignKey("core.TextKeyModel", on_delete=models.CASCADE)
    translated_text = models.CharField(max_length=255)

    class Meta:
        unique_together = ("language", "text_key")
        app_label = "core"
        db_table = "translations"
        verbose_name = "Translation"
        verbose_name_plural = "Translations"

    def __str__(self):
        return f"{self.language} - {self.text_key} - {self.translated_text}"
