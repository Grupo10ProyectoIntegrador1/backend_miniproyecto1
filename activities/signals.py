from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Subtask

@receiver(post_save, sender=Subtask)
def update_user_streak_on_subtask_complete(sender, instance, created, update_fields, **kwargs):
    """
    Cuando una subtarea se marca como 'done', actualizar la racha del usuario.
    Solo actualiza si el status cambió a 'done' y tiene done_at.
    """
    # Verificar si el status cambió a 'done' en esta actualización
    if instance.status == 'done' and instance.done_at:
        # Si es un update, verificar que el status fue modificado
        if update_fields is None or 'status' in update_fields:
            from users.models import User
            try:
                user = User.objects.get(user_id=instance.activity.user_id)
                user.update_streak()
            except User.DoesNotExist:
                pass