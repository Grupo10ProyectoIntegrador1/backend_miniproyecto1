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