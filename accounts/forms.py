# accounts/forms.py; see https://learndjango.com/tutorials/django-custom-user-model
from django.contrib.auth.forms import (
    UserChangeForm, UserCreationForm)
from django.contrib.auth.forms import AuthenticationForm
from django.forms import ModelForm
from betterforms.multiform import MultiModelForm
from accounts.models import CustomUser, UserProfile


class CustomUserCreationForm(UserCreationForm):

    class Meta:
        model = CustomUser
        fields = ("username", "email")


class CustomUserChangeForm(UserChangeForm):

    class Meta:
        model = CustomUser
        fields = ("username", "email")


class CustomUserAuthForm(AuthenticationForm):
    """
    A custom authentication form that works with your CustomUser.
    You can add or override fields/validation here if necessary.
    """
    # For example, you might want to add custom help text or widgets.
    class Meta:
        model = CustomUser
        fields = ('username', 'password')
        
    # def save(self, commit=True):
    #     """
    #     Save the form and return the user instance.
    #     """
    #     # user = super().save(commit=commit)
    #     # Add any additional logic here if needed
    #     pass


class CustomUserProfileForm(ModelForm):
    class Meta:
        # user = CustomUser
        model = UserProfile
        fields = ('watercompany',)

