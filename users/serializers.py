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
                exceeds_by = float(item['total_hours']) - float(new_limit)
                
                # Buscar hasta 3 d\u00edas alternativos para esta fecha con conflicto
                from datetime import timedelta
                alternative_dates = []
                # Comenzamos a buscar a partir del d\u00eda siguiente de la fecha en conflicto
                check_date = item['target_date'] + timedelta(days=1)
                days_checked = 0
                max_days_to_check = 30 # \u00daltimo recurso evitar bucles infinitos
                
                while len(alternative_dates) < 3 and days_checked < max_days_to_check:
                    # Aqu\u00ed no tenemos una \u00fanica actividad (sino una suma de varias subtareas ese d\u00eda)
                    # As\u00ed que ignoramos la validaci\u00f3n de due_date de la actividad individual, o el Frontend \n                    # tendr\u00e1 que lidiar con que al moverla le diga que supera el due date de x actividad.

                    # Horas planificadas en la posible fecha alternativa
                    day_planned_hours = Subtask.objects.filter(
                        activity__user_id=user_id,
                        target_date=check_date
                    ).exclude(status='done').aggregate(
                        total=Sum('estimated_hours')
                    )['total'] or 0.0
                    
                    if (day_planned_hours + exceeds_by) <= new_limit:
                        alternative_dates.append(str(check_date))
                        
                    check_date += timedelta(days=1)
                    days_checked += 1

                conflicts.append({
                    'date': str(item['target_date']),
                    'planned_hours': float(item['total_hours']),
                    'limit_hours': float(new_limit),
                    'exceeds_by': exceeds_by,
                    'hours_to_reduce': exceeds_by,
                    'alternative_dates': alternative_dates
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