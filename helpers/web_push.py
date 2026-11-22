import json
import logging

from django.conf import settings
from django.utils import timezone

from pywebpush import WebPushException, webpush

logger = logging.getLogger(__name__)

# These status codes mean the subscription no longer exists on the push service.
GONE_STATUS_CODES = (404, 410)

STATUS_SENT = "sent"
STATUS_GONE = "gone"
STATUS_FAILED = "failed"


def _vapid_claims():
    return {"sub": f"mailto:{settings.VAPID_ADMIN_EMAIL}"}


def send_to_subscription(subscription, payload):
    """Send one push and report what happened: sent / gone / failed."""
    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=json.dumps(payload),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims=_vapid_claims(),
        )
        return STATUS_SENT
    except WebPushException as exc:
        if getattr(exc.response, "status_code", None) in GONE_STATUS_CODES:
            return STATUS_GONE
        logger.warning("Web push failed for %s: %s", subscription.endpoint[:40], exc)
        return STATUS_FAILED


def push_to_user(user, payload):
    """Send to every active subscription of a user. Returns the number delivered."""
    if not settings.VAPID_PRIVATE_KEY:
        return 0

    delivered = 0
    subscriptions = user.push_subscriptions.filter(is_deleted=False)
    for subscription in subscriptions:
        status = send_to_subscription(subscription, payload)
        if status == STATUS_SENT:
            delivered += 1
        elif status == STATUS_GONE:
            subscription.is_deleted = True
            subscription.deleted_at = timezone.now()
            subscription.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
    return delivered
