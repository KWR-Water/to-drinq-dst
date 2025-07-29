from rest_framework import serializers
from drinq.models import (
    TreatmentPlant,
    TreatmentplantDesignParameter,
    TreatmentplantProperty,
    TreatmentplantPropertyValue,
)


class DesignParameterInputSerializer(serializers.Serializer):
    treatmentplant_id = serializers.IntegerField()
    configuration_id = serializers.IntegerField()
    parameters = serializers.DictField(child=serializers.FloatField())


class TreatmentPlantPropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = TreatmentplantPropertyValue
        fields = ['property', 'value']
