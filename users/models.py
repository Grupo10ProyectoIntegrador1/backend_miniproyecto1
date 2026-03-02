import uuid
from django.db import models

class User(models.Model):
    """
    Mapea la tabla public.user de Supabase
    user_id -> PK entera (la que usamos en activity.user_id)
    uuid_user -> UUID que viene del JWT de Supabase Auth 
    """
    user_id = models.BigAutoField(primary_key=True)
    uuid_user = models.UUIDField(unique=True)
    name = models.TextField()
    last_name = models.TextField()
    streak_current = models.IntegerField(default=0)
    streak_last_day = models.DateField(null=True, blank=True)
    streak_best = models.IntegerField(default=0)

    class Meta: 
        db_table = 'user'
        managed = False

    def __str__(self):
        return f"{self.name} {self.last_name}"
    

