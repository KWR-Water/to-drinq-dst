from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from drinq.models import MultiStepConfiguration, TreatmentPlant


class PlantPageAccessTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username='owner', password='secretpass')
        self.other = user_model.objects.create_user(
            username='other', password='secretpass')
        self.staff = user_model.objects.create_user(
            username='staff', password='secretpass', is_staff=True)
        configuration = MultiStepConfiguration.objects.create(
            user=self.owner, session_key='access-session', name='Config')
        self.plant = TreatmentPlant.objects.create(
            name='Plant', option=1, configuration=configuration)
        plant_kwargs = {'plant_id': self.plant.id}
        self.urls = {
            'design_parameter_input': reverse(
                'design_parameter_input', kwargs=plant_kwargs),
            'technology_properties': reverse(
                'technology_properties', kwargs=plant_kwargs),
            'design_parameter_results': reverse(
                'design_parameter_results', kwargs=plant_kwargs),
            'design_parameter_results_export_csv': reverse(
                'design_parameter_results_export_csv', kwargs=plant_kwargs),
            'adaptability_details': reverse(
                'adaptability_details', kwargs=plant_kwargs),
            'design_parameter_overview': reverse(
                'design_parameter_overview', kwargs=plant_kwargs),
            'technology_parameter_overview': reverse(
                'technology_parameter_overview', kwargs=plant_kwargs),
            'optimizer_status': reverse(
                'optimizer_status', kwargs=plant_kwargs),
            'design_detail': reverse(
                'design_detail', kwargs={'slug': self.plant.slug}),
            'edit_treatmentdesign': reverse(
                'edit_treatmentdesign', kwargs={'slug': self.plant.slug}),
        }

    def test_anonymous_user_is_redirected_to_login(self) -> None:
        for name, url in self.urls.items():
            with self.subTest(page=name):
                response = Client().get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith('/login/'))

    def test_other_user_gets_404(self) -> None:
        client = Client()
        client.force_login(self.other)
        for name, url in self.urls.items():
            with self.subTest(page=name):
                self.assertEqual(client.get(url).status_code, 404)

    def test_owner_can_open_pages(self) -> None:
        client = Client()
        client.force_login(self.owner)
        for name in (
            'design_parameter_input',
            'technology_properties',
            'design_parameter_results',
            'design_parameter_results_export_csv',
            'optimizer_status',
        ):
            with self.subTest(page=name):
                self.assertEqual(client.get(self.urls[name]).status_code, 200)

    def test_staff_can_open_pages_of_other_users(self) -> None:
        client = Client()
        client.force_login(self.staff)
        response = client.get(self.urls['design_parameter_results'])
        self.assertEqual(response.status_code, 200)

    def test_technology_overview_selection_requires_login(self) -> None:
        url = reverse('technology_parameter_overview_select')
        response = Client().get(url)
        self.assertEqual(response.status_code, 302)

    def test_configuration_pages_require_login(self) -> None:
        urls = [
            reverse('session_select'),
            reverse('form_complete', kwargs={'session_key': 'access-session'}),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = Client().get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith('/login/'))

    def test_plant_creation_requires_login(self) -> None:
        response = Client().post(reverse('name_treatmentdesign'), {})
        self.assertEqual(response.status_code, 302)

    def test_plant_creation_in_foreign_configuration_gets_404(self) -> None:
        client = Client()
        client.force_login(self.other)
        session = client.session
        session['treatment_maps'] = {'1': {1: {'technology': 1}}}
        session.save()
        response = client.post(
            reverse('name_treatmentdesign'),
            {
                'name': 'Intruder',
                'option_number': '1',
                'configuration': self.plant.configuration_id,
            },
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(TreatmentPlant.objects.filter(name='Intruder'))


class DesignParametersApiAccessTests(TestCase):
    url = '/api/process_parameters/'

    def setUp(self) -> None:
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username='owner', password='secretpass')
        self.other = user_model.objects.create_user(
            username='other', password='secretpass')
        self.configuration = MultiStepConfiguration.objects.create(
            user=self.owner, session_key='api-session', name='Config')
        self.plant = TreatmentPlant.objects.create(
            name='Plant', option=1, configuration=self.configuration)
        self.body = {
            'treatmentplant_id': self.plant.id,
            'configuration_id': self.configuration.id,
            'parameters': {},
        }

    def test_anonymous_request_is_rejected(self) -> None:
        response = APIClient().post(self.url, self.body, format='json')
        self.assertEqual(response.status_code, 401)

    def test_other_user_gets_404(self) -> None:
        client = APIClient()
        client.force_authenticate(self.other)
        response = client.post(self.url, self.body, format='json')
        self.assertEqual(response.status_code, 404)

    def test_owner_passes_the_access_check(self) -> None:
        client = APIClient(raise_request_exception=False)
        client.force_authenticate(self.owner)
        response = client.post(self.url, self.body, format='json')
        self.assertNotIn(response.status_code, (401, 403, 404))


class AccountApiAccessTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='user', email='user@example.org', password='secretpass')
        self.other = user_model.objects.create_user(
            username='other', email='other@example.org',
            password='secretpass')
        self.admin = user_model.objects.create_user(
            username='admin', password='secretpass', is_staff=True)
        self.new_user = {
            'username': 'newuser',
            'email': 'new@example.org',
            'password': 'a-long-secret-1',
        }

    def test_register_requires_authentication(self) -> None:
        response = APIClient().post(
            '/accounts/register/', self.new_user, format='json')
        self.assertEqual(response.status_code, 401)

    def test_register_forbidden_for_regular_user(self) -> None:
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.post(
            '/accounts/register/', self.new_user, format='json')
        self.assertEqual(response.status_code, 403)

    def test_register_allowed_for_admin(self) -> None:
        client = APIClient()
        client.force_authenticate(self.admin)
        response = client.post(
            '/accounts/register/', self.new_user, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            get_user_model().objects.filter(username='newuser').exists())

    def test_user_lookup_requires_authentication(self) -> None:
        response = APIClient().get(f'/accounts/users/{self.user.pk}/')
        self.assertEqual(response.status_code, 401)

    def test_user_can_read_only_self(self) -> None:
        client = APIClient()
        client.force_authenticate(self.user)
        own = client.get(f'/accounts/users/{self.user.pk}/')
        other = client.get(f'/accounts/users/{self.other.pk}/')
        self.assertEqual(own.status_code, 200)
        self.assertEqual(other.status_code, 404)

    def test_admin_can_read_any_user(self) -> None:
        client = APIClient()
        client.force_authenticate(self.admin)
        response = client.get(f'/accounts/users/{self.user.pk}/')
        self.assertEqual(response.status_code, 200)
