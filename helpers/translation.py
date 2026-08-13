# helpers/translation.py
import re


def _prettify(key):
    """'add_new_role' -> 'Add New Role', 'employer_id_number' -> 'Employer ID Number'"""
    words = re.sub(r"[_\-]+", " ", key).strip().split()
    return " ".join(w.upper() if w.lower() == "id" else w.capitalize() for w in words)


def t(key, lang_code="en"):
    from models.language_models import LanguageModel
    from models.text_key_models import TextKeyModel
    from models.translation_models import TranslationModel

    try:
        lang = LanguageModel.objects.get(code=lang_code)
        text_key = TextKeyModel.objects.get(key=key)
        translation = TranslationModel.objects.get(language=lang, text_key=text_key)
        return translation.translated_text
    except Exception:
        try:
            return TextKeyModel.objects.get(key=key).default_text
        except TextKeyModel.DoesNotExist:
            pretty = _prettify(key)
            register_key(key, pretty)
            return pretty


def register_key(key, default_text):
    from models.text_key_models import TextKeyModel

    try:
        TextKeyModel.objects.get(key=key)
    except TextKeyModel.DoesNotExist:
        TextKeyModel.objects.create(key=key, default_text=default_text)