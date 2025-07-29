from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drinq.models import (
    DesignParameter,
    TreatmentPlant,
    TreatmentplantDesignParameter,
    TreatmentplantProperty,
    TreatmentplantPropertyValue,
    TreatmentPlantLayout,
    Stage,
    StageTechnologies,
    )
from drinq.serializers import (
    DesignParameterInputSerializer,
    TreatmentPlantPropertySerializer,
)
from drinq.api_calculation import TreatmentPlantDesignCalculator


class ProcessDesignParametersAPI(APIView):
    """
    API endpoint to process design parameters for a TreatmentPlant.
    """

    def post(self, request, *args, **kwargs):
        serializer = DesignParameterInputSerializer(data=request.data)
        if serializer.is_valid():
            plant_id = serializer.validated_data['treatmentplant_id']
            config_id = serializer.validated_data['configuration_id']
            parameters = serializer.validated_data['parameters']

            try:
                plant = TreatmentPlant.objects.get(
                    id=plant_id,
                    configuration_id=config_id)
            except TreatmentPlant.DoesNotExist:
                return Response(
                    {'error': 'TreatmentPlant not found.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Save/update parameter values
            for param_id, value in parameters.items():
                TreatmentplantDesignParameter.objects.update_or_create(
                    treatmentplant=plant,
                    designparameter_id=param_id,
                    defaults={'value': value}
                )
            all_design_parameters = DesignParameter.objects.all()
            parameters_by_name = {
                all_design_parameters.get(id=par_id).name: value
                for par_id, value in parameters.items()
            }
            # Get the technologies for the treatment plant
            technologies = TreatmentPlantLayout.objects.filter(
                treatmentplant=plant)
            stage_technologies = StageTechnologies.objects.filter(
                technology__in=technologies.values_list(
                    'technology', flat=True)
            )            
            stage_names = [st.stage.name for st in stage_technologies]
            technology_names = [
                technology.technology.name for technology in technologies]
            
            # Calculate nominal flow and save it as a property
            plant_calculator = TreatmentPlantDesignCalculator(
                treatmentplant_id=plant.id,
                design_parameters=parameters_by_name,
                stages=stage_names,
                technologies=technology_names
            )
            nominal_flow = plant_calculator.calculate_nominal_flow_m3hr()
            prop, _ = TreatmentplantProperty.objects.get_or_create(
                name='nominal flow (m3/hr)')
            prop_value, _ = TreatmentplantPropertyValue.objects.update_or_create(
                treatmentplant=plant,
                property=prop,
                defaults={'value': str(nominal_flow)}
            )

            output_serializer = TreatmentPlantPropertySerializer(prop_value)
            return Response(output_serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)