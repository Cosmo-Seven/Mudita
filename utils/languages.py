from core.models import LanguageModel


def languages(request):
    languages = LanguageModel.objects.all()
    current_language = None
    for language in languages:
        if language.code == request.session.get("language"):
            current_language = language
            break

    context = {"languages": languages, "current_language": current_language}
    return context
