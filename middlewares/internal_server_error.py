from django.shortcuts import render


class InternalServerErrorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        return render(request, "dashboard/internal_server_error.html", status=500)
