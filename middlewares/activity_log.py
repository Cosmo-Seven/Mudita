from django.conf import settings

from core.models import ActivityLogModel


class ActivityLogMiddleware:
    """Login ဝင်ထားတဲ့ user တွေ ဘယ် route ကို သွားပြီး ဘာ action လုပ်ခဲ့လဲ ဆိုတာ
    ActivityLogModel မှာ မှတ်တမ်းတင်ပေးတဲ့ middleware။"""

    ACTION_CONTAINS = (
        ("delete", "delete"),
        ("remove", "delete"),
        ("restore", "restore"),
        ("logout", "logout"),
        ("login", "login"),
        ("create", "create"),
        ("add", "create"),
        ("import", "create"),
        ("upload", "create"),
        ("submit", "create"),
        ("subscribe", "create"),
        ("save", "create"),
        ("update", "update"),
        ("edit", "update"),
        ("toggle", "update"),
        ("unlock", "update"),
        ("lock", "update"),
        ("reorder", "update"),
        ("move", "update"),
        ("set_", "update"),
        ("bulk", "update"),
    )

    def __init__(self, get_response):
        self.get_response = get_response
        self.ignored_prefixes = tuple(
            [
                f"/{prefix.strip('/')}/"
                for prefix in (settings.STATIC_URL, settings.MEDIA_URL)
                if prefix
            ]
            + [f"/{settings.ADMIN_LOGIN_URL.strip('/')}/"]
        )

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._save_log(request, response)
        except Exception:
            # Log ရေးရင်း error တက်လို့ request ကို ဘယ်တော့မှ မဖျက်ပါ
            pass
        return response

    def _save_log(self, request, response):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return

        path = request.path_info
        if path.startswith(self.ignored_prefixes):
            return

        match = getattr(request, "resolver_match", None)
        route_name = getattr(match, "url_name", "") or ""
        kwargs = getattr(match, "kwargs", None) or {}
        object_id = ""
        for key in ("pk", "object_id", "employee_id", "employer_id", "group_id", "stage_id"):
            if key in kwargs:
                object_id = str(kwargs[key])
                break

        method = request.method
        ActivityLogModel.objects.create(
            user=user if getattr(user, "pk", None) else None,
            user_email=getattr(user, "email", "") or "",
            method=method,
            action=self._classify(method, route_name),
            path=path[:500],
            route_name=route_name[:150],
            object_id=object_id[:100],
            status_code=getattr(response, "status_code", None),
            ip_address=self._client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:2000],
        )

    @classmethod
    def _classify(cls, method, route_name):
        name = (route_name or "").lower()
        if method == "GET":
            if "logout" in name:
                return "logout"
            if "login" in name:
                return "login"
            return "view"
        if method == "POST":
            for needle, action in cls.ACTION_CONTAINS:
                if needle in name:
                    return action
            return "action"
        return method.lower()

    @staticmethod
    def _client_ip(request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
