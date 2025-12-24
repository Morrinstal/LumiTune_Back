from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers 
from .models import Profile

User = get_user_model()

class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ("display_name", "date_of_birth", "country_code", "city", "role")

class RegisterSerializer(serializers.Serializer):
    # принимаем и email, и username (alias для email)
    email = serializers.EmailField(required=False)
    username = serializers.EmailField(required=False)
    password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        raw = (attrs.get("email") or attrs.get("username") or "").strip().lower()
        if not raw:
            raise serializers.ValidationError({"email": "Email is required"})
        if User.objects.filter(email=raw).exists():
            raise serializers.ValidationError({"email": "Email already exists"})
        attrs["email"] = raw
        return attrs

    def create(self, validated_data):
        email = validated_data["email"]
        password = validated_data["password"]
        user = User.objects.create_user(email=email, password=password, full_name="")
        Profile.objects.get_or_create(
            user=user,
            defaults={"display_name": email.split("@")[0]}
        )
        return user

class MeSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer()

    class Meta:
        model = User
        fields = ("id", "email", "full_name", "profile")

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()
        if profile_data is not None:
            Profile.objects.update_or_create(user=instance, defaults=profile_data)
        return instance
class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=8, write_only=True)   
class PasswordResetCodeConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(min_length=4, max_length=6)
    new_password = serializers.CharField(min_length=8, write_only=True)

    def to_internal_value(self, data):
        """
        Принимаем и new_password, и newPassword (с фронта часто приходит camelCase).
        """
        if "new_password" not in data and "newPassword" in data:
            # скопируем, чтобы не трогать исходный dict
            data = dict(data)
            data["new_password"] = data.pop("newPassword")
        return super().to_internal_value(data)
class PasswordResetCodeVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(min_length=4, max_length=6)   