from django.shortcuts import redirect
from django.conf import settings


def maintenance_required(view_func):
    def _wrapped_view(request, *args, **kwargs):

        if getattr(settings, "MAINTENANCE_MODE", False):
            return redirect("under_maintenance")

        return view_func(request, *args, **kwargs)

    return _wrapped_view
