import uuid
from django.db import models
from django.core.exceptions import ValidationError


class Activity(models.Model):
    """Modelo de actividad evaluativa según el diagrama ER."""

    STATUS_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('en_progreso', 'En Progreso'),
        ('completada', 'Completada'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    type = models.CharField(max_length=100)
    course = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendiente')
    due_date = models.DateField(null=True, blank=True)
    weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    user_id = models.IntegerField(null=True, blank=True)  # Sprint 0-1: sin autenticación
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'activities'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.course})"


class Subtask(models.Model):
    """Modelo de subtarea asociada a una actividad evaluativa."""

    STATUS_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('en_progreso', 'En Progreso'),
        ('completada', 'Completada'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
        related_name='subtasks'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendiente')
    target_date = models.DateField(null=True, blank=True)
    estimated_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'subtasks'
        ordering = ['created_at']

    def __str__(self):
        return self.title

    def clean(self):
        """Validaciones de negocio a nivel de modelo."""
        super().clean()
        if not self.title or not self.title.strip():
            raise ValidationError({'title': 'El título de la subtarea es obligatorio.'})
        if self.estimated_hours is not None and self.estimated_hours <= 0:
            raise ValidationError(
                {'estimated_hours': 'Las horas estimadas deben ser mayores a 0.'}
            )
