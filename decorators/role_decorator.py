from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.conf import settings


def role_permission_required(permission_codenames):
    if isinstance(permission_codenames, str):
        permission_codenames = [permission_codenames]

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, "You must be logged in to access this page.")
                return redirect(
                    request.META.get("HTTP_REFERER", "/" + settings.DASHBOARD_LOGIN_URL)
                )
            if any(request.user.has_permission(perm) for perm in permission_codenames):
                return view_func(request, *args, **kwargs)
            else:
                messages.error(
                    request, "You do not have permission to access this page."
                )
                return redirect(
                    request.META.get("HTTP_REFERER", "/" + settings.DASHBOARD_LOGIN_URL)
                )

        return _wrapped_view

    return decorator
