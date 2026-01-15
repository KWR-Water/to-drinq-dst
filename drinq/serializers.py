from rest_framework import serializers
from drinq.models import (
    ParameterCategory,
    TreatmentPlantProperty,
    TreatmentPlantPropertyValue,
    TreatmentPlantTechnologyPropertyValue,
)


class TreatmentPlantTechnologyPropertySerializer(serializers.ModelSerializer):

    class Meta:
        model = TreatmentPlantTechnologyPropertyValue
        fields = ['technology', 'technologyproperty', 'value']


class DesignParameterInputSerializer(serializers.Serializer):
    treatmentplant_id = serializers.IntegerField()
    configuration_id = serializers.IntegerField()
    parameters = serializers.DictField(child=serializers.FloatField())
    # optional nested technology properties so a single POST can include
    # both plant-level design parameters and technology-level values
    technology_properties = TreatmentPlantTechnologyPropertySerializer(
        many=True, required=False)


class ParameterCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ParameterCategory
        fields = ['name']


class TreatmentPlantPropertySerializer(serializers.ModelSerializer):
    category = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = TreatmentPlantProperty
        fields = ['id', 'name', 'unit', 'category']


class TreatmentPlantPropertyValueSerializer(serializers.ModelSerializer):
    property = TreatmentPlantPropertySerializer(read_only=True)

    class Meta:
        model = TreatmentPlantPropertyValue
        fields = ['property', 'value']
