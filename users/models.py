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
    
    @property
    def is_authenticated(self):
        return True

    def update_streak(self):
        """
        Actualiza la racha del usuario basado en su última actividad.
        - Si completó algo HOY: no cambia nada
        - Si completó algo AYER: incrementa racha
        - Si streak_last_day es null o pasó más de 1 día: inicia/resetea a 1
        """
        from datetime import date, timedelta

        today = date.today()

        if self.streak_last_day == today:
            # Ya completó algo hoy, no cambiar
            return

        if self.streak_last_day is None:
            # Primera vez que hace algo
            self.streak_current = 1
        elif self.streak_last_day == today - timedelta(days=1):
            # Completó algo ayer, incrementar racha
            self.streak_current += 1
        else:
            # Pasó más de 1 día sin hacer nada, resetear a 1
            self.streak_current = 1

        if self.streak_current > self.streak_best:
            self.streak_best = self.streak_current

        self.streak_last_day = today
        self.save()
        

class DailyCapacity(models.Model):
    """
    Mapea la tabla public.daily_capacity de Supabase
    """
    daily_capacity_id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    daily_limit_hours = models.DecimalField(max_digits=4, decimal_places=2, default=6)

    class Meta:
        db_table = 'daily_capacity'
        managed = False

    def __str__(self):
        return f"{self.user.name} - Limite: {self.daily_limit_hours}h"
