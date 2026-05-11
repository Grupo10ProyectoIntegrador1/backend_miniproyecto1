from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Subtask

@receiver(post_save, sender=Subtask)
def update_user_streak_on_subtask_complete(sender, instance, created, **kwargs):
    """
    Cuando una subtarea se marca como 'done', actualizar la racha del usuario.
    """
    if instance.status == 'done' and instance.done_at:
        user = instance.activity.user
        # Llamar el método para actualizar racha
        user.update_streak()