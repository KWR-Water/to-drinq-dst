from django.test import TestCase
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from drinq.models import (
    TreatmentPlant,
    MultiStepConfiguration,
    DesignParameter,
    DesignTree,
    TreatmentplantDesignParameter,
    TreatmentplantProperty,
    TreatmentplantPropertyValue,
)
from drinq.serializers import (
    DesignParameterInputSerializer,
    TreatmentPlantPropertySerializer,
)


class ProcessDesignParametersAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.force_login(self.user)
        water_source = DesignTree.objects.create(
            name="Test Water Source",)
        self.config = MultiStepConfiguration.objects.create(
            name="Test Config", user=self.user, 
            water_source=water_source, session_key='abc123'
            )
        self.plant = TreatmentPlant.objects.create(
            name="Plant1",
            description="desc",
            option=1,
            configuration=self.config
        )
        self.population_persons, _ = DesignParameter.objects.get_or_create(name="population persons")  # noqa: E501
        self.avg_cons, _ = DesignParameter.objects.get_or_create(name="average consumption (lppd)")  # noqa: E501
        self.peak_demand_factor, _ = DesignParameter.objects.get_or_create(name="peak demand factor")  # noqa: E501
        self.largescale_cons, _ = DesignParameter.objects.get_or_create(name="large-scale consumption (m3/day)")  # noqa: E501
        self.leakage_factor, _ = DesignParameter.objects.get_or_create(name="leakage factor")  # noqa: E501
        self.nominal_flow, _ = TreatmentplantProperty.objects.get_or_create(
            name="Nominal flow (m3/hr)")
        self.client = APIClient()

    def test_design_parameter_input_serializer(self):
        data = {
            "treatmentplant_id": self.plant.id,
            "configuration_id": self.config.id,
            "parameters": {
                str(self.population_persons.id): 10000,  # population persons
                str(self.avg_cons.id): 120.5,
                str(self.peak_demand_factor.id): 1.5,
                str(self.largescale_cons.id): 500.0,
                str(self.leakage_factor.id): 0.2
            }
        }
        serializer = DesignParameterInputSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["treatmentplant_id"], self.plant.id)

    def test_api_process_parameters(self):
        url = "/api/process_parameters/"
        data = {
            "treatmentplant_id": self.plant.id,
            "configuration_id": self.config.id,
            "parameters": {
                str(self.population_persons.id): 10000,
                str(self.avg_cons.id): 120.5,
                str(self.peak_demand_factor.id): 1.5,
                str(self.largescale_cons.id): 2000.0,
                str(self.leakage_factor.id): 0.15
            },
            # "technologies": ["Technology1", "Technology2"],
            # "stages": ["Stage1", "Stage2"]
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn("property", response.data)
        self.assertIn("value", response.data)
        # Check that the property value is the sum of the parameters
        self.assertEqual(response.data["value"], "230.359375")

    def test_treatment_plant_property_serializer(self):
        prop_value = TreatmentplantPropertyValue.objects.create(
            treatmentplant=self.plant,
            property=self.nominal_flow,
            value="420"
        )
        serializer = TreatmentPlantPropertySerializer(prop_value)
        self.assertEqual(serializer.data["value"], "420")