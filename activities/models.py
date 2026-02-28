from django.db import models
from django.core.exceptions import ValidationError


class Activity(models.Model):
    """Modelo de actividad evaluativa según el diagrama ER."""

    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('done', 'Completada'),
        ('postponed', 'Postergada'),
        ('overdue', 'Vencida'),
    ]

    TYPE_CHOICES = [
        ('exam', 'Examen'),
        ('quiz', 'Quiz'),
        ('project', 'Proyecto'),
        ('homework', 'Tarea'),
        ('presentation', 'Presentación'),
    ]

    # Mapeamos al esquema existente de Supabase: tabla `activity` con PK `activity_id`
    id = models.BigAutoField(primary_key=True, db_column='activity_id')
    title = models.CharField(max_length=255)
    type = models.CharField(max_length=100, choices=TYPE_CHOICES)
    course = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    due_date = models.DateField()
    weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    user_id = models.BigIntegerField()

    class Meta:
        db_table = 'activity'
        ordering = ['-due_date']

    def __str__(self):
        return f"{self.title} ({self.course})"


class Subtask(models.Model):
    """Modelo de subtarea asociada a una actividad evaluativa."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
    ]

    # PK mapeado a subtask_id (bigint) en Supabase
    id = models.BigAutoField(primary_key=True, db_column='subtask_id')
    # FK mapeado a activity_id (int8) en Supabase
    activity = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
        related_name='subtasks',
        db_column='activity_id'
    )
    title = models.CharField(max_length=255)
    target_date = models.DateField(null=True, blank=True)
    estimated_hours = models.FloatField(null=True, blank=True)
    description = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    class Meta:
        db_table = 'subtask'

    def __str__(self):
        return self.title
