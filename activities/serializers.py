from datetime import date
from rest_framework import serializers
from rest_framework import status
from django.db.models import Sum

from .models import Activity, Subtask
from users.models import DailyCapacity

class SubtaskSerializer(serializers.ModelSerializer):
    """Serializer para subtareas con validaciones (overload)."""

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
            'target_date', 'estimated_hours', 'note', 'done_at',
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
        target_date = data.get('target_date', getattr(self.instance, 'target_date', None))
        status_val = data.get('status', getattr(self.instance, 'status', 'pending'))

        # --- Protección de Estados ---
        if self.instance:
            old_status = self.instance.status
            # Si era 'overdue' y le asignan nueva fecha a futuro, pasa a 'postponed'
            if old_status == 'overdue' and status_val == 'overdue' and target_date and target_date >= date.today():
                data['status'] = 'postponed'
                status_val = 'postponed'
            elif status_val != old_status and status_val not in ['done', 'pending', 'postponed']:
                # El usuario sólo debería poder pasar a 'done' manualmente (o pending)
                # 'postponed' se setea auto (arriba). Si manda 'overdue' manualmente, bloqueamos (a no ser que ya estuviera vencida).
                pass
        else:
            # Creación nueva: no puede nacer ni done, ni postponed ni overdue
            if status_val not in ['pending', 'done']:
                data['status'] = 'pending'
                status_val = 'pending'

        from django.utils import timezone
        
        if self.instance and self.instance.note:
            new_note = data.get('note', None)
            if new_note == '' or new_note is None:
                data['note'] = self.instance.note

        if status_val == 'done':
            # Se completará automáticamente el campo `done_at` si no se proporciona
            if not data.get('done_at') and not getattr(self.instance, 'done_at', None):
                data['done_at'] = timezone.now()
        else:
            # Se borrará el campo `done_at` si el estado ya no es "completado".
            data['done_at'] = None

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
            
            # Si el nuevo estado es 'done', esa tarea deja de contar para la sobrecarga
            if status_val == 'done':
                new_estimated = 0.0
                
            total_after_save = planned_hours + new_estimated
            
            if total_after_save > limit_hours:
                exceeds_by = total_after_save - limit_hours
                
                # Buscar 1 día alternativo
                from datetime import timedelta
                alternative_dates = []
                check_date = target_date + timedelta(days=1)
                days_checked = 0
                max_days_to_check = 30 # Limitar la búsqueda a 30 días para evitar loops infinitos
                
                while len(alternative_dates) < 1 and days_checked < max_days_to_check:
                    # Verificar si check_date supera el due_date de la actividad
                    if activity and activity.due_date and check_date > activity.due_date:
                        break # No buscar más allá de la fecha de entrega

                    # Calcular horas planificadas en check_date
                    day_planned_hours = Subtask.objects.filter(
                        activity__user_id=user_id,
                        target_date=check_date
                    ).exclude(status='done').aggregate(
                        total=Sum('estimated_hours')
                    )['total'] or 0.0
                    
                    if (day_planned_hours + exceeds_by) <= limit_hours:
                        alternative_dates.append(str(check_date))
                        
                    check_date += timedelta(days=1)
                    days_checked += 1

                raise serializers.ValidationError({
                    'overload_conflict': [{
                        'status': 'error',
                        'resolved': False,
                        'message': f'Quedarías con {total_after_save:g}h planificadas (límite {limit_hours:g}h)',
                        'planned_hours': planned_hours,
                        'limit_hours': limit_hours,
                        'exceeds_by': exceeds_by,
                        'hours_to_reduce': exceeds_by,
                        'alternative_dates': alternative_dates
                    }]
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

    def validate(self, data):
        """Validar límites de sub-tareas creadas en lote junto a la actividad."""
        # --- Protección de Estados de Actividad ---
        status_val = data.get('status', getattr(self.instance, 'status', 'pending'))
        due_date = data.get('due_date', getattr(self.instance, 'due_date', None))
        
        if self.instance:
            old_status = self.instance.status
            # Si era 'overdue' y le asignan nueva fecha a futuro, pasa a 'postponed'
            if old_status == 'overdue' and status_val == 'overdue' and due_date and due_date >= date.today():
                data['status'] = 'postponed'
                status_val = 'postponed'
            elif status_val != old_status and status_val not in ['done', 'pending', 'postponed']:
                # El usuario sólo debería poder pasar a 'done' manualmente (o pending)
                pass
        else:
            # Creación nueva: no puede nacer ni done, ni postponed ni overdue
            if status_val not in ['pending', 'done']:
                data['status'] = 'pending'
                status_val = 'pending'

        # --- Validación: due_date no puede ser anterior al target_date de subtareas ---
        if self.instance and due_date:
            # Buscar subtareas cuyo target_date sea posterior al nuevo due_date
            conflicting_subtasks = self.instance.subtasks.filter(
                target_date__gt=due_date
            ).exclude(status='done')

            if conflicting_subtasks.exists():
                subtask_names = list(
                    conflicting_subtasks.values_list('title', flat=True)[:5]
                )
                names_str = ', '.join(f'"{name}"' for name in subtask_names)
                count = conflicting_subtasks.count()
                raise serializers.ValidationError({
                    'due_date': [
                        f'No puedes mover la fecha límite al {due_date} porque '
                        f'{count} subtarea(s) tienen fecha objetivo posterior: {names_str}. '
                        f'Reprograma esas subtareas primero.'
                    ]
                })

        # Solo correr validacion batch de subtasks si estamos creando (no hay id aún)
        if self.instance:
            return data

        subtasks_data = data.get('subtasks', [])
        if not subtasks_data:
            return data
            
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            return data
            
        user_id = request.user.user_id
        try:
            capacity_obj = DailyCapacity.objects.get(user__user_id=user_id)
            limit_hours = float(capacity_obj.daily_limit_hours)
        except DailyCapacity.DoesNotExist:
            limit_hours = 6.0

        # Agrupar las peticiones por fecha para saber si en este mimo envío intentan sobrecargar
        dates_hours = {}
        for st in subtasks_data:
            td = st.get('target_date')
            est = st.get('estimated_hours', 0.0)
            if td:
                dates_hours[td] = dates_hours.get(td, 0.0) + est
                
        # Verificar cada fecha contra la BD
        for target_date, added_hours in dates_hours.items():
            planned_hours = Subtask.objects.filter(
                activity__user_id=user_id,
                target_date=target_date
            ).exclude(status='done').aggregate(
                total=Sum('estimated_hours')
            )['total'] or 0.0
            
            total_after_save = planned_hours + added_hours
            if total_after_save > limit_hours:
                exceeds_by = total_after_save - limit_hours
                
                # Buscar 1 día alternativo
                from datetime import timedelta
                alternative_dates = []
                check_date = target_date + timedelta(days=1)
                days_checked = 0
                max_days_to_check = 30
                
                while len(alternative_dates) < 1 and days_checked < max_days_to_check:
                    # Verificar si check_date supera el due_date de la actividad
                    if due_date and check_date > due_date:
                        break # No buscar más allá de la fecha de entrega
                    
                    # Calcular horas planificadas en check_date
                    day_planned_hours = Subtask.objects.filter(
                        activity__user_id=user_id,
                        target_date=check_date
                    ).exclude(status='done').aggregate(
                        total=Sum('estimated_hours')
                    )['total'] or 0.0
                    
                    if (day_planned_hours + exceeds_by) <= limit_hours:
                        alternative_dates.append(str(check_date))
                        
                    check_date += timedelta(days=1)
                    days_checked += 1
                
                raise serializers.ValidationError({
                    'overload_conflict': [{
                        'status': 'error',
                        'resolved': False,
                        'message': f'La fecha {target_date} quedaría con {total_after_save:g}h (límite {limit_hours:g}h)',
                        'planned_hours': planned_hours,
                        'limit_hours': limit_hours,
                        'exceeds_by': exceeds_by,
                        'hours_to_reduce': exceeds_by,
                        'alternative_dates': alternative_dates
                    }]
                })
        return data

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
                  'target_date', 'estimated_hours', 'note', 'done_at',
                  'parent_activity']
        