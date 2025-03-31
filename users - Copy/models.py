from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

# from users.managers import CustomUserManager


class CustomUser(AbstractUser):
    # class Meta:
    #     db_table = 'auth_user'

    # username = None
    # email = models.EmailField(_('email address'), unique=True)

    # USERNAME_FIELD = 'email'
    # REQUIRED_FIELDS = []

    # objects = CustomUserManager()
    pass

    def __str__(self):
        return self.username
