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
    estimated_hours = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
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
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'activity', 'created_at', 'updated_at']

    def validate_estimated_hours(self, value):
        """Las horas estimadas deben ser mayores a 0."""
        if value <= 0:
            raise serializers.ValidationError(
                'Las horas estimadas deben ser mayores a 0.'
            )
        return value



class ActivitySerializer(serializers.ModelSerializer):
    """
    Serializer para actividades evaluativas.
    Permite crear una actividad con subtareas anidadas en una sola petición.
    Valida campos obligatorios: title, type, course.
    Valida que se incluya al menos una subtarea.
    """
    subtasks = SubtaskSerializer(many=True)

    class Meta:
        model = Activity
        fields = [
            'id', 'title', 'type', 'course', 'status',
            'due_date', 'weight', 'user_id',
            'subtasks',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'status', 'created_at', 'updated_at']

    def validate_subtasks(self, value):
        """Valida que se incluya al menos una subtarea."""
        if not value or len(value) == 0:
            raise serializers.ValidationError(
                "Debe incluir al menos una subtarea."
            )
        return value

    def create(self, validated_data):
        """Crea la actividad junto con sus subtareas en una transacción."""
        subtasks_data = validated_data.pop('subtasks')
        activity = Activity.objects.create(**validated_data)
        for subtask_data in subtasks_data:
            Subtask.objects.create(activity=activity, **subtask_data)
        return activity
