import re
from rest_framework import serializers
from .models import User, DailyCapacity


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['user_id', 'uuid_user', 'name', 'last_name', 'streak_current', 'streak_last_day', 'streak_best']
        read_only_fields = ['user_id', 'streak_current', 'streak_last_day', 'streak_best']

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("El nombre no puede estar vacío.")
        if len(value) < 2:
            raise serializers.ValidationError("El nombre debe tener al menos 2 caracteres.")
        if len(value) > 50:
            raise serializers.ValidationError("El nombre no puede tener más de 50 caracteres.")
        if not re.match(r"^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s\-']+$", value):
            raise serializers.ValidationError("El nombre solo puede contener letras, espacios, guiones y apóstrofes.")
        return value

    def validate_last_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("El apellido no puede estar vacío.")
        if len(value) < 2:
            raise serializers.ValidationError("El apellido debe tener al menos 2 caracteres.")
        if len(value) > 50:
            raise serializers.ValidationError("El apellido no puede tener más de 50 caracteres.")
        if not re.match(r"^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s\-']+$", value):
            raise serializers.ValidationError("El apellido solo puede contener letras, espacios, guiones y apóstrofes.")
        return value


class DailyCapacitySerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyCapacity
        fields = ['daily_limit_hours']

    def validate_daily_limit_hours(self, value):
        if value < 1 or value > 16:
            raise serializers.ValidationError("El límite diario debe estar entre 1 y 16 horas.")
        return value

    def validate(self, data):
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            return data

        new_limit = data.get('daily_limit_hours')
        if new_limit is None:
            if self.instance:
                new_limit = self.instance.daily_limit_hours
            else:
                return data

        user_id = request.user.user_id
        
        from activities.models import Subtask
        from django.db.models import Sum
        from datetime import date

        today = date.today()

        # Encontrar fechas desde hoy con horas planificadas mayores al nuevo límite
        overloaded_dates = Subtask.objects.filter(
            activity__user_id=user_id,
            target_date__gte=today
        ).exclude(status='done').values('target_date').annotate(
            total_hours=Sum('estimated_hours')
        ).filter(total_hours__gt=new_limit)

        if overloaded_dates.exists():
            conflicts = []
            for item in overloaded_dates:
                conflicts.append({
                    'date': str(item['target_date']),
                    'planned_hours': float(item['total_hours']),
                    'limit_hours': float(new_limit),
                    'exceeds_by': float(item['total_hours']) - float(new_limit)
                })

            raise serializers.ValidationError({
                'overload_conflict': [{
                    'status': 'error',
                    'resolved': False,
                    'message': 'No puedes reducir tu capacidad porque tienes días planificados que superan este nuevo límite.',
                    'conflicts': conflicts
                }]
            })

        return data