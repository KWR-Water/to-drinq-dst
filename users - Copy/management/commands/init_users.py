import warnings
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db.utils import IntegrityError, OperationalError

from django.core.management import BaseCommand
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Group, Permission

from users.models import CustomUser
from drinq import models as drinq_models

GROUPS_PERMISSIONS = {
    'todrinq owner': {
        # drinq_models.Compound: ['view'],
    },
}


class Command(BaseCommand):
    help = 'Fill the database with test data for demonstration and testing'

    def handle(self, *args, **options):

        self.initialize_groups()
        self.init_users()

    def init_users(self):
        try:
            try:
                owner_group = Group.objects.get(name='todrinq owner')
            except OperationalError:
                raise OperationalError('Did you forget to run init_groups?')
        except OperationalError:
            raise OperationalError('Did you forget to migrate?')
        try:
            owner = CustomUser.objects.create_user(
                password='JUE1cXe4cfsat0FfKu5d',
                email='compound_owner@test.nl',
                is_superuser=False)
            owner.groups.add(owner_group)
        except IntegrityError:
            pass
        try:
            dirk = CustomUser.objects.create_user(
                password='DUE1cXe4c09840FfKu5d',
                email='dirk.vries@kwrwater.nl',
                is_superuser=False)
        except IntegrityError:
            warnings.warn('IntegrityError when trying to create a dirk user')
            pass
        try:
            superuser = CustomUser.objects.create_superuser(
                password='a9B8?$73q.+=',
                email='super@user.nl',
                is_superuser=True)
        except IntegrityError:
            warnings.warn('IntegrityError when trying to create a superuser')
            pass

    def initialize_groups(self):
        ''' initialize groups in the database '''
        # Loop groups
        for group_name in GROUPS_PERMISSIONS:

            # Get or create group
            group, created = Group.objects.get_or_create(name=group_name)

            # Loop models in group
            for model_cls in GROUPS_PERMISSIONS[group_name]:

                # Loop permissions in group/model
                for _, perm_name in enumerate(GROUPS_PERMISSIONS[group_name][model_cls]):

                    # Generate permission name as Django would generate it
                    model_name = model_cls._meta.model_name
                    app_label = model_cls._meta.app_label
                    codename = perm_name + "_" + model_name
                    content_type = ContentType.objects.get(
                        app_label=app_label, model=model_name)

                    # Find permission object and add to group
                    perm = Permission.objects.get(
                        codename=codename, content_type=content_type)
                    group.permissions.add(perm)
