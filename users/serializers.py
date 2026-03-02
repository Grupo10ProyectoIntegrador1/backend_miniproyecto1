from rest_framework import serializers
from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['user_id', 'uuid_user', 'name', 'last_name', 'streak_current', 'streak_last_day', 'streak_best']
        read_only_fields = ['user_id', 'streak_current', 'streak_last_day', 'streak_best']