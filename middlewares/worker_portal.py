from django.conf import settings
from django.shortcuts import redirect

from core.models import EmployeeModel


class WorkerPortalMiddleware:
    allowed_paths = {
        "/worker/",
        "/worker/profile/",
        "/worker/requests/submit/",
        "/worker/push/subscribe/",
    }

    def __init__(self, get_response):
        self.get_response = get_response
        self.login_path = f"/{settings.DASHBOARD_LOGIN_URL.strip('/')}/"
        self.logout_path = f"/{settings.DASHBOARD_LOGOUT_URL.strip('/')}/"
        self.static_prefix = f"/{settings.STATIC_URL.strip('/')}/"
        self.media_prefix = f"/{settings.MEDIA_URL.strip('/')}/"

    def __call__(self, request):
        user = request.user
        if (
            user.is_authenticated
            and not user.is_staff
            and EmployeeModel.objects.filter(user=user, is_deleted=False).exists()
            and request.path_info not in self.allowed_paths
            and request.path_info not in (self.login_path, self.logout_path)
            and not request.path_info.startswith(
                (self.static_prefix, self.media_prefix)
            )
        ):
            return redirect("worker_profile")
        return self.get_response(request)
