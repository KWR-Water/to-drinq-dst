from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth.forms import AdminUserCreationForm
from users.models import CustomUser

# Code adopted from learndjango: https://learndjango.com/tutorials/django-custom-user-model


class CustomUserCreationForm(AdminUserCreationForm):

    class Meta:
        model = CustomUser
        fields = ("username", "email")


class CustomUserChangeForm(UserChangeForm):

    class Meta:
        model = CustomUser
        fields = ("username", "email")
