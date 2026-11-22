from django.db import models


class TrashModel(models.Model):
    """Trash နဲ့ ဆိုင်တဲ့ permission တွေ host လုပ်ဖို့ သုံးတဲ့ model သာ။
    အမှန်တကယ် database table မဖန်တီးပါ (managed=False)။"""

    id = models.UUIDField(primary_key=True, editable=False)

    class Meta:
        app_label = "core"
        managed = False
        verbose_name = "Trash"
        verbose_name_plural = "Trash"
        permissions = [
            ("restore_trashmodel", "Can restore items from Trash"),
        ]

    def __str__(self):
        return "Trash"
