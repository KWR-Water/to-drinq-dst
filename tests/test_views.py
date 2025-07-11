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

# How to debug invalid forms:
# - After form.is_valid(), inspect form.errors to see which fields are invalid.
# - Make sure all required fields for the form/model are present in the POST data.
# - If a field is missing or has an invalid value, add or correct it in the test data.