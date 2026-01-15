from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import QuerySet
from django.urls import reverse
from drinq.models import (
    DesignParameter,
    TreatmentPlant,
    TreatmentplantDesignParameter,
    TreatmentPlantProperty,
    TreatmentPlantPropertyValue,
    TreatmentPlantLayout,
    Technology,
    TechnologyProperty,
    TechnologyPropertyJunction,
    TechnologyConstructionCostParameter,
    TreatmentPlantTechnologyPropertyValue,
    ParameterCategory,
    Stage,
    StageTechnologies,
    )
from drinq.serializers import (
    DesignParameterInputSerializer,
    TreatmentPlantPropertyValueSerializer,
)
from drinq.api_calculation import TreatmentPlantPerformanceCalculator

PLANT_PROPERTIES_TO_CALCULATE = [
    'nominal flow rate (m3/hr)',
    'construction costs',
    # Add more properties as needed
]


def get_stage_names(
    treatmentplant: TreatmentPlant,
    technologies: QuerySet[TreatmentPlantLayout] | None = None,
) -> list[str]:
    """
    Get the names of stages associated with the treatment plant.
    """
    if technologies is None:
        technologies = TreatmentPlantLayout.objects.filter(
            treatmentplant=treatmentplant)
    stage_technologies = StageTechnologies.objects.filter(
        technology__in=technologies.values_list('technology', flat=True)
    )
    return [st.stage.name for st in stage_technologies]


def get_technology_names(
    treatmentplant: TreatmentPlant,
    technologies: QuerySet[TreatmentPlantLayout] | None = None,
) -> tuple[list[str], dict[str, TreatmentPlantLayout]]:

    technologyname_list: list[str] = []
    technologyname_dict: dict[str, TreatmentPlantLayout] = {}
    if technologies is None:
        technologies = TreatmentPlantLayout.objects.filter(
            treatmentplant=treatmentplant)
    technologyname_list = [
        technology.technology.name for technology in technologies
    ]
    technologyname_dict = {
        technology.technology.name: technology for technology in technologies
    }
    return technologyname_list, technologyname_dict


def get_technology_properties(
    treatmentplant: TreatmentPlant,
    technologies: QuerySet[TreatmentPlantLayout] | None = None,
):
    """
    Calculate and return technology properties for the treatment plant.
    """
    if technologies is None:
        technologies = TreatmentPlantLayout.objects.filter(
            treatmentplant=treatmentplant)
    technology_names, technology_dict = get_technology_names(
        treatmentplant, technologies)
    technology_properties = {tech_name: {} for tech_name in technology_names}
    for name, tech in technology_dict.items():
        tech_properties = TechnologyPropertyJunction.objects.filter(
            technology=tech.technology)
        for prop in tech_properties:
            parent_prop = TechnologyProperty.objects.get(
                id=prop.property.id).parent_property
            prop_name, default_value = None, None
            if parent_prop:
                child_properties = parent_prop.child_properties.all()
                for child_prop in child_properties:
                    child_default = TechnologyPropertyJunction.objects.filter(
                        technology=tech.technology,
                        property=child_prop).first()
                    if child_default:
                        prop_name = child_prop.name
                        default_value = child_default.defaultvalue
                    else:
                        prop_name = child_prop.name
                        default_value = 0
                        # TODO: decide whether to raise an error or set to 0
            prop_default = TechnologyPropertyJunction.objects.filter(
                technology=tech.technology,
                property=prop.property).first()
            if prop_default:
                default_value = prop_default.defaultvalue
                prop_name = prop.property.name
            else:
                raise prop_default.DoesNotExist(
                    f"No default value for property {prop.property.name} "
                    f"and technology {tech.technology.name}"
                )
            technology_properties[name].update(
                {
                    prop_name: {
                                'default_value': default_value,
                                'value': None
                                },
                    })
    return technology_properties


def query_technology_constrcost_parameters(
    technology: Technology,
):
    """
    Get the construction cost parameters for a technology in the treatment plant.
    """
    technology_costs = TechnologyConstructionCostParameter.objects.get(
        technology=technology
        )
    return technology_costs


def get_constrcost_parameters(
    technology_list: list[int]
) -> dict[str, dict]:
    """
    Get the construction cost parameters for a list of technologies.
    """
    cost_parameters = {}
    for technology_id in technology_list:
        technology = Technology.objects.get(id=technology_id)
        tech_name = technology.name
        plantproperty_name, technologyproperty_name = None, None
        a, b, c = 0, 0, 0
        plantproperty_value, technologyproperty_value = None, None
        try:
            cost_par_result = query_technology_constrcost_parameters(technology)  # noqa E501
            a, b, c = cost_par_result.a, cost_par_result.b, cost_par_result.c
        except TechnologyConstructionCostParameter.DoesNotExist:
            Warning(
                f"No cost parameters found for technology {technology.name}"
            )
            continue
        if cost_par_result.plantproperty:
            plantproperty_name = TreatmentPlantProperty.objects.get(
                id=cost_par_result.plantproperty.pk).name
            plantproperty_value = TreatmentPlantPropertyValue.objects.filter(
                property=cost_par_result.plantproperty).first()
        if cost_par_result.technologyproperty:
            technologyproperty_name = TechnologyProperty.objects.get(
                id=cost_par_result.technologyproperty.pk).name
            technologyproperty_value = TreatmentPlantTechnologyPropertyValue.objects.filter(  # noqa, E501
                technologyproperty=cost_par_result.technologyproperty).first()
            # TODO: for technology properties, a separate form should be created  # noqa, E501
        cost_parameters[tech_name] = {
            'a': a,
            'b': b,
            'c': c,
            'plantproperty': plantproperty_name,
            'technologyproperty': technologyproperty_name,
            'plantproperty_value': plantproperty_value,
            'technologyproperty_value': technologyproperty_value
        }
    return cost_parameters


class DigestDesignParametersAPI(APIView):
    """
    API endpoint to digest design parameters for a TreatmentPlant.
    """
    def post(self, request, *args, **kwargs):
        serializer = DesignParameterInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)  # noqa E501

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

        # Persist design parameter values
        for param_id_str, item_val in parameters.items():
            # allow keys as strings or ints
            try:
                param_id = int(param_id_str)
            except (TypeError, ValueError):
                param_id = param_id_str
                continue
            TreatmentplantDesignParameter.objects.update_or_create(
                treatmentplant=plant,
                designparameter_id=param_id,
                defaults={'value': item_val}
            )

        # Check for technology-level design parameters that must be
        # provided before instantiating the performance calculator.
        technologies = TreatmentPlantLayout.objects.filter(
            treatmentplant=plant)

        # Find technology properties that are marked as design parameters
        techprop_defaults = TechnologyPropertyJunction.objects.filter(
            technology__in=technologies.values_list('technology', flat=True),
            is_designparameter=1,
        ).select_related('property', 'technology')

        required_tech_props = []
        for tp in techprop_defaults:
            existing_val = TreatmentPlantTechnologyPropertyValue.objects.filter(
                treatmentplant=plant,
                technology=tp.technology,
                technologyproperty=tp.property,
            ).first()
            required_tech_props.append({
                'technology_id': tp.technology.id,
                'technology_name': tp.technology.name,
                'technologyproperty_id': tp.property.id,
                'technologyproperty_name': tp.property.name,
                'default_value': tp.defaultvalue,
                'existing_value': existing_val.value if existing_val else None,
            })

        # If technology properties are required but not provided in this
        # request, return the form specification so the caller can fill them.
        if required_tech_props and not request.data.get('technology_properties'):
            # direct user to the technology-properties form so they can
            # supply the required technology-level design parameters
            redirect_url = reverse(
                'technology_properties',
                kwargs={'plant_id': plant.id})
            return Response(
                {
                    'required_technology_properties': required_tech_props,
                    'redirect_url': redirect_url,
                    'message': 'Technology-level properties required; redirecting to technology-properties form.',
                },
                status=status.HTTP_200_OK,
            )
        # TODO: add a form for the technology properties and refer to it.
        
        # If technology property values are provided, validate and persist them
        tech_props_input = request.data.get('technology_properties')
        if tech_props_input:
            from drinq.serializers import TreatmentPlantTechnologyPropertySerializer

            tech_serializer = TreatmentPlantTechnologyPropertySerializer(data=tech_props_input, many=True)
            if not tech_serializer.is_valid():
                return Response(tech_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            for item in tech_serializer.validated_data:
                tech_id = item.get('technology')
                techprop_id = item.get('technologyproperty')
                val = item.get('value')
                TreatmentPlantTechnologyPropertyValue.objects.update_or_create(
                    treatmentplant=plant,
                    technology_id=tech_id,
                    technologyproperty_id=techprop_id,
                    defaults={'value': str(val)},
                )

        # Build input for calculator (adapt as needed by your calculator API)
        dp_qs = TreatmentplantDesignParameter.objects.filter(
            treatmentplant=plant)
        design_params_by_name = {
            dp.designparameter.name: dp.value 
            for dp in dp_qs.select_related('designparameter')
        }
        # `technologies` already defined above when checking tech props
        stage_names = get_stage_names(plant, technologies)
        technology_names, _ = get_technology_names(
            plant, technologies)

        # instantiate calculator
        calculator = TreatmentPlantPerformanceCalculator(
            treatmentplant_id=plant.id,
            design_parameters=design_params_by_name,
            stages=stage_names,
            technologies=technology_names
        )

        # Compute a set of plant properties
        computed_plantwide = {}
        tech_properties = get_technology_properties(
            treatmentplant=plant,
            technologies=technologies)
        parameter_categories = ParameterCategory.objects.all()
        category_mapping = {cat.name: cat for cat in parameter_categories}
        nominalflow_prop_name = [
            prp for prp in PLANT_PROPERTIES_TO_CALCULATE
            if 'nominal flow rate' in prp][0]
        constrcost_prop_name = [
            prp for prp in PLANT_PROPERTIES_TO_CALCULATE 
            if 'construction costs' in prp][0]

        computed_plantwide[nominalflow_prop_name] = calculator.get_nominal_flow_m3hr()
        constrcost_pars = get_constrcost_parameters(
            technology_list=technologies.values_list('technology', flat=True))
        computed_plantwide[constrcost_prop_name] = calculator.get_constructioncosts(
            plant_properties=computed_plantwide,
            cost_parameters=constrcost_pars,
        )

        # persist computed properties and serialize
        serialized_properties = []
        for prop_name, val in computed_plantwide.items():
            prop_obj, _ = TreatmentPlantProperty.objects.get_or_create(
                name=prop_name)
            prop_value_obj, _ = TreatmentPlantPropertyValue.objects.update_or_create(
                treatmentplant=plant,
                property=prop_obj,
                defaults={'value': str(val)}
            )
            serialized = TreatmentPlantPropertyValueSerializer(prop_value_obj).data  # noqa E501
            serialized_properties.append(serialized)

        # Build redirect URL to results page (uses url name from urls.py)
        redirect_url = reverse('design_parameter_results',
                               kwargs={'plant_id': plant.id})

        return Response(
            {
                'properties': serialized_properties,
                'redirect_url': redirect_url
            }, status=status.HTTP_200_OK)
    # return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
