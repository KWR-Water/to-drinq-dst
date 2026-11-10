from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.test.client import RequestFactory
from django.http import HttpResponse
from unittest.mock import patch
from pathlib import Path
import json
import tempfile
from drinq.models import (
    MultiStepConfiguration,
    TreatmentPlant,
    Technology,
    TechnologyKPI,
    TechnologyProperty,
    TechnologyPropertyJunction,
    TreatmentPlantLayout,
    TreatmentPlantTechnologyPropertyValue,
    TreatmentPlantTechnologyKPIValue,
    TreatmentPlantProperty,
    TreatmentPlantPropertyValue,
    WaterqualityParameter,
    WaterqualityParameterTechnologyJunction,
    TreatmentPlantWaterQualityParameterValue,
)
from drinq.forms import TreatmentDesignSelectionForm
from drinq.views import QuestionsCompleteView, TechnologyPropertiesView

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
        self.assertContains(response, 'Compare treatment plant KPIs')
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

    def test_uses_shorter_selector_option_label_format(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Compare Config [1]: Plant Alpha')
        self.assertContains(response, 'Compare Config [2]: Plant Beta')
        self.assertNotContains(response, 'option 1')
        self.assertNotContains(response, 'configuration: Compare Config')

    def test_abbreviates_long_option_name_and_sets_full_tooltip(self):
        self.client.force_login(self.user)
        long_name = (
            'Plant name that is intentionally very long so it gets '
            'abbreviated in selector'
        )
        long_plant = TreatmentPlant.objects.create(
            name=long_name,
            option=3,
            configuration=self.configuration,
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Compare Config [3]: Plant name that is intentionally very long...'
        )
        self.assertContains(
            response,
            f'title="Compare Config [3]: {long_plant.name}"',
            html=False,
        )

    @override_settings(
        TREATMENT_PLANT_OPTION_NAME_DISPLAY_MAX_CHARS=20,
    )
    def test_respects_configurable_option_name_display_max_chars(self):
        self.client.force_login(self.user)
        long_name = 'Long option label for setting override behavior'
        TreatmentPlant.objects.create(
            name=long_name,
            option=4,
            configuration=self.configuration,
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Compare Config [4]: Long option label...')
        self.assertContains(
            response,
            f'title="Compare Config [4]: {long_name}"',
            html=False,
        )


class DesignParameterResultsViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(
            username='results-user',
            password='secretpass',
        )
        self.client.force_login(self.user)

        self.configuration = MultiStepConfiguration.objects.create(
            user=self.user,
            session_key='results-session',
            name='Results Config',
        )
        self.treatment_plant = TreatmentPlant.objects.create(
            name='Results Plant',
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

        self.first_technology = Technology.objects.create(
            name='Coagulation',
            description='First technology',
        )
        self.second_technology = Technology.objects.create(
            name='Filtration',
            description='Second technology',
        )
        self.first_kpi = TechnologyKPI.objects.create(
            name='Specific energy',
            description='Energy use per treated unit',
            unit='kWh/m^3',
        )
        self.second_kpi = TechnologyKPI.objects.create(
            name='Chemical dose',
            description='Chemical use per treated unit',
            unit='mg/L',
        )

        TreatmentPlantLayout.objects.create(
            treatmentplant=self.treatment_plant,
            step=1,
            technology=self.first_technology,
        )
        TreatmentPlantLayout.objects.create(
            treatmentplant=self.treatment_plant,
            step=2,
            technology=self.second_technology,
        )

        TreatmentPlantTechnologyKPIValue.objects.create(
            treatmentplant=self.treatment_plant,
            technology=self.first_technology,
            kpi=self.first_kpi,
            value=1.25,
        )
        TreatmentPlantTechnologyKPIValue.objects.create(
            treatmentplant=self.treatment_plant,
            technology=self.second_technology,
            kpi=self.second_kpi,
            value=0.75,
        )

        self.url = reverse(
            'design_parameter_results',
            kwargs={'plant_id': self.treatment_plant.id},
        )

    def test_renders_collapsible_technology_sections(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Treatment plant KPIs')
        self.assertContains(response, 'Treatment plant KPIs for plant Results Plant')
        self.assertContains(response, 'KPIs per Technology')
        self.assertContains(response, 'Expand all')
        self.assertContains(response, 'Collapse all')
        self.assertContains(response, 'Step 1: Coagulation')
        self.assertContains(response, 'Step 2: Filtration')
        self.assertContains(response, 'data-bs-toggle="collapse"', html=False)
        self.assertContains(
            response,
            'technology-kpi-collapse-1',
            html=False,
        )
        self.assertContains(
            response,
            'technology-kpi-collapse-2',
            html=False,
        )


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


class QuestionsCompleteViewDispatchTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        User = get_user_model()
        self.user = User.objects.create_user(
            username='dispatch-user',
            password='secretpass',
        )

        self.initial_configuration = MultiStepConfiguration.objects.create(
            user=self.user,
            session_key='dispatch-initial-session',
            name='Initial configuration',
        )
        self.selected_configuration = MultiStepConfiguration.objects.create(
            user=self.user,
            session_key='dispatch-selected-session',
            name='Selected configuration',
        )

    def _build_request(self):
        request = self.factory.get(
            reverse(
                'form_complete',
                kwargs={'session_key': self.selected_configuration.session_key},
            )
        )
        request.user = self.user

        middleware = SessionMiddleware(lambda _request: None)
        middleware.process_request(request)
        request.session.save()
        request.session['configuration_id'] = self.initial_configuration.id

        return request

    @patch.object(QuestionsCompleteView, 'get')
    def test_dispatch_updates_configuration_id_for_selected_session_key(
            self,
            mock_get):
        mock_get.return_value = HttpResponse('ok')
        request = self._build_request()

        response = QuestionsCompleteView.as_view()(
            request,
            session_key=self.selected_configuration.session_key,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            request.session['configuration_id'],
            self.selected_configuration.id,
        )

    @patch.object(QuestionsCompleteView, 'get')
    def test_dispatch_uses_authenticated_user_for_session_key_lookup(
            self,
            mock_get):
        User = get_user_model()
        other_user = User.objects.create_user(
            username='dispatch-other-user',
            password='secretpass',
        )
        MultiStepConfiguration.objects.create(
            user=other_user,
            session_key=self.selected_configuration.session_key,
            name='Other user configuration',
        )

        mock_get.return_value = HttpResponse('ok')
        request = self._build_request()

        response = QuestionsCompleteView.as_view()(
            request,
            session_key=self.selected_configuration.session_key,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            request.session['configuration_id'],
            self.selected_configuration.id,
        )


class TechnologyPropertiesOptimizeTests(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(
            username='optimize-user',
            password='secretpass',
        )
        self.client.force_login(self.user)

        self.configuration = MultiStepConfiguration.objects.create(
            user=self.user,
            session_key='optimize-session',
            name='Optimize Config',
        )
        self.treatment_plant = TreatmentPlant.objects.create(
            name='Optimize Plant',
            option=1,
            configuration=self.configuration,
        )
        self.technology = Technology.objects.create(
            name='Chlorination contactor',
            description='Optimization test technology',
        )
        TreatmentPlantLayout.objects.create(
            treatmentplant=self.treatment_plant,
            technology=self.technology,
            step=1,
        )
        self.property = TechnologyProperty.objects.create(
            name='residence_time_hours',
            description='Residence time used for optimization',
            unit='h',
        )
        self.property_junction = TechnologyPropertyJunction.objects.create(
            technology=self.technology,
            property=self.property,
            default_value=4.0,
            is_designparameter=True,
            is_digested=False,
            sent_to_optimizer=True,
        )
        self.url = reverse(
            'technology_properties',
            kwargs={'plant_id': self.treatment_plant.id},
        )

        self.chlorine_dose_property = TechnologyProperty.objects.create(
            name='chlorination chemical dose',
            description='Dose from optimizer output',
            unit='mg/L',
        )
        self.volume_property = TechnologyProperty.objects.create(
            name='chlorination volume',
            description='Volume from optimizer output',
            unit='m3',
        )

    def test_shows_optimize_button_when_optimizer_flags_exist(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Optimize conditions')

    def test_renders_collapsible_technology_sections(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Expand all')
        self.assertContains(response, 'Collapse all')
        self.assertContains(response, 'Step 1 — Chlorination contactor')
        self.assertContains(
            response,
            'technology-properties-collapse-1',
            html=False,
        )

    def test_optimizer_managed_value_remains_editable(self):
        response = self.client.get(self.url)

        formset = response.context['formset']
        matching_form = next(
            form for form in formset.forms
            if getattr(form.instance, 'technologyproperty_id', None) == self.property.id
        )

        self.assertFalse(matching_form.fields['value'].disabled)
        self.assertIn('optimizer-managed-input', matching_form.fields['value'].widget.attrs.get('class', ''))

    def test_hides_optimize_button_without_optimizer_flags(self):
        self.property_junction.sent_to_optimizer = False
        self.property_junction.save(update_fields=['sent_to_optimizer'])

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Optimize conditions')

    def test_optimize_action_exports_optimizer_json(self):
        self.client.get(self.url)
        value_row = TreatmentPlantTechnologyPropertyValue.objects.get(
            treatmentplant=self.treatment_plant,
            technology=self.technology,
            technologyproperty=self.property,
        )
        post_data = {
            'action': 'optimize',
            'techprop-TOTAL_FORMS': '1',
            'techprop-INITIAL_FORMS': '1',
            'techprop-MIN_NUM_FORMS': '0',
            'techprop-MAX_NUM_FORMS': '1000',
            'techprop-0-id': str(value_row.id),
            'techprop-0-technology': str(self.technology.id),
            'techprop-0-technologyproperty': str(self.property.id),
            'techprop-0-value': '8.5',
            'waterquality-TOTAL_FORMS': '0',
            'waterquality-INITIAL_FORMS': '0',
            'waterquality-MIN_NUM_FORMS': '0',
            'waterquality-MAX_NUM_FORMS': '1000',
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            with override_settings(
                BASE_DIR=Path(tmp_dir),
                OPTIMIZER_ASYNC=False,
            ):
                mock_run_dir = (
                    Path(tmp_dir)
                    / 'research'
                    / 'pystimela_optim'
                    / 'outputs'
                    / 'mock_run'
                )
                mock_run_dir.mkdir(parents=True, exist_ok=True)
                with patch.object(
                    TechnologyPropertiesView,
                    '_run_optimizer_pipeline',
                    return_value=mock_run_dir,
                ) as run_mock, patch.object(
                    TechnologyPropertiesView,
                    '_export_optimizer_results_to_processed',
                    return_value=(
                        Path(tmp_dir)
                        / 'research'
                        / 'data'
                        / 'processed'
                        / 'optimizer_runs'
                        / 'mock'
                    ),
                ) as export_mock:
                    response = self.client.post(self.url, data=post_data)

                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, self.url)
                run_mock.assert_called_once()
                export_mock.assert_called_once()

                output_file = (
                    Path(tmp_dir)
                    / 'research'
                    / 'data'
                    / 'processed'
                    / 'optimizer_inputs'
                    / (
                        f'treatmentplant_{self.treatment_plant.id}'
                        '_optimization_input.json'
                    )
                )
                self.assertTrue(output_file.exists())

                payload = json.loads(output_file.read_text(encoding='utf-8'))
                self.assertEqual(
                    payload['treatment_plant']['id'],
                    self.treatment_plant.id,
                )
                self.assertEqual(len(payload['technology_properties']), 1)
                self.assertEqual(
                    payload['technology_properties'][0][
                        'technologyproperty_name'
                    ],
                    self.property.name,
                )
                self.assertEqual(
                    payload['technology_properties'][0]['value'],
                    8.5,
                )
                self.assertEqual(payload['waterquality_parameters'], [])

                optimizer_workspace = (
                    Path(tmp_dir)
                    / 'research'
                    / 'pystimela_optim'
                )
                enabled_path = (
                    optimizer_workspace
                    / 'outputs'
                    / 'enabled_processes.json'
                )
                self.assertTrue(enabled_path.exists())
                enabled_data = json.loads(enabled_path.read_text(encoding='utf-8'))
                self.assertIn('chlorination', enabled_data.get('enabled', []))

                chlorination_csv = (
                    optimizer_workspace
                    / 'inputs'
                    / 'config_chlorination.csv'
                )
                self.assertTrue(chlorination_csv.exists())
                csv_rows = chlorination_csv.read_text(
                    encoding='utf-8'
                ).splitlines()
                self.assertTrue(csv_rows[0].startswith('section,parameter,value'))
                self.assertTrue(
                    any(
                        'decision_variables,use_auto_bounds,True' in row
                        for row in csv_rows
                    )
                )

                in_wq_json = (
                    optimizer_workspace
                    / 'configs'
                    / 'in_wq_params.json'
                )
                self.assertTrue(in_wq_json.exists())

    def test_optimize_action_persists_optimizer_output_to_db(self):
        self.client.get(self.url)
        value_row = TreatmentPlantTechnologyPropertyValue.objects.get(
            treatmentplant=self.treatment_plant,
            technology=self.technology,
            technologyproperty=self.property,
        )
        post_data = {
            'action': 'optimize',
            'techprop-TOTAL_FORMS': '1',
            'techprop-INITIAL_FORMS': '1',
            'techprop-MIN_NUM_FORMS': '0',
            'techprop-MAX_NUM_FORMS': '1000',
            'techprop-0-id': str(value_row.id),
            'techprop-0-technology': str(self.technology.id),
            'techprop-0-technologyproperty': str(self.property.id),
            'techprop-0-value': '8.5',
            'waterquality-TOTAL_FORMS': '0',
            'waterquality-INITIAL_FORMS': '0',
            'waterquality-MIN_NUM_FORMS': '0',
            'waterquality-MAX_NUM_FORMS': '1000',
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            with override_settings(
                BASE_DIR=Path(tmp_dir),
                OPTIMIZER_ASYNC=False,
            ):
                mock_run_dir = (
                    Path(tmp_dir)
                    / 'research'
                    / 'pystimela_optim'
                    / 'outputs'
                    / 'mock_run'
                )
                mock_run_dir.mkdir(parents=True, exist_ok=True)
                result_payload = {
                    'success': True,
                    'optimal variables': {
                        'chlorine_dose_mgL': 2.25,
                        'volume_m3': 14.0,
                    },
                }
                (mock_run_dir / 'chlorination_results.json').write_text(
                    json.dumps(result_payload),
                    encoding='utf-8',
                )

                with patch.object(
                    TechnologyPropertiesView,
                    '_run_optimizer_pipeline',
                    return_value=mock_run_dir,
                ), patch.object(
                    TechnologyPropertiesView,
                    '_export_optimizer_results_to_processed',
                    return_value=(
                        Path(tmp_dir)
                        / 'research'
                        / 'data'
                        / 'processed'
                        / 'optimizer_runs'
                        / 'mock'
                    ),
                ):
                    response = self.client.post(self.url, data=post_data)

                self.assertEqual(response.status_code, 302)

                dose_value = TreatmentPlantTechnologyPropertyValue.objects.get(
                    treatmentplant=self.treatment_plant,
                    technology=self.technology,
                    technologyproperty=self.chlorine_dose_property,
                )
                self.assertEqual(dose_value.value, 2.25)

                volume_value = TreatmentPlantTechnologyPropertyValue.objects.get(
                    treatmentplant=self.treatment_plant,
                    technology=self.technology,
                    technologyproperty=self.volume_property,
                )
                self.assertEqual(volume_value.value, 14.0)

    def test_write_optimizer_inputs_uses_tss_alias_and_nominal_flow(self):
        flow_property, _ = TreatmentPlantProperty.objects.get_or_create(
            name='nominal flow rate',
            defaults={'unit': 'm3/h'},
        )
        TreatmentPlantPropertyValue.objects.update_or_create(
            treatmentplant=self.treatment_plant,
            property=flow_property,
            defaults={'value': 321.0},
        )

        filtration_technology = Technology.objects.create(
            name='Rapid Sand Filtration - Single',
            description='Filtration technology for optimizer input test',
        )
        tss_parameter = WaterqualityParameter.objects.create(
            name='TSS',
            description='Suspended solids',
            unit='mg/L',
        )
        tss_junction = WaterqualityParameterTechnologyJunction.objects.create(
            technology=filtration_technology,
            waterqualityparameter=tss_parameter,
            is_inputparameter=True,
            is_targetparameter=False,
            sent_to_optimizer=True,
            default_value=5.0,
        )
        TreatmentPlantWaterQualityParameterValue.objects.create(
            treatmentplant=self.treatment_plant,
            wq_tech_parameter=tss_junction,
            value=15.0,
        )

        payload = {
            'treatment_plant': {
                'id': self.treatment_plant.id,
                'name': self.treatment_plant.name,
                'slug': self.treatment_plant.slug,
            },
            'generated_at': '2026-06-25T00:00:00+00:00',
            'technology_properties': [],
            'waterquality_parameters': [
                {
                    'junction_id': tss_junction.id,
                    'technology_id': filtration_technology.id,
                    'technology_name': filtration_technology.name,
                    'waterqualityparameter_id': tss_parameter.id,
                    'waterqualityparameter_name': tss_parameter.name,
                    'unit': tss_parameter.unit,
                    'is_inputparameter': True,
                    'is_targetparameter': False,
                    'value': 15.0,
                    'source_table': 'waterqualityparameter_technology',
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            with override_settings(BASE_DIR=Path(tmp_dir)):
                view = TechnologyPropertiesView()
                view._write_optimizer_csv_inputs(
                    treatment_plant=self.treatment_plant,
                    payload=payload,
                )

                in_wq_path = (
                    Path(tmp_dir)
                    / 'research'
                    / 'pystimela_optim'
                    / 'configs'
                    / 'in_wq_params.json'
                )
                self.assertTrue(in_wq_path.exists())
                in_wq_data = json.loads(in_wq_path.read_text(encoding='utf-8'))
                wq_parameters = in_wq_data['WQ_parameters']

                self.assertEqual(
                    wq_parameters['suspended_solids']['value'],
                    15.0,
                )
                self.assertEqual(
                    wq_parameters['flow']['value'],
                    321.0,
                )

    def test_write_optimizer_inputs_maps_additional_django_outputs(self):
        payload = {
            'treatment_plant': {
                'id': self.treatment_plant.id,
                'name': self.treatment_plant.name,
                'slug': self.treatment_plant.slug,
            },
            'generated_at': '2026-06-25T00:00:00+00:00',
            'technology_properties': [
                {
                    'technology_name': 'Rapid Sand Filtration Double Medium',
                    'technologyproperty_name': 'filtration surface',
                    'value': 22.0,
                },
                {
                    'technology_name': 'Rapid Sand Filtration Double Medium',
                    'technologyproperty_name': 'filtration depth',
                    'value': 1.5,
                },
                {
                    'technology_name': 'Rapid Sand Filtration Double Medium',
                    'technologyproperty_name': 'filtration depth b',
                    'value': 1.2,
                },
                {
                    'technology_name': 'Rapid Sand Filtration Double Medium',
                    'technologyproperty_name': 'grain size a',
                    'value': 0.9,
                },
                {
                    'technology_name': 'Rapid Sand Filtration Double Medium',
                    'technologyproperty_name': 'grain size b',
                    'value': 1.1,
                },
                {
                    'technology_name': 'Coagulation dynamic mixing',
                    'technologyproperty_name': 'coagulation volume',
                    'value': 55.0,
                },
                {
                    'technology_name': 'Coagulation dynamic mixing',
                    'technologyproperty_name': 'coagulant dose',
                    'value': 0.2,
                },
                {
                    'technology_name': 'Flocculation dynamic mixing',
                    'technologyproperty_name': 'flocculation surface',
                    'value': 35.0,
                },
                {
                    'technology_name': 'Flocculation dynamic mixing',
                    'technologyproperty_name': 'flocculation length',
                    'value': 8.0,
                },
                {
                    'technology_name': 'Baffled ozonation contactor',
                    'technologyproperty_name': 'ozonation area',
                    'value': 14.0,
                },
                {
                    'technology_name': 'Baffled ozonation contactor',
                    'technologyproperty_name': 'ozonation height',
                    'value': 4.5,
                },
                {
                    'technology_name': 'Baffled ozonation contactor',
                    'technologyproperty_name': 'ozonation chemical dose',
                    'value': 2.3,
                },
            ],
            'waterquality_parameters': [],
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            with override_settings(BASE_DIR=Path(tmp_dir)):
                view = TechnologyPropertiesView()
                view._write_optimizer_csv_inputs(
                    treatment_plant=self.treatment_plant,
                    payload=payload,
                )

                outputs_path = (
                    Path(tmp_dir)
                    / 'research'
                    / 'pystimela_optim'
                    / 'configs'
                    / 'django_outputs.json'
                )
                self.assertTrue(outputs_path.exists())
                outputs_payload = json.loads(
                    outputs_path.read_text(encoding='utf-8')
                )
                outputs = outputs_payload['Process_outputs']

                self.assertEqual(outputs['dual_filtration_surface']['value'], 22.0)
                self.assertEqual(outputs['dual_filtration_depth']['value'], 1.5)
                self.assertEqual(outputs['dual_filtration_depth_b']['value'], 1.2)
                self.assertEqual(
                    outputs['dual_filtration_grain_size_a']['value'],
                    0.9,
                )
                self.assertEqual(
                    outputs['dual_filtration_grain_size_b']['value'],
                    1.1,
                )
                self.assertEqual(outputs['coagulation_volume']['value'], 55.0)
                self.assertEqual(
                    outputs['coagulation_chemical_dose']['value'],
                    0.2,
                )
                self.assertEqual(outputs['flocculation_surface']['value'], 35.0)
                self.assertEqual(outputs['flocculation_length']['value'], 8.0)
                self.assertEqual(outputs['ozonation_area']['value'], 14.0)
                self.assertEqual(outputs['ozonation_height']['value'], 4.5)
                self.assertEqual(
                    outputs['ozonation_chemical_dose']['value'],
                    2.3,
                )

    def test_optimize_action_writes_complete_wq_defaults(self):
        self.client.get(self.url)
        value_row = TreatmentPlantTechnologyPropertyValue.objects.get(
            treatmentplant=self.treatment_plant,
            technology=self.technology,
            technologyproperty=self.property,
        )
        post_data = {
            'action': 'optimize',
            'techprop-TOTAL_FORMS': '1',
            'techprop-INITIAL_FORMS': '1',
            'techprop-MIN_NUM_FORMS': '0',
            'techprop-MAX_NUM_FORMS': '1000',
            'techprop-0-id': str(value_row.id),
            'techprop-0-technology': str(self.technology.id),
            'techprop-0-technologyproperty': str(self.property.id),
            'techprop-0-value': '8.5',
            'waterquality-TOTAL_FORMS': '0',
            'waterquality-INITIAL_FORMS': '0',
            'waterquality-MIN_NUM_FORMS': '0',
            'waterquality-MAX_NUM_FORMS': '1000',
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            with override_settings(
                BASE_DIR=Path(tmp_dir),
                OPTIMIZER_ASYNC=False,
            ):
                mock_run_dir = (
                    Path(tmp_dir)
                    / 'research'
                    / 'pystimela_optim'
                    / 'outputs'
                    / 'mock_run'
                )
                mock_run_dir.mkdir(parents=True, exist_ok=True)

                with patch.object(
                    TechnologyPropertiesView,
                    '_run_optimizer_pipeline',
                    return_value=mock_run_dir,
                ), patch.object(
                    TechnologyPropertiesView,
                    '_export_optimizer_results_to_processed',
                    return_value=(
                        Path(tmp_dir)
                        / 'research'
                        / 'data'
                        / 'processed'
                        / 'optimizer_runs'
                        / 'mock'
                    ),
                ):
                    response = self.client.post(self.url, data=post_data)

                self.assertEqual(response.status_code, 302)

                in_wq_json = (
                    Path(tmp_dir)
                    / 'research'
                    / 'pystimela_optim'
                    / 'configs'
                    / 'in_wq_params.json'
                )
                payload = json.loads(in_wq_json.read_text(encoding='utf-8'))
                self.assertIn('WQ_parameters', payload)
                self.assertIn('wq_parameters', payload)

                required_keys = {
                    'flow',
                    'temperature',
                    'DOC',
                    'ammonia',
                    'pH',
                    'uv254',
                    'bromide',
                    'suspended_solids',
                    'conductivity',
                    'm-number',
                    'bromate',
                    'ecoli',
                    'AOC',
                }
                self.assertTrue(
                    required_keys.issubset(
                        set(payload['WQ_parameters'].keys())
                    )
                )

    def test_shows_optimizer_running_notice(self):
        with patch.object(
            TechnologyPropertiesView,
            '_get_optimizer_status',
            return_value={
                'state': 'running',
                'message': 'Optimization is running.',
                'updated_rows': [],
            },
        ):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Optimization is in progress. Updated results may take a while.',
        )

    def test_shows_results_button_when_optimizer_is_done(self):
        with patch.object(
            TechnologyPropertiesView,
            '_get_optimizer_status',
            return_value={
                'state': 'done',
                'message': 'Optimization completed.',
                'updated_rows': [
                    {
                        'technology_id': self.technology.id,
                        'row_type': 'property',
                        'name': self.property.name,
                        'value': 4.0,
                        'unit': self.property.unit,
                    },
                ],
            },
        ):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Optimization completed.')
        self.assertContains(response, 'btn btn-primary mt-2')
        self.assertContains(
            response,
            'View Treatment plant KPI results',
        )

# How to debug invalid forms:
# - After form.is_valid(), inspect form.errors to see which fields are invalid.
# - Make sure all required fields for the form/model are present in the POST data.
# - If a field is missing or has an invalid value, add or correct it in the test data.