from django.shortcuts import redirect


class LockScreenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        allowed_paths = ["/lock-screen/", "/unlock/"]

        if request.session.get("is_locked", False):
            if request.path not in allowed_paths:
                return redirect("lock_screen")

        return self.get_response(request)
