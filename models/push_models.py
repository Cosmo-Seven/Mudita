from django.db import models

from models.base_models import BaseModel


class PushSubscriptionModel(BaseModel):
    """Web Push (VAPID) subscription ကို browser တစ်ခုချင်းအလိုက် သိမ်းထားတဲ့ model."""

    user = models.ForeignKey(
        "core.UserModel",
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
    )
    endpoint = models.TextField(unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    user_agent = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.user_id} · {self.endpoint[:40]}"

    class Meta:
        app_label = "core"
        db_table = "push_subscriptions"
        verbose_name = "Push Subscription"
        verbose_name_plural = "Push Subscriptions"
