"""Access rules shared by the web views and the REST API."""
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser

from drinq.models import TreatmentPlant


def user_can_access_plant(
    user: AbstractBaseUser | AnonymousUser, plant: TreatmentPlant
) -> bool:
    """Return True for staff and for the owner of the plant's configuration.

    Args:
        user: The requesting user, possibly anonymous.
        plant: The treatment plant that is accessed.

    Returns:
        Whether the user may view and change the plant.
    """
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    configuration = plant.configuration
    return configuration is not None and configuration.user_id == user.pk
