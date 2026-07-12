from django.apps import apps


def get_allowed_models():
    EXCLUDED_MODELS = ["userlocationmodel", "logentry", "session"]

    return [
        model._meta.model_name
        for model in apps.get_app_config("core").get_models()
        if not model._meta.abstract and model._meta.model_name not in EXCLUDED_MODELS
    ]
