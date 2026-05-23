from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from drinq.models import MultiStepConfiguration, TreatmentPlant, Technology
from drinq.forms import TreatmentDesignSelectionForm

# drinq/test_views.py


class NamedDesignUpdateViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.force_login(self.user)

        self.config = MultiStepConfiguration.objects.create(
            user=self.user,
            session_key='abc123',
            name='Test Config'
        )
        self.technology = Technology.objects.create(
            name='Tech1',
            description='desc'
        )
        self.treatment_plant = TreatmentPlant.objects.create(
            name='Plant1',
            description='desc',
            option='1',
            configuration=self.config
        )
        self.url = reverse(
            'edit_treatmentdesign', kwargs={'slug': self.treatment_plant.slug})

    def get_valid_post_data(self):
        # Adjust keys to match your form fields
        return {
            'name': 'Updated Plant',
            'description': 'Updated desc',
            'option': self.treatment_plant.option,
            'configuration': self.config.id,
            # 'slug': self.treatment_plant.slug,
            # Add any other required fields for the form
        }

    def test_post_valid_data(self):
        data = self.get_valid_post_data()
        response = self.client.post(self.url, data)
        self.treatment_plant.refresh_from_db()
        self.assertEqual(response.status_code, 302)  # Should redirect on success
        self.assertEqual(self.treatment_plant.name, 'Updated Plant')
        self.assertEqual(self.treatment_plant.description, 'Updated desc')

    def test_post_missing_required_field(self):
        data = self.get_valid_post_data()
        data.pop('name')  # Remove required field
        response = self.client.post(self.url, data)
        self.assertNotEqual(response.status_code, 302)
        # Check which fields are causing the error
        form = TreatmentDesignSelectionForm(data, instance=self.treatment_plant)
        form.is_valid()
        print("Form errors:", form.errors)
        self.assertIn('name', form.errors)

    def test_post_invalid_option_number(self):
        data = self.get_valid_post_data()
        data['option'] = ''  # Invalid
        response = self.client.post(self.url, data)
        self.assertNotEqual(response.status_code, 302)
        form = TreatmentDesignSelectionForm(data, instance=self.treatment_plant)
        form.is_valid()
        print("Form errors:", form.errors)
        self.assertIn('option', form.errors)


class ConfigurationManagementViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(
            username='manager', password='secretpass')
        self.client.force_login(self.user)

        self.configuration = MultiStepConfiguration.objects.create(
            user=self.user,
            session_key='session-management',
            name='Configuration To Manage'
        )
        self.option_one = TreatmentPlant.objects.create(
            name='Option One Plant',
            description='first option',
            option=1,
            configuration=self.configuration,
        )
        self.option_two = TreatmentPlant.objects.create(
            name='Option Two Plant',
            description='second option',
            option=2,
            configuration=self.configuration,
        )
        self.url = reverse('configuration_manage')

    def test_delete_specific_design_option(self):
        response = self.client.post(
            self.url,
            {
                'action': 'delete_option',
                'configuration_id': self.configuration.id,
                'treatment_plant_id': self.option_one.id,
            }
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            TreatmentPlant.objects.filter(id=self.option_one.id).exists())
        self.assertTrue(
            TreatmentPlant.objects.filter(id=self.option_two.id).exists())

    def test_delete_configuration_removes_all_options(self):
        response = self.client.post(
            self.url,
            {
                'action': 'delete_configuration',
                'configuration_id': self.configuration.id,
            }
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            MultiStepConfiguration.objects.filter(
                id=self.configuration.id).exists())
        self.assertFalse(
            TreatmentPlant.objects.filter(
                configuration_id=self.configuration.id).exists())


class ConfigurationUpdateViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(
            username='owner', password='secretpass')
        self.other_user = User.objects.create_user(
            username='other', password='otherpass')
        self.client.force_login(self.user)

        self.configuration = MultiStepConfiguration.objects.create(
            user=self.user,
            session_key='session-edit',
            name='Original name',
            description='Original description',
        )
        self.other_configuration = MultiStepConfiguration.objects.create(
            user=self.other_user,
            session_key='session-other',
            name='Other name',
            description='Other description',
        )

    def test_update_configuration_name_and_description(self):
        url = reverse(
            'configuration_edit',
            kwargs={'pk': self.configuration.id},
        )
        response = self.client.post(
            url,
            {
                'name': 'Updated name',
                'description': 'Updated description',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.configuration.refresh_from_db()
        self.assertEqual(self.configuration.name, 'Updated name')
        self.assertEqual(
            self.configuration.description,
            'Updated description',
        )
        self.assertContains(
            response,
            'Configuration details updated successfully.',
        )

    def test_cannot_edit_configuration_of_other_user(self):
        url = reverse(
            'configuration_edit',
            kwargs={'pk': self.other_configuration.id},
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

# How to debug invalid forms:
# - After form.is_valid(), inspect form.errors to see which fields are invalid.
# - Make sure all required fields for the form/model are present in the POST data.
# - If a field is missing or has an invalid value, add or correct it in the test data.