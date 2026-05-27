from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from drinq.models import (
    MultiStepConfiguration,
    TreatmentPlant,
    Technology,
    TreatmentPlantProperty,
    TreatmentPlantPropertyValue,
)
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


class TreatmentPlantComparisonViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(
            username='compare-user',
            password='secretpass',
        )
        self.other_user = User.objects.create_user(
            username='compare-other-user',
            password='secretpass',
        )

        self.configuration = MultiStepConfiguration.objects.create(
            user=self.user,
            session_key='compare-session',
            name='Compare Config',
        )
        self.other_configuration = MultiStepConfiguration.objects.create(
            user=self.other_user,
            session_key='compare-other-session',
            name='Other Config',
        )

        self.plant_one = TreatmentPlant.objects.create(
            name='Plant Alpha',
            option=1,
            configuration=self.configuration,
        )
        self.plant_two = TreatmentPlant.objects.create(
            name='Plant Beta',
            option=2,
            configuration=self.configuration,
        )
        self.other_user_plant = TreatmentPlant.objects.create(
            name='Plant Hidden',
            option=1,
            configuration=self.other_configuration,
        )

        flow_property, _ = TreatmentPlantProperty.objects.get_or_create(
            name='nominal flow rate',
            defaults={'unit': 'm^3/h'},
        )
        co2_property, _ = TreatmentPlantProperty.objects.get_or_create(
            name='co2 equivalent emissions',
            defaults={'unit': 'kg/m^3'},
        )

        TreatmentPlantPropertyValue.objects.create(
            treatmentplant=self.plant_one,
            property=flow_property,
            value='100.0',
        )
        TreatmentPlantPropertyValue.objects.create(
            treatmentplant=self.plant_two,
            property=flow_property,
            value='120.0',
        )
        TreatmentPlantPropertyValue.objects.create(
            treatmentplant=self.plant_two,
            property=co2_property,
            value='0.12',
        )

        self.url = reverse('treatmentplant_compare')

    def test_requires_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_displays_comparison_values(self):
        self.client.force_login(self.user)
        response = self.client.get(
            self.url,
            {
                'left_plant': self.plant_one.id,
                'right_plant': self.plant_two.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Compare Treatment Plant KPIs')
        self.assertContains(response, 'nominal flow rate')
        self.assertContains(response, '100.0')
        self.assertContains(response, '120.0')
        self.assertContains(response, 'co2 equivalent emissions')
        self.assertContains(response, 'Category KPI Radar')

    def test_rejects_same_plant_selection(self):
        self.client.force_login(self.user)
        response = self.client.get(
            self.url,
            {
                'left_plant': self.plant_one.id,
                'right_plant': self.plant_one.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Please select two different treatment configurations.',
        )

    def test_hides_other_users_treatment_plants_from_selector(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.plant_one.name)
        self.assertContains(response, self.plant_two.name)
        self.assertNotContains(response, self.other_user_plant.name)


class TestDesignParameterResultsExportCsvView(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(
            username='csv-user',
            password='secretpass',
        )
        self.client.force_login(self.user)

        self.configuration = MultiStepConfiguration.objects.create(
            user=self.user,
            session_key='csv-session',
            name='CSV Config',
        )
        self.treatment_plant = TreatmentPlant.objects.create(
            name='CSV Plant',
            option=1,
            configuration=self.configuration,
        )

        flow_property, _ = TreatmentPlantProperty.objects.get_or_create(
            name='nominal flow rate',
            defaults={'unit': 'm^3/h'},
        )
        TreatmentPlantPropertyValue.objects.create(
            treatmentplant=self.treatment_plant,
            property=flow_property,
            value='100.0',
        )

        self.url = reverse(
            'design_parameter_results_export_csv',
            kwargs={'plant_id': self.treatment_plant.id},
        )

    def test_exports_csv_download(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertIn('nominal flow rate', response.content.decode('utf-8'))

# How to debug invalid forms:
# - After form.is_valid(), inspect form.errors to see which fields are invalid.
# - Make sure all required fields for the form/model are present in the POST data.
# - If a field is missing or has an invalid value, add or correct it in the test data.