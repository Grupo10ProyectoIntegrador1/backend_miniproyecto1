from datetime import date
from rest_framework import serializers
from .models import Activity, Subtask


class SubtaskSerializer(serializers.ModelSerializer):
    """Serializer para subtareas con validaciones US-02."""

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
