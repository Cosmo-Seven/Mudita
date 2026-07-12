from django import template
from helpers.translation import t

register = template.Library()


@register.simple_tag
def translate(key, lang_code="en"):
    return t(key, lang_code)


@register.filter
def get_translation(translations, arg):
    try:
        key_id, lang_code = arg.split("|")
        return translations.get(f"{key_id}|{lang_code}", "")
    except Exception:
        return ""
