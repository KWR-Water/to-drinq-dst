from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from drinq.models import (
    TreatmentPlant,
    MultiStepConfiguration,
    DesignParameter,
    DesignTree,
    TreatmentPlantProperty,
    TreatmentPlantPropertyValue,
)
from drinq.serializers import (
    DesignParameterInputSerializer,
    TreatmentPlantPropertyValueSerializer,
)


class DigestingDesignParametersAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(
            username='testuser', password='testpass')
        self.client.force_login(self.user)
        water_source = DesignTree.objects.create(
            name="Test Water Source",)
        self.config = MultiStepConfiguration.objects.create(
            name="Test Config",
            user=self.user,
            water_source=water_source,
            session_key='abc123'
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
        self.nominal_flow, _ = TreatmentPlantProperty.objects.get_or_create(
            name="Nominal flow (m3/hr)")
        self.client = APIClient()

    def test_design_parameter_input_serializer(self):
        data = {
            "treatmentplant_id": self.plant.id,
            "configuration_id": self.config.id,
            "parameters": {
                str(self.population_persons.id): 10000,  # inhabitants
                str(self.avg_cons.id): 120.5,  # lppd
                str(self.peak_demand_factor.id): 1.5,  # peak demand factor
                str(self.largescale_cons.id): 2000.0,  # m3/day
                str(self.leakage_factor.id): 0.15  # leakage factor (0 to 1)
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
                str(self.population_persons.id): 10000,  # inhabitants
                str(self.avg_cons.id): 120.5,  # lppd
                str(self.peak_demand_factor.id): 1.5,  # peak demand factor
                str(self.largescale_cons.id): 2000.0,  # m3/day
                str(self.leakage_factor.id): 0.15  # leakage factor (0 to 1)
            },
            # "technologies": ["Technology1", "Technology2"],
            # "stages": ["Stage1", "Stage2"]
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 200)
        for property in response.data['properties']:
            self.assertIn("property", property)
            self.assertIn("value", property)
            performance_ind = property["property"]
            if performance_ind["name"].lower() == "nominal flow":
                self.assertEqual(property["value"], "230.359375")
                self.assertEqual(performance_ind["unit"], "m3/hr")

    def test_treatment_plant_property_serializer(self):
        prop_value = TreatmentPlantPropertyValue.objects.create(
            treatmentplant=self.plant,
            property=self.nominal_flow,
            value="420"
        )
        serializer = TreatmentPlantPropertyValueSerializer(prop_value)
        self.assertEqual(serializer.data["value"], "420")