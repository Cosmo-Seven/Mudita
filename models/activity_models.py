import uuid

from django.db import models


class ActivityLogModel(models.Model):
    """Login ဝင်ထားတဲ့ user တွေ ဘယ် route ကို သွားပြီး ဘာလုပ်ခဲ့လဲ ဆိုတာ မှတ်တမ်းတင်ထားတဲ့ log။"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "core.UserModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    user_email = models.CharField(max_length=255, blank=True)
    method = models.CharField(max_length=10, blank=True)
    action = models.CharField(max_length=30, blank=True)
    path = models.CharField(max_length=500, blank=True)
    route_name = models.CharField(max_length=150, blank=True)
    object_id = models.CharField(max_length=100, blank=True)
    status_code = models.PositiveIntegerField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = "core"
        db_table = "activity_logs"
        verbose_name = "Activity Log"
        verbose_name_plural = "Activity Logs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_email or 'system'} - {self.method} {self.path}"
