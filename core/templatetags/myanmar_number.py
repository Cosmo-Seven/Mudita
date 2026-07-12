from django import template

register = template.Library()


@register.filter
def mm_number(value):
    myanmar_digits = {
        "0": "၀",
        "1": "၁",
        "2": "၂",
        "3": "၃",
        "4": "၄",
        "5": "၅",
        "6": "၆",
        "7": "၇",
        "8": "၈",
        "9": "၉",
    }
    return "".join(myanmar_digits.get(char, char) for char in str(value))
