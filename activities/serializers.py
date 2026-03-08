from datetime import date
from rest_framework import serializers
from rest_framework.exceptions import APIException
from rest_framework import status
from django.db.models import Sum

from .models import Activity, Subtask
from users.models import DailyCapacity

class OverloadConflictException(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Conflicto de sobrecarga diaria.'
    default_code = 'overload_conflict'

    def __init__(self, detail=None, code=None, **kwargs):
        super().__init__(detail, code)
        # Permite retornar el payload exacto requerido (planned_hours, limit_hours, exceeds_by)
        self.detail = detail

class SubtaskSerializer(serializers.ModelSerializer):
    """Serializer para subtareas con validaciones US-02 y US-12 (overload)."""

    title = serializers.CharField(
        required=True,
        allow_blank=False,
        error_messages={
            'required': 'El título de la subtarea es obligatorio.',
            'blank': 'El título de la subtarea no puede estar vacío.',
        },
    )
    estimated_hours = serializers.FloatField(
        required=True,
        error_messages={
            'required': 'Las horas estimadas son obligatorias.',
        },
    )
    target_date = serializers.DateField(
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Subtask
        fields = [
            'id', 'activity', 'title', 'description', 'status',
            'target_date', 'estimated_hours',
        ]
        read_only_fields = ['id', 'activity']

    def validate_estimated_hours(self, value):
        """Las horas estimadas deben ser > 0 y <= 16."""
        if value <= 0:
            raise serializers.ValidationError(
                'Las horas estimadas deben ser mayores a 0.'
            )
        if value > 16:
            raise serializers.ValidationError(
                'Las horas estimadas no pueden superar 16 horas.'
            )
        return value

    def validate_target_date(self, value):
        """La fecha de la subtarea debe ser >= hoy."""
        if value and value < date.today():
            raise serializers.ValidationError(
                'La fecha de la subtarea no puede ser anterior a hoy.'
            )
        return value

    def validate(self, data):
        """
        La target_date de la subtarea no puede ser mayor
        que la due_date de la actividad asociada.
        """
        target_date = data.get('target_date')
        # La actividad se inyecta en el contexto desde la vista
        activity = self.context.get('activity')
        if not activity and self.instance:
            activity = self.instance.activity
        if target_date and activity and target_date > activity.due_date:
            raise serializers.ValidationError({
                'target_date': (
                    f'La fecha de la subtarea ({target_date}) no puede ser '
                    f'posterior a la fecha límite de la actividad ({activity.due_date}).'
                )
            })

        # --- US-12 Detección de sobrecarga diaria ---
        if target_date and activity:
            user_id = activity.user_id
            
            # 1. Obtener límite diario (fallback 6h si no existe)
            try:
                capacity_obj = DailyCapacity.objects.get(user__user_id=user_id)
                limit_hours = float(capacity_obj.daily_limit_hours)
            except DailyCapacity.DoesNotExist:
                limit_hours = 6.0
                
            # 2. Calcular horas planificadas para ese día (excluyendo 'done')
            # Si estamos actualizando (self.instance), excluir la propia subtarea
            # para no sumar sus horas antiguas que ya estaban planeadas.
            qs = Subtask.objects.filter(
                activity__user_id=user_id,
                target_date=target_date
            ).exclude(status='done')
            
            if self.instance:
                qs = qs.exclude(id=self.instance.id)
                
            planned_hours = qs.aggregate(
                total=Sum('estimated_hours')
            )['total'] or 0.0
            
            # 3. Validar si excede (planned + nueva estimación)
            # Priorizamos la estimación nueva en request, o la que ya tenía la subtarea
            new_estimated = data.get('estimated_hours', getattr(self.instance, 'estimated_hours', 0.0))
            total_after_save = planned_hours + new_estimated
            
            if total_after_save > limit_hours:
                exceeds_by = total_after_save - limit_hours
                raise OverloadConflictException({
                    'status': 'error',
                    'message': f'Quedarías con {total_after_save:g}h planificadas (límite {limit_hours:g}h)',
                    'planned_hours': planned_hours,
                    'limit_hours': limit_hours,
                    'exceeds_by': exceeds_by
                })

        return data


class ActivitySerializer(serializers.ModelSerializer):
    """
    Serializer para actividades evaluativas.
    Campos obligatorios: title, type, due_date.
    Campos opcionales: course, weight, user_id, subtasks.
    Status por defecto: pending.
    """
    subtasks = SubtaskSerializer(many=True, required=False)

    TYPE_LABELS = {
        'exam': 'Examen',
        'quiz': 'Quiz',
        'project': 'Proyecto',
        'homework': 'Tarea',
        'presentation': 'Presentación',
    }

    STATUS_LABELS = {
        'pending': 'Pendiente',
        'done': 'Completada',
        'postponed': 'Postergada',
        'overdue': 'Vencida',
    }

    type = serializers.ChoiceField(
        choices=['exam', 'quiz', 'project', 'homework', 'presentation'],
        error_messages={
            'required': 'El tipo de actividad es obligatorio.',
            'invalid_choice': 'Tipo inválido. Opciones: exam, quiz, project, homework, presentation.',
        }
    )

    due_date = serializers.DateField(
        required=True,
        error_messages={
            'required': 'La fecha límite es obligatoria.',
        }
    )


    class Meta:
        model = Activity
        fields = '__all__'
        # status ya no es read_only, se puede editar
        read_only_fields = ['id', 'user_id']

    def validate_due_date(self, value):
        """La fecha límite de la actividad debe ser >= hoy."""
        if value < date.today():
            raise serializers.ValidationError(
                'La fecha límite no puede ser anterior a hoy.'
            )
        return value

    def validate_weight(self, value):
        """El peso debe estar entre 0 y 100."""
        if value is not None:
            if value < 0:
                raise serializers.ValidationError('El peso no puede ser negativo.')
            if value > 100:
                raise serializers.ValidationError('El peso no puede ser mayor a 100.')
        return value

    def create(self, validated_data):
        """Crea la actividad junto con sus subtareas si se incluyen."""
        subtasks_data = validated_data.pop('subtasks', [])
        activity = Activity.objects.create(**validated_data)
        for subtask_data in subtasks_data:
            Subtask.objects.create(activity=activity, **subtask_data)
        return activity


class ActivityBriefSerializer(serializers.ModelSerializer):
    """ Info minima de la actividad padre"""
    class Meta:
        model = Activity
        fields = ['id', 'title', 'type', 'course', 'weight', 'due_date']

class TodaySubtaskSerializer(serializers.ModelSerializer):
    """Subtarea enriqueceda con su actividad padre + fecha efectiva """
    parent_activity = ActivityBriefSerializer(source='activity', read_only=True)

    class Meta:
        model = Subtask
        fields = ['id', 'title', 'description', 'status',
                  'target_date', 'estimated_hours',
                  'parent_activity']
        