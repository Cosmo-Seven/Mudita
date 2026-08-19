# helpers/translation.py
import re
from django.core.cache import cache

CACHE_TTL = 300  # 5 minutes


def _prettify(key):
    words = re.sub(r"[_\-]+", " ", key).strip().split()
    return " ".join(w.upper() if w.lower() == "id" else w.capitalize() for w in words)


def _load_translation_map(lang_code):
    cache_key = f"translations:{lang_code}"
    data = cache.get(cache_key)
    if data is not None:
        return data

    from models.language_models import LanguageModel
    from models.text_key_models import TextKeyModel
    from models.translation_models import TranslationModel

    data = {tk.key: tk.default_text for tk in TextKeyModel.objects.all()}   # 1 query

    try:
        lang = LanguageModel.objects.get(code=lang_code)                     # 1 query
        translations = TranslationModel.objects.filter(language=lang).select_related("text_key")  # 1 query
        for tr in translations:
            data[tr.text_key.key] = tr.translated_text
    except LanguageModel.DoesNotExist:
        pass

    cache.set(cache_key, data, CACHE_TTL)
    return data


def t(key, lang_code="en"):
    data = _load_translation_map(lang_code)
    if key in data:
        return data[key]

    pretty = _prettify(key)
    register_key(key, pretty)
    cache.delete(f"translations:{lang_code}")   # key အသစ်ထည့်လိုက်တာမို့ cache bust
    return pretty


def register_key(key, default_text):
    from models.text_key_models import TextKeyModel
    TextKeyModel.objects.get_or_create(key=key, defaults={"default_text": default_text})