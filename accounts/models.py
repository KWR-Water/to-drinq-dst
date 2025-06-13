# See: https://learndjango.com/tutorials/django-custom-user-model
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_save
from django.utils.translation import gettext as _
from django.dispatch import receiver


class CustomUser(AbstractUser):
    pass
    # add additional fields in here

    def __str__(self):
        return self.username


class UserProfile(models.Model):
    user = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.CASCADE,
    )
    watercompany = models.ForeignKey(
        "drinq.Watercompany", verbose_name=_("water company"),
        on_delete=models.CASCADE,
        blank=True,
        null=True)

    def __str__(self):
        return str(self.user)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
        db_table = "accounts_customuser_profile"


@receiver(post_save, sender=CustomUser)
def create_or_update_user_profile(sender, instance, created, **kwargs) -> None:
    UserProfile.objects.get_or_create(user=instance)