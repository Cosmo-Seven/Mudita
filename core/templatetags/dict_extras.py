# core/templatetags/dict_extras.py
from django import template
register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def stage_done(stage_logs, stage_id):
    return any(log.stage_id == stage_id for log in stage_logs)