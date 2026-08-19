from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from models.text_key_models import TextKeyModel
from models.translation_models import TranslationModel


@receiver([post_save, post_delete], sender=TextKeyModel)
@receiver([post_save, post_delete], sender=TranslationModel)
def clear_translation_cache(sender, **kwargs):
    cache.clear()