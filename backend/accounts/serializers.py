from django.contrib.auth import authenticate
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import User


def check_password_strength(password, user=None):
    try:
        validate_password(password, user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages))
    return password


class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(source="date_joined", read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "role", "created_at"]
        read_only_fields = fields

    def get_role(self, user):
        return "admin" if user.is_staff else "user"


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(
        min_length=3, max_length=150, validators=[UnicodeUsernameValidator()]
    )
    password = serializers.CharField(max_length=128, trim_whitespace=False)

    def validate_username(self, value):
        # create_user stores the NFKC form, so compare that one.
        value = User.normalize_username(value)
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("That username is already in use.")
        return value

    def validate(self, attrs):
        check_password_strength(attrs["password"], User(username=attrs["username"]))
        return attrs


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, trim_whitespace=False)

    def validate(self, attrs):
        # One message for unknown user and wrong password, so usernames can't be probed.
        # Usernames are unique case-insensitively, so match the stored spelling.
        submitted = User.normalize_username(attrs["username"])
        stored = (
            User.objects.filter(username__iexact=submitted).values_list("username", flat=True).first()
        )
        user = authenticate(
            self.context["request"], username=stored or submitted, password=attrs["password"]
        )
        if user is None:
            raise serializers.ValidationError("Invalid username or password.")
        return {"user": user}


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(max_length=128, trim_whitespace=False)
    new_password = serializers.CharField(max_length=128, trim_whitespace=False)

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value):
        return check_password_strength(value, self.context["request"].user)
