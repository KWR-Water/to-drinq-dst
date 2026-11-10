"""Admin site configuration.

The decision tree models (design trees, questions, choices, deciding factors,
their technology links and the stored answers) are deliberately not
registered. Editing them can break the questionnaire for every user.
"""
from django.contrib import admin
from django.db.models import Model
from django.http import HttpRequest

from drinq.models import (
    AdaptabilityCriterion,
    ChemicalAgent,
    ChemicalagentPrice,
    Citation,
    Compound,
    CompoundCas,
    CompoundSynonym,
    DesignParameter,
    Goal,
    GoalPerTechnology,
    MultiStepConfiguration,
    ParameterCategory,
    Process,
    RemovalEfficiency,
    Stage,
    StageStage,
    StageTechnologies,
    Technology,
    TechnologyAdaptabilityScore,
    TechnologyChemicalagentJunction,
    TechnologyConstructionCostParameter,
    TechnologyKPI,
    TechnologyProperty,
    TechnologyPropertyJunction,
    TechnologyPropertyPystimelaoptJunction,
    TechnologyPystimelaoptJunction,
    TechnologyWaterqualityParameterPystimelaoptJunction,
    TreatmentPlant,
    TreatmentPlantChemicalagentPriceJunction,
    TreatmentPlantLayout,
    TreatmentPlantProperty,
    TreatmentPlantPropertyValue,
    TreatmentPlantTechnologyKPIValue,
    TreatmentPlantTechnologyOptimizationStatus,
    TreatmentPlantTechnologyPropertyValue,
    TreatmentPlantWaterQualityParameterValue,
    TreatmentplantDesignParameter,
    Watercompany,
    WaterqualityParameter,
    WaterqualityParameterTechnologyJunction,
)


class NameLockedAdmin(admin.ModelAdmin):
    """Make ``name`` read-only after creation.

    The names are shared with code and JSON files, so renaming a row breaks
    the calculations.
    """

    def get_readonly_fields(
        self, request: HttpRequest, obj: Model | None = None
    ) -> tuple[str, ...]:
        readonly = tuple(super().get_readonly_fields(request, obj))
        return (*readonly, 'name') if obj is not None else readonly


class ReadOnlyAdmin(admin.ModelAdmin):
    """Show rows for inspection only.

    Deleting stays governed by the delete permission. Admin blocks deleting a
    user when it may not delete the related rows, so it must not be disabled.
    """

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: Model | None = None
    ) -> bool:
        return False


# --- Chemistry and general catalogue ---------------------------------------
admin.site.register(
    (
        Compound, CompoundCas, CompoundSynonym, Process, Goal,
        RemovalEfficiency, GoalPerTechnology,
    )
)
admin.site.register((Watercompany, Citation, ParameterCategory))


@admin.register(Stage)
class StageAdmin(NameLockedAdmin):
    search_fields = ('name',)


@admin.register(StageStage)
class StageStageAdmin(admin.ModelAdmin):
    list_display = ('stage_current', 'stage_previous', 'stage_next')
    list_select_related = ('stage_current', 'stage_previous', 'stage_next')


@admin.register(Technology)
class TechnologyAdmin(NameLockedAdmin):
    search_fields = ('name',)


@admin.register(StageTechnologies)
class StageTechnologiesAdmin(admin.ModelAdmin):
    list_display = ('technology', 'stage')
    list_select_related = ('technology', 'stage')
    list_filter = ('stage',)
    search_fields = ('technology__name',)
    autocomplete_fields = ('stage', 'technology')


# --- Technology and design parameters --------------------------------------
@admin.register(TechnologyProperty)
class TechnologyPropertyAdmin(NameLockedAdmin):
    list_display = ('name', 'unit', 'category', 'parent_property')
    list_select_related = ('category', 'parent_property')
    list_filter = ('category',)
    search_fields = ('name',)


@admin.register(TechnologyPropertyJunction)
class TechnologyPropertyJunctionAdmin(admin.ModelAdmin):
    list_display = (
        'technology', 'property', 'default_value', 'is_designparameter',
        'is_digested', 'sent_to_optimizer',
    )
    list_select_related = ('technology', 'property')
    list_filter = (
        'is_designparameter', 'is_digested', 'sent_to_optimizer',
    )
    search_fields = ('technology__name', 'property__name')
    autocomplete_fields = ('technology', 'property')


@admin.register(TechnologyConstructionCostParameter)
class TechnologyConstructionCostParameterAdmin(admin.ModelAdmin):
    list_display = (
        'technology', 'a', 'b', 'c', 'd', 'e', 'plantproperty',
        'technologyproperty',
    )
    list_select_related = ('technology', 'plantproperty', 'technologyproperty')
    search_fields = ('technology__name',)
    autocomplete_fields = (
        'technology', 'plantproperty', 'technologyproperty')


@admin.register(TechnologyKPI)
class TechnologyKPIAdmin(NameLockedAdmin):
    list_display = ('name', 'unit')
    search_fields = ('name',)


@admin.register(DesignParameter)
class DesignParameterAdmin(NameLockedAdmin):
    list_display = ('name', 'unit', 'category', 'defaultvalue')
    list_select_related = ('category',)
    list_filter = ('category',)
    search_fields = ('name',)


@admin.register(TreatmentPlantProperty)
class TreatmentPlantPropertyAdmin(NameLockedAdmin):
    list_display = ('name', 'unit', 'category')
    list_select_related = ('category',)
    list_filter = ('category',)
    search_fields = ('name',)


# --- Water quality and chemicals -------------------------------------------
@admin.register(WaterqualityParameter)
class WaterqualityParameterAdmin(NameLockedAdmin):
    list_display = ('name', 'unit')
    search_fields = ('name',)


@admin.register(WaterqualityParameterTechnologyJunction)
class WaterqualityParameterTechnologyJunctionAdmin(admin.ModelAdmin):
    list_display = (
        'technology', 'waterqualityparameter', 'is_inputparameter',
        'is_targetparameter', 'sent_to_optimizer', 'default_value',
    )
    list_select_related = ('technology', 'waterqualityparameter')
    list_filter = (
        'is_inputparameter', 'is_targetparameter', 'sent_to_optimizer',
    )
    search_fields = ('technology__name', 'waterqualityparameter__name')
    autocomplete_fields = ('technology', 'waterqualityparameter')


@admin.register(ChemicalAgent)
class ChemicalAgentAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(ChemicalagentPrice)
class ChemicalagentPriceAdmin(admin.ModelAdmin):
    list_display = ('chemical_agent', 'default_value', 'units')
    list_select_related = ('chemical_agent',)
    autocomplete_fields = ('chemical_agent',)


@admin.register(TechnologyChemicalagentJunction)
class TechnologyChemicalagentJunctionAdmin(admin.ModelAdmin):
    list_display = ('technology', 'chemical_agent')
    list_select_related = ('technology', 'chemical_agent')
    search_fields = ('technology__name', 'chemical_agent__name')
    autocomplete_fields = ('technology', 'chemical_agent')


# --- Adaptability ----------------------------------------------------------
@admin.register(AdaptabilityCriterion)
class AdaptabilityCriterionAdmin(admin.ModelAdmin):
    list_display = ('slug', 'label')
    search_fields = ('slug', 'label')


@admin.register(TechnologyAdaptabilityScore)
class TechnologyAdaptabilityScoreAdmin(admin.ModelAdmin):
    list_display = (
        'technology', 'adaptabilitycriterion', 'raw_symbol', 'score')
    list_select_related = ('technology', 'adaptabilitycriterion')
    list_filter = ('adaptabilitycriterion',)
    search_fields = ('technology__name',)
    autocomplete_fields = ('technology', 'adaptabilitycriterion')


# --- Optimizer mappings (read-only) ----------------------------------------
@admin.register(TechnologyPystimelaoptJunction)
class TechnologyPystimelaoptJunctionAdmin(ReadOnlyAdmin):
    list_display = ('technology', 'pystim_name')
    list_select_related = ('technology',)
    search_fields = ('technology__name', 'pystim_name')


@admin.register(TechnologyPropertyPystimelaoptJunction)
class TechnologyPropertyPystimelaoptJunctionAdmin(ReadOnlyAdmin):
    list_display = ('technology_property', 'pystim_name')
    list_select_related = (
        'technology_property__technology', 'technology_property__property')
    search_fields = (
        'technology_property__technology__name',
        'technology_property__property__name',
        'pystim_name',
    )


@admin.register(TechnologyWaterqualityParameterPystimelaoptJunction)
class TechnologyWaterqualityParameterPystimelaoptJunctionAdmin(
    ReadOnlyAdmin
):
    list_display = ('wqparameter_technology', 'pystim_name')
    list_select_related = (
        'wqparameter_technology__technology',
        'wqparameter_technology__waterqualityparameter',
    )
    search_fields = (
        'wqparameter_technology__technology__name',
        'wqparameter_technology__waterqualityparameter__name',
        'pystim_name',
    )


# --- User-generated plant data (read-only) ---------------------------------
@admin.register(MultiStepConfiguration)
class MultiStepConfigurationAdmin(ReadOnlyAdmin):
    list_display = ('name', 'user', 'water_source', 'date_created')
    list_select_related = ('user', 'water_source')
    list_filter = ('water_source',)
    search_fields = ('name', 'user__username')


@admin.register(TreatmentPlant)
class TreatmentPlantAdmin(ReadOnlyAdmin):
    list_display = ('name', 'option', 'configuration')
    list_select_related = ('configuration',)
    search_fields = (
        'name', 'configuration__name', 'configuration__user__username')


@admin.register(TreatmentPlantLayout)
class TreatmentPlantLayoutAdmin(ReadOnlyAdmin):
    list_display = ('treatmentplant', 'step', 'technology')
    list_select_related = ('treatmentplant', 'technology')
    search_fields = ('treatmentplant__name', 'technology__name')


@admin.register(TreatmentplantDesignParameter)
class TreatmentplantDesignParameterAdmin(ReadOnlyAdmin):
    list_display = ('treatmentplant', 'designparameter', 'value')
    list_select_related = ('treatmentplant', 'designparameter')
    search_fields = ('treatmentplant__name', 'designparameter__name')


@admin.register(TreatmentPlantPropertyValue)
class TreatmentPlantPropertyValueAdmin(ReadOnlyAdmin):
    list_display = ('treatmentplant', 'property', 'value')
    list_select_related = ('treatmentplant', 'property')
    search_fields = ('treatmentplant__name', 'property__name')


@admin.register(TreatmentPlantTechnologyPropertyValue)
class TreatmentPlantTechnologyPropertyValueAdmin(ReadOnlyAdmin):
    list_display = (
        'treatmentplant', 'technology', 'technologyproperty', 'value',
        'source',
    )
    list_select_related = (
        'treatmentplant', 'technology', 'technologyproperty')
    list_filter = ('source',)
    search_fields = (
        'treatmentplant__name', 'technology__name',
        'technologyproperty__name',
    )


@admin.register(TreatmentPlantTechnologyKPIValue)
class TreatmentPlantTechnologyKPIValueAdmin(ReadOnlyAdmin):
    list_display = ('treatmentplant', 'technology', 'kpi', 'value')
    list_select_related = ('treatmentplant', 'technology', 'kpi')
    search_fields = ('treatmentplant__name', 'technology__name', 'kpi__name')


@admin.register(TreatmentPlantWaterQualityParameterValue)
class TreatmentPlantWaterQualityParameterValueAdmin(ReadOnlyAdmin):
    list_display = ('treatmentplant', 'wq_tech_parameter', 'value')
    list_select_related = (
        'treatmentplant',
        'wq_tech_parameter__technology',
        'wq_tech_parameter__waterqualityparameter',
    )
    search_fields = ('treatmentplant__name',)


@admin.register(TreatmentPlantChemicalagentPriceJunction)
class TreatmentPlantChemicalagentPriceJunctionAdmin(ReadOnlyAdmin):
    list_display = ('treatmentplant', 'chemicalagent', 'price')
    list_select_related = ('treatmentplant', 'chemicalagent')
    search_fields = ('treatmentplant__name', 'chemicalagent__name')


@admin.register(TreatmentPlantTechnologyOptimizationStatus)
class TreatmentPlantTechnologyOptimizationStatusAdmin(ReadOnlyAdmin):
    list_display = (
        'treatmentplant', 'technology', 'is_optimized', 'optimized_at')
    list_select_related = ('treatmentplant', 'technology')
    list_filter = ('is_optimized',)
    search_fields = ('treatmentplant__name', 'technology__name')
