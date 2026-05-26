 
from django.shortcuts import render, redirect, get_object_or_404

from collections import OrderedDict, defaultdict

import logging
import numpy as np
from warnings import warn
from django.contrib.auth.mixins import LoginRequiredMixin

from django.http import (
    HttpResponse, Http404, HttpResponseRedirect, JsonResponse,
    )
from django.views import generic
from django.forms import ValidationError, modelformset_factory
from django.urls import reverse
from django.db.models import Avg, Count
from django.db import IntegrityError, transaction
from django.db.utils import OperationalError

from drinq.models import (
    AdaptabilityCriterion,
    Compound,
    CompoundCas,
    Technology,
    TechnologyRelatedtechnology,
    StageTechnologies,
    Stage,
    DecidingFactor,
    DecidingFactorQuestion,
    DecidingFactorChoice,
    QuestionAnswer,
    MultiStepConfiguration,
    DesignParameter,
    TechnologyKPI,
    TechnologyProperty,
    TechnologyPropertyJunction,
    TreatmentPlant,
    TreatmentPlantLayout,
    TreatmentplantDesignParameter,
    TreatmentPlantChemicalagentPriceJunction,
    TreatmentPlantPropertyValue,
    TreatmentPlantProperty,
    TreatmentPlantTechnologyPropertyValue,
    TreatmentPlantWaterQualityParameterValue,
    TechnologyConstructionCostParameter,
    TechnologyChemicalagentJunction,
    ChemicalagentPrice,
    WaterqualityParameterTechnologyJunction,
    TreatmentPlantTechnologyKPIValue,
    TechnologyAdaptabilityScore,
    ConfiguredTechnologies,
)
from drinq.forms import (
    ConfigurationNameForm,
    WaterSourceForm,
    QuestionWizardForm,
    SessionSelectForm,
    TreatmentDesignSelectionForm,
    DesignParameterValueFormSet,
    TreatmentPlantTechPropertyValueFormSet,
    TreatmentTechPropertyValueForm,
    WaterQualityParameterValueFormSet,
    build_technology_property_initials,
    )
from drinq.chemistry_tools import smiles_to_svg
import drinq.decision_tree as dst
import drinq.api_calculation as dac

from drinq.api_calculation import (
    WaterqualityParameterData,
    KPI_NOMINAL_FLOW_M3PERH,
    KPI_ENERGY_CONSUMPTION_KWHRPERM3,
    KPI_CONSTRUCTION_COSTS,
    KPI_FOOTPRINT_AREA_M2,
    KPI_OPER_AND_MAINT_COSTS_ANN,
    KPI_INVESTMENT_COSTS_ANN,
    KPI_LEVELIZED_COST_OF_WATER,
    KPI_LEVELIZED_CHEMICAL_COSTS,
    KPI_CO2_EMISSIONS_KGPERM3,
    TECHKPI_ENERGYCONSUMPTION_KWHRPERDAY,
    TECHKPI_FOOTPRINT_AREA_M2,
    TECHKPI_POWER_KW,
    TECHKPI_CO2_EMISSIONS_KGPERM3,
    TECHKPI_DAILY_CHEMICAL_COSTS_EUR_PER_DAY,
    DESIGN_PAR_OPERATION_MAINTENANCE_PERC_NAME,
    DESIGN_PAR_INTEREST_PERC_NAME,
    DESIGN_PAR_LIFESPAN_NAME,
    DESIGN_PAR_PERSONNEL_COSTS_NAME,
    DESIGN_PAR_ENERGY_PRICE_NAME,
    )

from drinq.utils.treatmentkpi import (
    TPPN,
    TPN,
    INPUT_WQPARAMETER_KEY,
    TARGET_WQPARAMETER_KEY,
)


EXCLUDE_KEY = ['csrfmiddlewaretoken', 'next']
INITIAL_TOTAL_STEPS = 4
DECISION_TREE_MAX_STEPS = 50
DB_PLANTKPI_MAPPING = {
    KPI_NOMINAL_FLOW_M3PERH: TPPN['nominal_flow_rate'],
    KPI_ENERGY_CONSUMPTION_KWHRPERM3: TPPN['specific_energy_consumption'],
    KPI_FOOTPRINT_AREA_M2: TPPN['footprint_area'],
    KPI_CONSTRUCTION_COSTS: TPPN['construction_costs'],
    KPI_OPER_AND_MAINT_COSTS_ANN: TPPN['operation_and_maintenance_costs_annual'],
    KPI_INVESTMENT_COSTS_ANN: TPPN['investment_costs_annual'],
    KPI_CO2_EMISSIONS_KGPERM3: TPPN['co2_equivalent_emissions'],
    KPI_LEVELIZED_COST_OF_WATER: TPPN['levelized_cost_of_water'],
    KPI_LEVELIZED_CHEMICAL_COSTS: TPPN['levelized_cost_of_chemicals'],
    # KPI_MASS_OF_CHEMICALS: TPPN['mass_of_chemicals'],
}
# SUMMED_TECHKPI_MAPPING = {
#     KPI_ENERGY_CONSUMPTION_KWHRPERM3: TPPN['energy_consumption_kwhperm3'],
#     TECHKPI_FOOTPRINT_AREA_M2: TPPN['footprint_area_m2'],
#     TECHKPI_CO2_EMISSIONS_KGPERM3: TPPN['co2_equivalent_emissions_kgperm3'],
# }

logger = logging.getLogger(__name__)


def get_adaptability_scores_for_technologies(technologies):
    """Return aggregated adaptability scores for a sequence of technologies.

    The technology score is the average over available adaptability criteria.
    The treatment-plant score is the average over included technology scores.
    """
    criteria_rows = list(
        AdaptabilityCriterion.objects
        .order_by('id')
        .values('id', 'slug', 'label')
    )
    criteria = [
        {
            'id': row['id'],
            'slug': row['slug'],
            'label': row['label'],
            'display_name': row['label'] or row['slug'],
        }
        for row in criteria_rows
    ]

    technology_ids = [tech.id for tech in technologies if tech is not None]
    if not technology_ids:
        return {
            'criteria': criteria,
            'criteria_total': len(criteria),
            'technology_scores': {},
            'technology_criteria_counts': {},
            'technology_criterion_scores': {},
            'plant_score': None,
        }

    technology_score_rows = (
        TechnologyAdaptabilityScore.objects
        .filter(technology_id__in=technology_ids)
        .values('technology_id')
        .annotate(
            adaptability_score=Avg('score'),
            criteria_count=Count('adaptabilitycriterion', distinct=True),
        )
    )

    technology_scores = {
        row['technology_id']: row['adaptability_score']
        for row in technology_score_rows
    }
    technology_criteria_counts = {
        row['technology_id']: row['criteria_count']
        for row in technology_score_rows
    }
    technology_criterion_scores = {
        technology_id: {} for technology_id in technology_ids
    }
    criterion_score_rows = (
        TechnologyAdaptabilityScore.objects
        .filter(technology_id__in=technology_ids)
        .values('technology_id', 'adaptabilitycriterion_id', 'score')
    )
    for row in criterion_score_rows:
        technology_criterion_scores[row['technology_id']][
            row['adaptabilitycriterion_id']
        ] = row['score']

    available_scores = [
        technology_scores[technology_id]
        for technology_id in technology_ids
        if technology_scores.get(technology_id) is not None
    ]
    plant_score = (
        sum(available_scores) / len(available_scores)
        if available_scores else None
    )

    return {
        'criteria': criteria,
        'criteria_total': len(criteria),
        'technology_scores': technology_scores,
        'technology_criteria_counts': technology_criteria_counts,
        'technology_criterion_scores': technology_criterion_scores,
        'plant_score': plant_score,
    }


class Register(generic.TemplateView):
    template_name = "drinq/register.html"


class Welcome(generic.TemplateView):
    template_name = "drinq/welcome.html"


class PasswordChangeOk(generic.TemplateView):
    template_name = "drinq/password_change_ok.html"


class SessionSelectView(generic.edit.FormView):
    template_name = 'drinq/session_select.html'
    form_class = SessionSelectForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        session = form.cleaned_data['session']
        return redirect('form_complete', session_key=session.session_key)


class ConfigurationManagementView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'drinq/configuration_manage.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        configurations = (
            MultiStepConfiguration.objects
            .filter(user=self.request.user)
            .prefetch_related('treatmentplant_set')
            .order_by('-date_created')
        )
        context['configurations'] = configurations
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        if action == 'delete_configuration':
            return self._delete_configuration(request)
        if action == 'delete_option':
            return self._delete_option(request)
        return redirect('configuration_manage')

    def _delete_configuration(self, request):
        configuration_id = request.POST.get('configuration_id')
        try:
            configuration = MultiStepConfiguration.objects.get(
                id=configuration_id,
                user=request.user,
            )
        except MultiStepConfiguration.DoesNotExist:
            raise Http404('Configuration does not exist.')

        if request.session.get('configuration_id') == configuration.id:
            request.session.pop('configuration_id', None)
        self._delete_configuration_with_fallback(configuration)
        return redirect('configuration_manage')

    def _delete_option(self, request):
        configuration_id = request.POST.get('configuration_id')
        treatment_plant_id = request.POST.get('treatment_plant_id')
        try:
            treatment_plant = TreatmentPlant.objects.get(
                id=treatment_plant_id,
                configuration_id=configuration_id,
                configuration__user=request.user,
            )
        except TreatmentPlant.DoesNotExist:
            raise Http404('Treatment design option does not exist.')

        self._delete_treatment_plant_with_fallback(treatment_plant)
        return redirect('configuration_manage')

    def _delete_configuration_with_fallback(
            self,
            configuration: MultiStepConfiguration) -> None:
        try:
            configuration.delete()
            return
        except (OperationalError, IntegrityError) as exc:
            if not self._is_supported_delete_fallback_error(exc):
                raise

        self._hard_delete_configuration(configuration.id)

    def _delete_treatment_plant_with_fallback(
            self,
            treatment_plant: TreatmentPlant) -> None:
        try:
            treatment_plant.delete()
            return
        except (OperationalError, IntegrityError) as exc:
            if not self._is_supported_delete_fallback_error(exc):
                raise

        self._hard_delete_treatment_plant(treatment_plant.id)

    def _is_supported_delete_fallback_error(self, exc: Exception) -> bool:
        error_text = str(exc).lower()
        if isinstance(exc, OperationalError):
            return 'no such table' in error_text
        if isinstance(exc, IntegrityError):
            return 'foreign key' in error_text
        return False

    def _hard_delete_configuration(self, configuration_id: int) -> None:
        db_alias = MultiStepConfiguration.objects.db
        treatment_plant_ids = list(
            TreatmentPlant.objects.filter(
                configuration_id=configuration_id,
            ).values_list('id', flat=True)
        )

        with transaction.atomic(using=db_alias):
            for treatment_plant_id in treatment_plant_ids:
                self._hard_delete_treatment_plant(
                    treatment_plant_id,
                    db_alias=db_alias,
                )

            self._raw_delete_if_table_exists(
                QuestionAnswer.objects.filter(
                    configuration_id=configuration_id,
                ),
                db_alias,
            )
            self._raw_delete_if_table_exists(
                ConfiguredTechnologies.objects.filter(
                    configuration_id=configuration_id,
                ),
                db_alias,
            )
            self._raw_delete_if_table_exists(
                MultiStepConfiguration.objects.filter(id=configuration_id),
                db_alias,
            )

    def _hard_delete_treatment_plant(
            self,
            treatment_plant_id: int,
            db_alias: str | None = None) -> None:
        if db_alias is None:
            db_alias = TreatmentPlant.objects.db

        child_querysets = [
            TreatmentPlantLayout.objects.filter(
                treatmentplant_id=treatment_plant_id,
            ),
            TreatmentplantDesignParameter.objects.filter(
                treatmentplant_id=treatment_plant_id,
            ),
            TreatmentPlantPropertyValue.objects.filter(
                treatmentplant_id=treatment_plant_id,
            ),
            TreatmentPlantTechnologyPropertyValue.objects.filter(
                treatmentplant_id=treatment_plant_id,
            ),
            TreatmentPlantWaterQualityParameterValue.objects.filter(
                treatmentplant_id=treatment_plant_id,
            ),
            TreatmentPlantTechnologyKPIValue.objects.filter(
                treatmentplant_id=treatment_plant_id,
            ),
            TreatmentPlantChemicalagentPriceJunction.objects.filter(
                treatmentplant_id=treatment_plant_id,
            ),
        ]

        for child_queryset in child_querysets:
            self._raw_delete_if_table_exists(child_queryset, db_alias)

        self._raw_delete_if_table_exists(
            TreatmentPlant.objects.filter(id=treatment_plant_id),
            db_alias,
        )

    def _raw_delete_if_table_exists(self, queryset, db_alias: str) -> None:
        try:
            queryset._raw_delete(db_alias)
        except OperationalError as exc:
            if 'no such table' not in str(exc).lower():
                raise


class ConfigurationUpdateView(LoginRequiredMixin, generic.UpdateView):
    model = MultiStepConfiguration
    form_class = ConfigurationNameForm
    template_name = 'drinq/configuration_edit.html'

    def get_queryset(self):
        return MultiStepConfiguration.objects.filter(user=self.request.user)

    def get_success_url(self):
        return f"{reverse('configuration_manage')}?updated=1"


class FormNameView(LoginRequiredMixin, generic.edit.FormView):
    form_class = ConfigurationNameForm
    template_name = 'drinq/form_name.html'
    success_url = 'form_watersource'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['step'] = 1
        context['total_steps'] = INITIAL_TOTAL_STEPS
        return context

    def form_valid(self, form):
        self.request.session.cycle_key()
        session_key = self.request.session.session_key
        configuration = form.save(commit=False)
        configuration.user = self.request.user
        configuration.session_key = session_key
        configuration.save()
        self.request.session['configuration_id'] = configuration.id
        return redirect(self.get_success_url())


class FormWaterSourceView(LoginRequiredMixin, generic.edit.FormView):
    form_class = WaterSourceForm
    template_name = 'drinq/form_watersource.html'
    success_url = 'form_multistep'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['step'] = 2
        context['total_steps'] = INITIAL_TOTAL_STEPS
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        configuration = MultiStepConfiguration.objects.get(
            id=self.request.session['configuration_id'])
        kwargs.update({'instance': configuration})
        return kwargs

    def form_valid(self, form):
        form.save()
        water_source = get_watersource(self.request)
        next_deciding_factor = self.get_next_deciding_factor(
            design_tree=water_source)
        return redirect(
            self.get_success_url(),
            decidingfactor_id=next_deciding_factor.pk)

    def get_first_question_id(self):
        queryset = DecidingFactorQuestion.objects.filter(name='q_sourcewater')
        if len(queryset) == 0:
            raise ValidationError("No question found for the water source.")
        question_id = queryset.first().pk
        return self.get_next_question_id(question_id)

    def get_next_deciding_factor(self, design_tree: int):
        # determine the choice based on the design tree
        if design_tree is None:
            raise ValidationError("No design tree found for the water source.")
        choice = DecidingFactorChoice.objects.get(
            design_tree=design_tree)  # this corresponds to the actual choice 
        qs_decidingfactor = DecidingFactor.objects.filter(
            design_tree=design_tree, choice=choice)
        deciding_factor = None
        if len(qs_decidingfactor) == 0:
            raise ValidationError("No parent ID found for the water source.")
        elif len(qs_decidingfactor) == 1:
            deciding_factor = qs_decidingfactor.first()
            return deciding_factor.get_descendants(depth=1).first()
        else:
            raise ValidationError(
                "Multiple parent IDs found for the water source.")


def get_watersource(request):
    """Get the water source from the session.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        DesignTree: The water source id.
    """
    if request.method == 'GET':
        configuration = MultiStepConfiguration.objects.get(
            id=request.session['configuration_id'])
        water_source = configuration.water_source
    else:
        water_source = int(request.POST.get('water_source'))
    return water_source


class MultiStepQuestionView(LoginRequiredMixin, generic.edit.FormView):
    template_name = "drinq/multi_form.html"
    success_url = 'form_multistep'

    def dispatch(self, request, *args, **kwargs):
        # self.question = DecidingFactorQuestion.objects.get(
        #     id=self.kwargs['question_id'])
        self.decidingfactor = self.kwargs['decidingfactor_id']

        if 'decidingfactor_id' not in request.session:
            request.session['decidingfactor_id'] = self.decidingfactor

        return super().dispatch(request, *args, **kwargs)

    def get_form_class(self):
        return lambda *args, **kwargs: QuestionWizardForm(
            self.decidingfactor, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        total_steps = context['total_steps'] = 1 + INITIAL_TOTAL_STEPS
        deciding_factor = context['view'].kwargs.get('decidingfactor_id')
        if deciding_factor is not None:
            context['step'] = 3
        else:
            context['step'] = total_steps
        context['total_steps'] = total_steps
        return context

    def form_valid(self, form):
        configuration = MultiStepConfiguration.objects.get(
            id=self.request.session['configuration_id'])
        deciding_factor = DecidingFactor.objects.get(id=self.decidingfactor)
        choice = form.data['choice']
        if choice is not None:  # should be cleaned_data['choice']
            choice = DecidingFactorChoice.objects.get(id=choice)
        _, created = QuestionAnswer.objects.get_or_create(
            configuration=configuration,
            question=deciding_factor.question,
            decidingfactor=deciding_factor,
            answer=choice
        )
        current_decidingfactor = deciding_factor.get_children().get(
            choice=choice)
        (
            next_decidingfactor,
            prev_decidingfactor_w_choice,
            goto_next_step,
            ) = self.get_next_decidingfactor(
            current_decidingfactor=current_decidingfactor)
        if prev_decidingfactor_w_choice is not None:
            _, created = QuestionAnswer.objects.get_or_create(
                configuration=configuration,
                question=prev_decidingfactor_w_choice.question,
                decidingfactor=prev_decidingfactor_w_choice,
                answer=prev_decidingfactor_w_choice.choice
            )
            if created:
                pass  # log something?
        _ = self.get_context_data()
        self.request.session['form_multistep'] = self.request.session.get(
            'form_multistep', 3) + 1
        if goto_next_step:
            return redirect(
                self.get_success_url(),
                decidingfactor_id=next_decidingfactor.pk)  # reverse?
        context = self.get_context_data()
        context['steps'] = context['total_steps']
        return redirect('form_complete', session_key=configuration.session_key)

    def get_next_decidingfactor(self, current_decidingfactor):
        """
        Get the next deciding factor based on the current one.
        """
        try:
            decidingfactor_children = current_decidingfactor.get_children()
            counter = 0
            question = None
            goto_next_step = True
            previous_decidingfactor_with_choice = None
            while counter < DECISION_TREE_MAX_STEPS and question is None:
                counter += 1
                if decidingfactor_children.exists():
                    next_deciding_factor = decidingfactor_children.first()
                    question = next_deciding_factor.question
                    if question is not None:
                        break  # the deciding factor has a question
                    else:
                        # If the next deciding factor has no question,
                        # get the next one
                        if next_deciding_factor.choice is not None:
                            # If the next deciding factor has a choice,
                            # store it as the previous one
                            previous_decidingfactor_with_choice = (
                                next_deciding_factor)
                        decidingfactor_children = next_deciding_factor.get_children()  # noqa, E501
                else:
                    # No more children, break the loop
                    next_deciding_factor = None
                    goto_next_step = False
                    break
            if counter == DECISION_TREE_MAX_STEPS:
                goto_next_step = False
            return (
                next_deciding_factor,
                previous_decidingfactor_with_choice,
                goto_next_step,
            )
        except DecidingFactor.DoesNotExist:
            return None, None, False


class QuestionsCompleteView(generic.TemplateView):
    template_name = "drinq/form_complete.html"

    def dispatch(self, request, *args, **kwargs):
        session_key = kwargs.get('session_key', None)
        session = request.session
        if session_key is None:
            session_key = session.get('session_key', None)
        if 'configuration_id' not in session and session_key is not None:
            configuration = MultiStepConfiguration.objects.get(
                session_key=session_key)
            if configuration is not None:
                session['configuration_id'] = configuration.id
        return super().dispatch(request, *args, **kwargs)

    def get(self, request: HttpResponse, *args, **kwargs):
        session_key = kwargs.get('session_key', None)
        configuration = MultiStepConfiguration.objects.get(
                session_key=session_key)
        try:
            results = QuestionAnswer.objects.filter(
                configuration__id=configuration.id)
        except QuestionAnswer.DoesNotExist:
            results = QuestionAnswer.objects.none()
        if not results.exists():
            return HttpResponseRedirect(redirect('drinq_redirect'))

        # Parse filter selections from GET
        selected_techs = []
        num_stages = 0
        if 'num_stages' in request.GET:
            try:
                num_stages = int(request.GET['num_stages'])
            except Exception:
                num_stages = 0

        # Always fill selected_techs to num_stages, using None for missing
        selected_techs = []
        for i in range(num_stages):
            tech_id = request.GET.get(f'stage_{i+1}')
            if tech_id is not None and tech_id != '':
                try:
                    selected_techs.append(int(tech_id))
                except Exception:
                    selected_techs.append(None)
            else:
                selected_techs.append(None)

        context = self.get_context_data(
            results=results, selected_techs=selected_techs)
        # Add num_stages to context for template
        context['num_stages'] = context.get('num_stages', len(selected_techs))
        return render(
            request,
            template_name=self.template_name,
            context={'data': context})

    def get_context_data(self, **kwargs):
        results = kwargs.get('results', None)
        selected_techs = kwargs.get('selected_techs', [])
        choices, technologies, treatment_options = {}, [], []
        config_id = self.request.session['configuration_id']
        session_key = MultiStepConfiguration.objects.get(
            id=config_id).session_key
        if session_key is not None:
            configuration = MultiStepConfiguration.objects.get(
                session_key=session_key)
        else:
            configuration = None
        named_option_ids = TreatmentPlant.objects.filter(
                configuration=configuration).values_list(
                    'option', flat=True)
        slugged_plants = TreatmentPlant.objects.filter(
                configuration=configuration)
        context = {
            'choices': choices,
            'technologies': technologies,
            'treatment_options': treatment_options,
            'form_treatment': TreatmentDesignSelectionForm(),
            'treatment_layouts': {},
            'configuration': configuration
        }
        if results is not None and configuration is not None:
            choices = results.values_list('answer', flat=True)
            for choice in choices:
                if choice is not None:
                    choice_description = dst.get_choice_description(
                        choice=choice, query_set=None)
                    if choice_description is not None:
                        context['choices'].update({choice: choice_description})
                    technology = dst.get_technology_of_choice(choice=choice)
                    if technology:
                        technologies += [technology]

            context['technologies'] = technologies
            treatment_options, treatment_maps = dst.get_treatment_trains(
                technology_tuples=technologies)

            # Build available technologies and stage names per step
            num_stages = len(technologies)
            stages = []
            stage_names = []
            for i in range(num_stages):
                tech_ids = set()
                for option in treatment_maps.values():
                    if (i+1) in option:
                        tech_ids.add(option[i+1]['technology'])
                techs = list(Technology.objects.filter(id__in=tech_ids))
                # Try to get the stage name from the first technology in this step
                stage_name = f"Stage {i+1}"
                omp_removal_passes = False
                if techs:
                    # FIX the filtering where the Ozone removal technology is 
                    # wrongly assigned to OMP removal for the disinfection stage.
                    # TODO: Try to get the stage via StageTechnologies if available
                    # Make an exception for the case Ozonation is for disinfection, 
                    # then do not chose the first entry
                    stage_objs = (
                        Stage.objects.filter(
                            id__in=StageTechnologies.objects.filter(
                                technology=techs[0]).values_list(
                                    'stage', flat=True)
                        ))
                    len_stage_objs = len(stage_objs)
                    if len_stage_objs > 0:
                        # Test whether OMP removal is present
                        if not omp_removal_passes:
                            for stage_name in stage_names:
                                if 'omp' in stage_name.lower():
                                    omp_removal_passes = True
                        if len_stage_objs > 1:
                            # First check if OMP removal is already present
                            if omp_removal_passes and 'omp' in stage_objs.first().name.lower():
                                stage_objs = stage_objs.exclude(name__icontains='omp')  # noqa, E501
                                len_stage_objs = len(stage_objs)
                        if len_stage_objs > 1:
                            logger.warning("Multiple stage objects found for technology %s", techs[0].name)
                        stage_obj = stage_objs.first()
                        stage_name = stage_obj.name
                    else:
                        stage_obj = None
                stages.append({'name': stage_name, 'technologies': techs})
                stage_names += [stage_name]

            # Filter treatment options based on selected_techs
            filtered_options = {}
            for opt_nr, option in treatment_maps.items():
                match = True
                for stage_idx, sel in enumerate(selected_techs):
                    if sel and option.get(stage_idx+1, {}).get('technology') != sel:
                        match = False
                        break
                if match:
                    filtered_options[opt_nr] = treatment_options[opt_nr]

            # Mark already named and slugged
            for option_number, _ in filtered_options.items():
                filtered_options[option_number]['already_named'] = (
                    option_number in named_option_ids
                )
            for plant in slugged_plants:
                if plant.slug is not None and plant.option in filtered_options:
                    filtered_options[plant.option]['slug'] = plant.slug

            context['treatment_options'] = filtered_options
            context['stages'] = stages
            context['selected_techs'] = selected_techs
            context['num_stages'] = num_stages
            self.request.session['treatment_maps'] = treatment_maps

        return context


class NamedDesignCreateView(generic.CreateView):
    model = TreatmentPlant
    form_class = TreatmentDesignSelectionForm
    template_name = 'drinq/form_complete.html'

    def post(self, request, *args, **kwargs):
        session = request.session
        name = request.POST.get('name')
        option = request.POST.get('option_number')
        configuration_id = request.POST.get('configuration')

        # Retrieve technologies from session or re-derive them
        treatment_map = session.get('treatment_maps', {}).get(option)
        if not treatment_map:
            return JsonResponse({
                'error': 'Technologies not found for this option'},
                status=400
                )

        # Create DesignOption and TreatmentPlantLayout
        configuration = MultiStepConfiguration.objects.get(
            id=configuration_id)
        treatment_plant, created = TreatmentPlant.objects.get_or_create(
            name=name,
            description=f"{name} for option {option}",
            option=option,
            configuration=configuration,
        )
        if created:
            # The treatment layout configuration is stored here.
            # It is determined by the treatment map stored in
            # the session
            for step_number, tech in treatment_map.items():
                tech_id = tech['technology']
                technology = Technology.objects.get(id=tech_id)
                _, _ = TreatmentPlantLayout.objects.get_or_create(
                    treatmentplant=treatment_plant,
                    step=step_number,
                    technology=technology
                )
        redirect_url = reverse(
            'design_detail',
            kwargs={'slug': treatment_plant.slug})
        return JsonResponse({'redirect_url': redirect_url})

    def form_valid(self, form):
        # session_key = self.request.session.session_key
        self.object = form.save()
        if self.request.user.is_authenticated:
            form.instance.user = self.request.user
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            option_id = form.cleaned_data.get('option')
            configuration = form.cleaned_data.get('configuration')
            plant_slug = TreatmentPlant.objects.get(
                option=option_id,
                configuration=configuration
            ).slug
            redirect_url = reverse(
                'design_detail',
                kwargs={'slug': plant_slug}
            )
            return JsonResponse({'redirect_url': redirect_url})

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'errors': form.errors}, status=400)
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse(
            'design_detail',
            kwargs={'slug': self.object.slug}
            )


class NamedDesignUpdateView(generic.UpdateView):
    model = TreatmentPlant
    form_class = TreatmentDesignSelectionForm
    template_name = 'drinq/form_edit-treatment-design-name.html'

    # def get_object(self):
    #     return get_object_or_404(
    #         TreatmentPlant,
    #         slug=self.kwargs.get('slug')
    #     )

    def get_success_url(self):
        return reverse(
            'design_detail',
            kwargs={'slug': self.object.slug})

    def form_valid(self, form):
        # Update the slug and description of the design option
        self.object = form.save(commit=False)
        option = self.request.POST.get('option', None)
        if option is None:
            form.clean()
            plant_id = getattr(self.object, 'id', None)
            if plant_id is not None:
                option = TreatmentPlant.objects.get(
                    id=plant_id).option
        if option:
            # Save the form and return a response
            # form.cleaned_data['option'] = option_number
            form.initial['option'] = option
            object_option = form.cleaned_data.get('option', None)
            if object_option is None:
                self.object.option = option
                self.object.save()
            response = super(NamedDesignUpdateView, self).form_valid(form)
            return response
        else:
            return JsonResponse({
                'error': 'Option number of the treatment plant is required.'},
                status=400)
            
    def post(self, request, *args, **kwargs):
        """Handle POST request to update the treatment design name."""
        self.object = self.get_object()
        form = self.get_form()
        form.full_clean()
        if form.is_valid():
            return self.form_valid(form)
        return self.form_invalid(form)


class TreatmentDesignDetailView(generic.DetailView):
    model = TreatmentPlantLayout
    template_name = 'drinq/treatmentdesign_details.html'

    def get_object(self):
        return get_object_or_404(
            TreatmentPlant,
            slug=self.kwargs.get('slug')
        )

    def get_context_data(self, **kwargs):
        context = {}
        treatment_layout = (
            TreatmentPlantLayout.objects
            .filter(treatmentplant=self.object)
            .select_related('technology')
            .order_by('step')
        )
        technologies = [
            layout.technology for layout in treatment_layout
            if layout.technology is not None
        ]
        adaptability_data = get_adaptability_scores_for_technologies(
            technologies)

        treatment_layout_with_adaptability = []
        criteria_coverage_notes = []
        adaptability_matrix_rows = []
        criteria = adaptability_data['criteria']
        for layout in treatment_layout:
            technology_id = layout.technology_id
            criteria_count = adaptability_data[
                'technology_criteria_counts'].get(technology_id, 0)
            criterion_score_map = adaptability_data[
                'technology_criterion_scores'].get(technology_id, {})
            treatment_layout_with_adaptability.append({
                'layout': layout,
                'adaptability_score': adaptability_data[
                    'technology_scores'].get(technology_id),
                'criteria_count': criteria_count,
            })
            criteria_coverage_notes.append({
                'step': layout.step,
                'technology_name': layout.technology.name,
                'criteria_count': criteria_count,
            })
            adaptability_matrix_rows.append({
                'step': layout.step,
                'technology_name': layout.technology.name,
                'criterion_scores': [
                    criterion_score_map.get(criterion['id'])
                    for criterion in criteria
                ],
                'average_score': adaptability_data[
                    'technology_scores'].get(technology_id),
            })

        context['treatment_plant'] = self.object
        context['treatment_layout'] = treatment_layout
        context['treatment_layout_with_adaptability'] = (
            treatment_layout_with_adaptability)
        context['adaptability_criteria'] = criteria
        context['criteria_coverage_notes'] = criteria_coverage_notes
        context['adaptability_matrix_rows'] = adaptability_matrix_rows
        context['plant_adaptability_score'] = adaptability_data['plant_score']
        context['adaptability_criteria_total'] = (
            adaptability_data['criteria_total'])
        return context


class DesignParameterInputView(generic.FormView):
    template_name = 'drinq/form_design-parameter-input.html'
    form_class = DesignParameterValueFormSet

    def get_treatment_plant(self):
        return get_object_or_404(TreatmentPlant, pk=self.kwargs['plant_id'])

    def get_treatment_technology_ids(self):
        treatment_plant = self.get_treatment_plant()
        return TreatmentPlantLayout.objects.filter(
            treatmentplant=treatment_plant
        ).values_list('technology', flat=True)

    def get_treatment_technology_names(self, technology_ids: list = None):
        if technology_ids is None:
            technology_ids = self.get_treatment_technology_ids()
        technology_names = []
        for technology_id in technology_ids:
            technology_names += Technology.objects.get(
                id=technology_id).name
        return technology_names

    def get_treatment_stage_ids(self, technology_ids: list = None):
        if technology_ids is None:
            technology_ids = self.get_treatment_technology_ids()
        stages = []
        if technology_ids is None:
            return stages
        for technology_id in technology_ids:
            stage = StageTechnologies.objects.filter(
                technology_id=technology_id)
            if len(stage) > 1:
                print("Multiple stages found for technology:", technology_id)
            stages += stage.values_list('stage', flat=True)
        return stages

    def get_treatment_stage_names(self, stages: list = None):
        if stages is None:
            stages = self.get_treatment_stage_ids()
        stage_names = []
        for stage_id in stages:
            try:
                stage_name = Stage.objects.get(id=stage_id).name
                stage_names += stage_name
            except Stage.DoesNotExist:
                raise Http404("Stage does not exist")
        return stage_names

    def get_form(self, form_class=None):
        treatment_plant = self.get_treatment_plant()
        design_parameters = DesignParameter.objects.all()
        # Ensure each parameter has a TreatmentplantDesignParameter instance
        for param in design_parameters:
            TreatmentplantDesignParameter.objects.get_or_create(
                treatmentplant=treatment_plant,
                designparameter=param,
                defaults={'value': 0}
            )
        queryset = TreatmentplantDesignParameter.objects.filter(
            treatmentplant=treatment_plant,
            designparameter__in=design_parameters
        )
        if self.request.method == 'POST':
            return DesignParameterValueFormSet(
                self.request.POST, queryset=queryset)
        return DesignParameterValueFormSet(queryset=queryset)

    def get_context_data(self, **kwargs):
        """Add treatment plant to context"""
        context = super().get_context_data(**kwargs)
        context['treatment_plant'] = self.get_treatment_plant()
        if 'formset' not in context:
            context['formset'] = self.get_form()
        return context

    def form_valid(self, formset):
        treatment_plant = self.get_treatment_plant()
        if not formset.is_valid():
            return self.form_invalid(formset)

        # Save every form explicitly to ensure values are persisted
        saved = []
        for form in formset.forms:
            # skip deleted forms if formset supports deletion
            if getattr(form, 'cleaned_data', None) is None:
                # bind cleaned_data if not already (safe because formset.is_valid() was True)
                form.full_clean()
            if form.cleaned_data.get('DELETE', False):
                # if deletion supported
                if form.instance.pk:
                    form.instance.delete()
                continue

            instance = form.save(commit=False)
            # ensure the FK is set
            if getattr(instance, 'treatmentplant', None) is None:
                instance.treatmentplant = treatment_plant
            instance.save()
            saved.append(instance)

        return redirect('technology_properties', plant_id=treatment_plant.id)

    def form_invalid(self, formset):
        """Handle invalid form"""
        return self.render_to_response(self.get_context_data(formset=formset))

    def post(self, request, *args, **kwargs):
        """Handle POST requests"""
        formset = self.get_form()
        if formset.is_valid():
            return self.form_valid(formset)
        return self.form_invalid(formset)


class DesignParameterResultsView(generic.DetailView):
    model = TreatmentPlant
    template_name = 'drinq/treatmentplant_property_results.html'
    pk_url_kwarg = 'plant_id'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        properties = (
            TreatmentPlantPropertyValue.objects
            .filter(treatmentplant=self.object)
            .select_related('property__category')
            .order_by('property__category__name', 'property__name')
        )

        properties_by_category = defaultdict(list)
        for prop_value in properties:
            category = getattr(prop_value.property, 'category', None)
            category_name = category.name if category else 'Uncategorized'
            properties_by_category[category_name].append(prop_value)

        context['properties_by_category'] = properties_by_category.items()

        # Gather technology KPIs for this treatment plant, grouped by
        # technology.
        tech_kpi_qs = TreatmentPlantTechnologyKPIValue.objects.filter(
            treatmentplant=self.object
        ).select_related('technology', 'kpi')

        # Group by technology
        tech_kpis = defaultdict(list)
        for kpi_value in tech_kpi_qs:
            tech_kpis[kpi_value.technology].append(kpi_value)

        # Get the ordered list of technologies by step from
        # TreatmentPlantLayout
        layout_qs = TreatmentPlantLayout.objects.filter(
            treatmentplant=self.object
        ).select_related('technology').order_by('step')
        ordered_techs = [
            layout.technology for layout in layout_qs
            if layout.technology is not None]
        adaptability_data = get_adaptability_scores_for_technologies(
            ordered_techs)

        # Build an ordered list of technology KPI blocks.
        technology_kpis_ordered = []
        for tech in ordered_techs:
            if tech in tech_kpis:
                technology_kpis_ordered.append({
                    'technology': tech,
                    'kpis': tech_kpis[tech],
                    'adaptability_score': adaptability_data[
                        'technology_scores'].get(tech.id),
                    'criteria_count': adaptability_data[
                        'technology_criteria_counts'].get(tech.id, 0),
                })

        context['technology_kpis_ordered'] = technology_kpis_ordered

        # --- Persist plant adaptability KPI as a TreatmentPlantPropertyValue ---
        adaptability_score = adaptability_data['plant_score']
        if adaptability_score is not None:
            adapt_prop, _ = TreatmentPlantProperty.objects.get_or_create(
                name="adaptability score",
                defaults={
                    'unit': '(0–1)',
                    'description': 'Average adaptability score across all technologies and criteria',
                },
            )
            TreatmentPlantPropertyValue.objects.update_or_create(
                treatmentplant=self.object,
                property=adapt_prop,
                defaults={'value': f"{adaptability_score:.4f}"},
            )

        context['plant_adaptability_score'] = adaptability_score
        context['adaptability_criteria_total'] = (
            adaptability_data['criteria_total'])
        return context


class AdaptabilityDetailView(generic.DetailView):
    model = TreatmentPlant
    template_name = 'drinq/adaptability_details.html'
    pk_url_kwarg = 'plant_id'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        treatment_layout = (
            TreatmentPlantLayout.objects
            .filter(treatmentplant=self.object)
            .select_related('technology')
            .order_by('step')
        )
        technologies = [
            layout.technology for layout in treatment_layout
            if layout.technology is not None
        ]
        adaptability_data = get_adaptability_scores_for_technologies(
            technologies)

        criteria = adaptability_data['criteria']
        matrix_rows = []
        for layout in treatment_layout:
            technology_id = layout.technology_id
            criterion_score_map = adaptability_data[
                'technology_criterion_scores'].get(technology_id, {})
            matrix_rows.append({
                'step': layout.step,
                'technology_name': layout.technology.name,
                'criterion_scores': [
                    criterion_score_map.get(criterion['id'])
                    for criterion in criteria
                ],
                'average_score': adaptability_data[
                    'technology_scores'].get(technology_id),
                'criteria_count': adaptability_data[
                    'technology_criteria_counts'].get(technology_id, 0),
            })

        context['treatment_plant'] = self.object
        context['adaptability_criteria'] = criteria
        context['adaptability_matrix_rows'] = matrix_rows
        context['plant_adaptability_score'] = adaptability_data['plant_score']
        context['adaptability_criteria_total'] = (
            adaptability_data['criteria_total'])
        return context


def index(request: HttpResponse):
    """Displays the index HTML page (index.html).

    Args:
        request (HttpResponse): http response object

    Returns:
        _type_: _description_
    """

    # return HttpResponse("Hello, world. You're at the drinq index.")
    return render(request, 'drinq/index.html')


class TechnologyPropertiesView(generic.FormView):
    """Collect technology-level property values (those flagged as
    design parameters). Persist them, run the performance calculator and
    redirect to the results page.
    """
    template_name = 'drinq/form_technology-properties.html'
    form_class = TreatmentPlantTechPropertyValueFormSet

    def get_treatment_plant(self):
        return get_object_or_404(TreatmentPlant, pk=self.kwargs['plant_id'])

    def get_form(self, form_class=None):
        treatment_plant = self.get_treatment_plant()
        tech_ids = TreatmentPlantLayout.objects.filter(
            treatmentplant=treatment_plant).values_list(
                'technology', flat=True)
        
        non_digested_prop_ids = TechnologyPropertyJunction.objects.filter(
            technology__in=tech_ids, is_digested=False
        ).values_list('property', flat=True)
        queryset = TreatmentPlantTechnologyPropertyValue.objects.filter(
            treatmentplant=treatment_plant,
            technologyproperty_id__in=non_digested_prop_ids
        )
        initial = []
        if not queryset.exists():
            # Build initial data for new forms, but do NOT include 'id'
            initial = build_technology_property_initials(treatment_plant)

        prefix = "techprop"
        if self.request.method == 'POST':
            total_forms = int(self.request.POST.get(f'{prefix}-TOTAL_FORMS', '0'))
            DynamicFormSet = modelformset_factory(
                TreatmentPlantTechnologyPropertyValue,
                form=TreatmentTechPropertyValueForm,
                extra=total_forms,
            )
            formset = DynamicFormSet(
                self.request.POST,
                queryset=queryset,
                initial=initial,
                prefix=prefix)
            return formset
        # For GET: if queryset is empty and initial is non-empty, set extra
        if not queryset.exists() and initial:
            DynamicFormSet = modelformset_factory(
                TreatmentPlantTechnologyPropertyValue,
                form=TreatmentTechPropertyValueForm,
                extra=len(initial),
            )
            return DynamicFormSet(
                queryset=queryset, initial=initial, prefix=prefix)
        return TreatmentPlantTechPropertyValueFormSet(
            queryset=queryset, initial=initial, prefix=prefix)

    def get_waterquality_formset(self):
        """Return a formset for water quality parameter values for this plant."""
        treatment_plant = self.get_treatment_plant()
        tech_ids = TreatmentPlantLayout.objects.filter(
            treatmentplant=treatment_plant).values_list('technology', flat=True)
        wqtech_junctions = WaterqualityParameterTechnologyJunction.objects.filter(
            technology__in=tech_ids
        ).select_related('waterqualityparameter')
        qs = TreatmentPlantWaterQualityParameterValue.objects.filter(
            treatmentplant=treatment_plant,
            wq_tech_parameter_id__in=[j.id for j in wqtech_junctions]
        )
        existing_ids = set(
            qs.values_list('wq_tech_parameter_id', flat=True))
        for junction in wqtech_junctions:
            if junction.id not in existing_ids:
                TreatmentPlantWaterQualityParameterValue.objects.create(
                    treatmentplant=treatment_plant,
                    wq_tech_parameter=junction,
                    value=junction.default_value
                )
        qs = TreatmentPlantWaterQualityParameterValue.objects.filter(
            treatmentplant=treatment_plant,
            wq_tech_parameter_id__in=[j.id for j in wqtech_junctions]
        )
        prefix = "waterquality"
        try:
            if self.request.method == 'POST':
                return WaterQualityParameterValueFormSet(
                    self.request.POST, queryset=qs, prefix=prefix)
            return WaterQualityParameterValueFormSet(
                queryset=qs, prefix=prefix)
        except Exception as e:
            logger.error("Exception in get_waterquality_formset: %s", e, exc_info=True)
            raise

    def form_valid(self, formset):
        treatment_plant = self.get_treatment_plant()
        waterquality_formset = self.get_waterquality_formset()
        valid_tech = formset.is_valid()
        valid_wq = waterquality_formset.is_valid()
        if not (valid_tech and valid_wq):
            logger.warning(
                "Formset or waterquality_formset invalid. formset errors: %s, waterquality_formset errors: %s", formset.errors, waterquality_formset.errors)
            return self.form_invalid(formset)

        # Step 1: Save all form data
        saved = []
        for form in formset.forms:
            if getattr(form, 'cleaned_data', None) is None:
                form.full_clean()
            if not form.cleaned_data or form.cleaned_data.get('DELETE', False):
                continue
            instance = form.save(commit=False)
            if getattr(instance, 'treatmentplant', None) is None:
                instance.treatmentplant = treatment_plant
            instance.save()
            saved.append(instance)
        # Save water quality parameter values
        for form in waterquality_formset.forms:
            if getattr(form, 'cleaned_data', None) is None:
                form.full_clean()
            if not form.cleaned_data:
                continue
            instance = form.save(commit=False)
            if getattr(instance, 'treatmentplant', None) is None:
                instance.treatmentplant = treatment_plant
            instance.save()
            saved.append(instance)

        # Step 2: Calculate technology-specific and plant-wide KPIs
        # - gather technologies and stages
        # - build design parameter dict
        # - run TreatmentPlantPerformanceCalculator and
        #   TechnologyPerformanceCalculator
        # - save calculated values to the DB

        # Run performance calculations after tech properties saved
        # gather technologies and stages
        tech_ids = TreatmentPlantLayout.objects.filter(
            treatmentplant=treatment_plant).values_list(
                'technology', flat=True)
        technology_names = [
            Technology.objects.get(id=t).name for t in tech_ids]

        stage_ids = StageTechnologies.objects.filter(
            technology__in=tech_ids).values_list('stage', flat=True).distinct()
        stage_names = [Stage.objects.get(id=s).name for s in stage_ids]

        # build design parameter dict
        design_parameters = {
            dp.designparameter.name: dp.value
            for dp in TreatmentplantDesignParameter.objects.filter(
                treatmentplant=treatment_plant)
        }
        tech_chem_objects = TechnologyChemicalagentJunction.objects
        chemical_agents = [
            cap.chemical_agent for cap in tech_chem_objects.filter(
                technology__in=tech_ids
            ).select_related('chemical_agent').distinct()
        ]
        chemicalagent_parameters = {
            tech_name: {
                c_agent.name: {
                    'price': ChemicalagentPrice.objects.get(
                        chemical_agent=c_agent).default_value
                    if ChemicalagentPrice.objects.filter(
                        chemical_agent=c_agent).exists() else None,
                    'emission_factor': None,
                }
                for c_agent in chemical_agents
                if TechnologyChemicalagentJunction.objects.filter(
                    technology__name=tech_name, chemical_agent=c_agent).exists()
            } for tech_name in technology_names
        }
        dwtp = dac.TreatmentPlantPerformanceCalculator(
            treatmentplant_id=treatment_plant.id,
            stages=stage_names,
            technologies=technology_names,
            design_parameters=design_parameters,
            waterquality_parameters={},  # to be filled in by tech calculator
            plant_kpis={},
            db_kpi_mapping=DB_PLANTKPI_MAPPING,
            chemicalagent_parameters=chemicalagent_parameters
        )
        # Step 2a: set the nominal flow
        # -----------------------------------------------------     
        if dwtp.nominal_flow_m3perhr.value is None:
            dwtp.update_nominal_flow_m3perhr()
            dwtp.update_plant_kpis()  # to set nominal flow KPI
        wq_parameters = {
            tech: {} for tech in technology_names}

        # Step 2b: initialize technology-dependent calculations
        # ----------------------------------------------------
        # The technology_properties dictionary contains the property values
        # for each technology in the treatment plant.
        tech_properties = {}
        defaultval_tech_props = {}
        digested_tech_prop_names = {}
        all_tech_properties = TechnologyProperty.objects.all()
        for tech_id in tech_ids:
            technology = Technology.objects.get(id=tech_id)
            tech_properties[technology.name] = {}
            wq_parameters[technology.name] = {}
            digested_tech_prop_names[technology.name] = []
            defaultval_tech_props[technology.name] = {}
            for wq_input in WaterqualityParameterTechnologyJunction.objects.filter(  # noqa, E501
                        technology=technology,
                        is_inputparameter=True,
                        is_targetparameter=False):
                wq_p = WaterqualityParameterData(
                    name=wq_input.waterqualityparameter.name,
                    input_label=INPUT_WQPARAMETER_KEY,
                    input_value=wq_input.default_value)
                wq_parameters[technology.name] = wq_p.to_dict()
            for wq_target in WaterqualityParameterTechnologyJunction.objects.filter(  # noqa, E501
                        technology=technology,
                        is_inputparameter=False,
                        is_targetparameter=True):
                if wq_target:
                    wq_name = wq_target.waterqualityparameter.name
                    wq_inputvalue, wq_inputdict = None, {}
                    if wq_parameters[technology.name].get(wq_name, None) is not None:  # noqa, E501
                        wq_inputdict = wq_parameters[technology.name][wq_name]
                        wq_inputvalue = wq_inputdict.get(
                            INPUT_WQPARAMETER_KEY, None)
                    # if there is already an input parameter with the same
                    # name, we want to keep its value and label, otherwise
                    # fill the dict with the target parameter's default value
                    wq_p = WaterqualityParameterData(
                        name=wq_name,
                        target_label=TARGET_WQPARAMETER_KEY,
                        target_value=wq_target.default_value,
                        input_value=wq_inputvalue,
                        input_label=INPUT_WQPARAMETER_KEY)
                    wq_parameters[technology.name].update(wq_p.to_dict())

            # Technology property default value lookup
            for def_tp in TechnologyPropertyJunction.objects.filter(
                        technology=technology, is_designparameter=False):
                if all_tech_properties.get(id=def_tp.property.id).parent_property is None:  # noqa, E501
                    defaultval_tech_props[technology.name].update(
                        {def_tp.property.name: def_tp.default_value})
            for isdigested_tp in TechnologyPropertyJunction.objects.filter(
                        technology=technology, is_digested=True):
                digested_tech_prop_names[technology.name] += [isdigested_tp.property.name]  # noqa, E501
            for tp in TreatmentPlantTechnologyPropertyValue.objects.filter(
                        treatmentplant=treatment_plant,
                        technology=Technology.objects.get(id=tech_id)
                    ):
                tech_properties[tp.technology.name].update(
                    {tp.technologyproperty.name: tp.value})
        # Merge the default values with the user-specified properties
        for tech_name in technology_names:
            tech_properties[tech_name] = {
                **defaultval_tech_props[tech_name],
                **tech_properties[tech_name]
            }
        technology_kpis = [
            tech_kpi.name for tech_kpi in TechnologyKPI.objects.all()]

        # Instantiate the Technology Performance Calculator
        kpi_calculator = dac.TechnologyPerformanceCalculator(
            treatmentplant_id=treatment_plant.id,
            stages=stage_names,
            technologies=technology_names,
            design_parameters=design_parameters,
            tech_parameters=tech_properties,
            waterquality_parameters=wq_parameters,
            chemicalagent_parameters=chemicalagent_parameters,
            plant_kpis=dwtp.plant_kpis,
            tech_kpinames=technology_kpis,
            digested_tech_parameter_list=digested_tech_prop_names,
        )
        kpi_calculator.calculate_kpi()
        kpi_calculator.sum_kpis()
        
        # Assign the summed technology KPIs to the plant calculator
        summed_kpis = kpi_calculator.summed_kpis
        dwtp.energyconsumption_kwhrperday.value = summed_kpis.get(  # noqa, E501
            TECHKPI_ENERGYCONSUMPTION_KWHRPERDAY, None)
        dwtp.energyconsumption_kwhrperm3.value = dwtp.get_energyconsumption_per_m3()  # noqa, E501
        dwtp.power_kw.value = summed_kpis.get(
            TECHKPI_POWER_KW, None)
        dwtp.co2_emissions_kgperm3.value = summed_kpis.get(  # noqa, E501
            TECHKPI_CO2_EMISSIONS_KGPERM3, None)
        dwtp.footprint_area_m2.value = summed_kpis.get(
            TECHKPI_FOOTPRINT_AREA_M2, None)

        # Save the digested technology properties back to the database
        for tech_name in technology_names:
            for prop_name in kpi_calculator.digested_tech_parameter_list[tech_name]:  # noqa, E501
                try:
                    prop_value = kpi_calculator.tech_parameters[tech_name][prop_name]  # noqa, E501
                    tech = Technology.objects.get(name=tech_name)
                    prop_obj = TechnologyProperty.objects.get(name=prop_name)
                    TreatmentPlantTechnologyPropertyValue.objects.update_or_create(  # noqa, E501
                        treatmentplant=treatment_plant,
                        technology=tech,
                        technologyproperty=prop_obj,
                        defaults={'value': str(prop_value)}
                    )
                except TechnologyProperty.DoesNotExist:
                    continue
            # save KPI values
            for (kpi_name, kpi_value) in (
                    kpi_calculator.tech_kpis[tech_name].items()):
                try:
                    kpi = TechnologyKPI.objects.get(name=kpi_name)
                    tech = Technology.objects.get(name=tech_name)
                    if kpi_value is None:
                        logger.warning(
                            f"-- None value found for technology: {tech.name}, KPI: {kpi.name}")
                        continue
                    TreatmentPlantTechnologyKPIValue.objects.update_or_create(  # noqa, E501
                        treatmentplant=treatment_plant,
                        technology=tech,
                        kpi=kpi,
                        defaults={'value': str(kpi_value)}
                        )
                except TechnologyKPI.DoesNotExist:
                    continue

        # Step 2c: compute plant-wide costs
        # ---------------------------------
        dwtp.update_plant_kpis()
        # compute construction costs if possible (replicate existing helper)
        constrcosts = {}
        for tech_id in tech_ids:
            related_tech_id = None
            try:
                related_technology = TechnologyRelatedtechnology.objects.get(technology_id=tech_id)
                related_tech_id = related_technology.id
            except TechnologyRelatedtechnology.DoesNotExist:
                related_technology = None
            try:
                tccp = TechnologyConstructionCostParameter.objects.filter(
                    technology_id=tech_id).first()
                if tccp:
                    if tccp.technologyproperty:
                        try:
                            techprop_value = TreatmentPlantTechnologyPropertyValue.objects.get(  # noqa, E501
                                treatmentplant=treatment_plant,
                                technology_id=tech_id,
                                technologyproperty=tccp.technologyproperty
                            ).value
                        except TreatmentPlantTechnologyPropertyValue.DoesNotExist:  # noqa, E501
                            # TODO: raise the error in future versions
                            logger.warning(
                                f"Missing TreatmentPlantTechnologyPropertyValue"  # noqa, E501
                                f" for technology_id={tech_id} and "
                                f"technologyproperty={tccp.technologyproperty} in "  # noqa, E501
                                f"construction cost calculation"
                            )
                            techprop_value = None
                        if techprop_value is None:
                            continue
                        constrcosts[Technology.objects.get(id=tech_id).name] = {
                            'a': tccp.a, 'b': tccp.b, 'c': tccp.c,
                            'technologyproperty': tccp.technologyproperty.name,
                            'technologyproperty_value': techprop_value,
                            'plantproperty': None,
                            'plantproperty_value': None,
                        }
                    else:
                        if tccp.plantproperty:
                            try:
                                plantprop_value = dwtp.plant_kpis.get(  # noqa, E501
                                    tccp.plantproperty.name, None)
                            except TreatmentPlantProperty.DoesNotExist:
                                plantprop_value = None
                            if plantprop_value is None:
                                logger.warning(
                                    f"Missing value of plant KPI {tccp.plantproperty.name}"  # noqa, E501
                                    f" for construction cost calculation ")
                                continue
                            constrcosts[Technology.objects.get(id=tech_id).name] = {  # noqa, E501
                                'a': tccp.a, 'b': tccp.b, 'c': tccp.c,
                                'technologyproperty': None,
                                'technologyproperty_value': None,
                                'plantproperty': tccp.plantproperty.name,
                                'plantproperty_value': plantprop_value
                            }
            except TechnologyConstructionCostParameter.DoesNotExist:
                logger.warning(
                    f"No construction cost parameters found for "
                    f"technology_id={tech_id}"
                    )
                continue
            # Now try the same for the related technology
            if related_tech_id is not None:
                try:
                    tccp = TechnologyConstructionCostParameter.objects.filter(
                        technology_id=related_tech_id).first()
                    if tccp:
                        if tccp.technologyproperty:
                            try:
                                techprop_value = TreatmentPlantTechnologyPropertyValue.objects.get(  # noqa, E501
                                    treatmentplant=treatment_plant,
                                    technology_id=related_tech_id,
                                    technologyproperty=tccp.technologyproperty
                                ).value
                            except TreatmentPlantTechnologyPropertyValue.DoesNotExist:  # noqa, E501
                                # TODO: raise the error in future versions
                                logger.warning(
                                    f"Missing TreatmentPlantTechnologyPropertyValue"  # noqa, E501
                                    f" for technology_id={related_tech_id} and "
                                    f"technologyproperty={tccp.technologyproperty} in "  # noqa, E501
                                    f"construction cost calculation"
                                )
                                warn(
                                    f"Missing TreatmentPlantTechnologyPropertyValue"  # noqa, E501
                                    f" for technology_id={related_tech_id} and "
                                    f"technologyproperty={tccp.technologyproperty}"
                                    )
                                techprop_value = None
                            if techprop_value is None:
                                continue
                            constrcosts[Technology.objects.get(id=related_tech_id).name] = {
                                'a': tccp.a, 'b': tccp.b, 'c': tccp.c,
                                'technologyproperty': tccp.technologyproperty.name,
                                'technologyproperty_value': techprop_value,
                                'plantproperty': None,
                                'plantproperty_value': None,
                            }
                        else:
                            if tccp.plantproperty:
                                try:
                                    plantprop_value = dwtp.plant_kpis.get(  # noqa, E501
                                        tccp.plantproperty.name, None)
                                except TreatmentPlantProperty.DoesNotExist:
                                    plantprop_value = None
                                if plantprop_value is None:
                                    logger.warning(
                                        f"Missing value of plant KPI {tccp.plantproperty.name}"  # noqa, E501
                                        f" for construction cost calculation ")
                                    continue
                                constrcosts[Technology.objects.get(id=related_tech_id).name] = {  # noqa, E501
                                    'a': tccp.a, 'b': tccp.b, 'c': tccp.c,
                                    'technologyproperty': None,
                                    'technologyproperty_value': None,
                                    'plantproperty': tccp.plantproperty.name,
                                    'plantproperty_value': plantprop_value
                                }
                except TechnologyConstructionCostParameter.DoesNotExist:
                    logger.warning(
                        f"No construction cost parameters found for "
                        f"technology_id={related_tech_id}"
                        )
                    continue
        try:
            dwtp.set_constructioncosts(cost_parameters=constrcosts)
        except KeyError as ke:
            # TODO: raise the error in future versions
            # perf_indic.update({TPPN['construction_costs_eurperm3']: None})
            logger.warning(
                f"KeyError during construction cost calculation: {ke}. ")  # noqa, E501

        # Calculate investment, maintenance and levelized costs
        oper_and_maintenance_rate = dwtp.design_parameters.get(
            DESIGN_PAR_OPERATION_MAINTENANCE_PERC_NAME, 5) / 100
        lifespan = dwtp.design_parameters.get(
            DESIGN_PAR_LIFESPAN_NAME, None)
        interest_rate = dwtp.design_parameters.get(
            DESIGN_PAR_INTEREST_PERC_NAME, None
        ) / 100
        personnel_costs_year = dwtp.design_parameters.get(
            DESIGN_PAR_PERSONNEL_COSTS_NAME, None
        )
        energy_price = dwtp.design_parameters.get(
            DESIGN_PAR_ENERGY_PRICE_NAME, None
        )
        energy_costs_year = (
            dwtp.energyconsumption_kwhrperday.value * 365 * energy_price
        )
        chemical_costs_per_day = summed_kpis.get(
            TECHKPI_DAILY_CHEMICAL_COSTS_EUR_PER_DAY,
            0.0,
        )
        chemical_costs_per_year = chemical_costs_per_day * 365
        yearly_production_m3 = dwtp.nominal_flow_m3perhr.value * 24 * 365
        dwtp.oper_and_maintenancecosts_eurperyear.value = dwtp.oper_and_maintenancecosts_eurperyear.calculate_value(
            construction_costs=dwtp.constructioncosts_eur.value,
            oper_maintenance_percentage=oper_and_maintenance_rate,
        )
        dwtp.investmentcosts_eur.value = dwtp.investmentcosts_eur.calculate_value(
            construction_costs_total=dwtp.constructioncosts_eur.value,
            operation_maintenance_percentage=oper_and_maintenance_rate,
            energy_cost_per_year=energy_costs_year,
            personnel_costs_per_year=personnel_costs_year,
            chemical_costs_per_year=chemical_costs_per_year,
            interest_rate=interest_rate,
            lifespan_years=lifespan,
        )
        dwtp.levelized_cost_of_water.value = dwtp.levelized_cost_of_water.calculate_value(
            total_investment_costs_peryear=dwtp.investmentcosts_eur.value,
            yearly_water_production_m3=yearly_production_m3,
        )
        dwtp.levelized_chemical_costs.value = dwtp.levelized_chemical_costs.calculate_value(
            chemical_costs_per_year=chemical_costs_per_year,
            yearly_water_production_m3=yearly_production_m3,
        )

        # Step 2-d: update plant-wide properties (KPIs)
        # --------------------------------------------
        dwtp.update_plant_kpis()  # update cost related KPIs
        for prop_name, val in dwtp.plant_kpis.items():
            value = np.round(val, 3)
            if val is None:
                continue
            prop_obj, _ = TreatmentPlantProperty.objects.get_or_create(name=prop_name)  # noqa, E501
            TreatmentPlantPropertyValue.objects.update_or_create(
                treatmentplant=treatment_plant,
                property=prop_obj,
                defaults={'value': str(value)}
            )

        # Step 3: Prepare and POST to the API
        tech_props = []
        for form in formset.forms:
            if getattr(form, 'cleaned_data', None) is None:
                form.full_clean()
            if not form.cleaned_data or form.cleaned_data.get('DELETE', False):
                continue
            instance = form.save(commit=False)
            tech_props.append({
                'technology': instance.technology.id,
                'technologyproperty': instance.technologyproperty.id,
                'value': instance.value,
            })

        return redirect(
            'design_parameter_results', plant_id=treatment_plant.id)
        
        # payload = {
        #     'treatmentplant_id': treatment_plant.id,
        #     'configuration_id': getattr(treatment_plant, 'configuration_id', None),
        #     'technology_properties': tech_props,
        # }

        # api_url = reverse('api_process_parameters')
        # if not api_url.startswith('http'):
        #     api_url = settings.SITE_URL.rstrip('/') + api_url

        # try:
        #     response = requests.post(api_url, json=payload, cookies=self.request.COOKIES)
        #     if response.status_code == 200:
        #         data = response.json()
        #         redirect_url = data.get('redirect_url')
        #         if redirect_url:
        #             return HttpResponseRedirect(redirect_url)
        #         else:
        #             self.add_error(None, 'No redirect URL returned from API.')
        #     else:
        #         self.add_error(None, f'API error: {response.status_code} {response.text}')
        # except Exception as e:
        #     self.add_error(None, f'API request failed: {e}')

        # return self.form_invalid(formset)

    def form_invalid(self, formset):
        # Ensure waterquality_formset is POST-bound for error display
        waterquality_formset = self.get_waterquality_formset()
        # Debug logging for errors
        print("=== form_invalid called ===")
        print("formset.errors:", formset.errors)
        print("formset.non_form_errors:", formset.non_form_errors())
        print("waterquality_formset.errors:", waterquality_formset.errors)
        print("waterquality_formset.non_form_errors:", waterquality_formset.non_form_errors())
        return self.render_to_response(self.get_context_data(
            formset=formset, waterquality_formset=waterquality_formset))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        treatment_plant = self.get_treatment_plant()
        formset = context.get('form') or self.get_form()
        waterquality_formset = self.get_waterquality_formset()

        # Build ordered technologies from TreatmentPlantLayout (by step)
        layouts = TreatmentPlantLayout.objects.filter(
            treatmentplant=treatment_plant).order_by('step').select_related('technology')
        tech_order = [lay.technology for lay in layouts]

        # Map tech id to Technology instance
        tech_map = {tech.id: tech for tech in tech_order}

        # Group forms by technology id preserving order
        forms_by_tech = OrderedDict()
        for tech in tech_order:
            forms_by_tech[tech] = []

        # For each form in the formset, determine its technology and attach
        # the form along with the human-readable property name
        for idx, form in enumerate(formset.forms):
            tech_id = None
            if getattr(form.instance, 'technology', None):
                tech_id = form.instance.technology.id
            else:
                tech_id = form.initial.get('technology')
            prop_id = None
            if getattr(form.instance, 'technologyproperty', None):
                prop_id = form.instance.technologyproperty.id
            else:
                prop_id = form.initial.get('technologyproperty')
            tech = tech_map.get(tech_id)
            prop_name = None
            prop_unit = None
            prop_help = None
            if prop_id:
                try:
                    prop = TechnologyProperty.objects.get(id=prop_id)
                    prop_name = prop.name
                    prop_unit = prop.unit
                    prop_help = prop.description
                except TechnologyProperty.DoesNotExist:
                    prop_name = str(prop_id)
            if tech is not None:
                forms_by_tech[tech].append({
                    'form': form,
                    'prop_name': prop_name,
                    'prop_unit': prop_unit,
                    'prop_help': prop_help,
                })

        # Group water quality parameter forms by technology
        # Build a mapping: {Technology: [form, ...]}
        waterquality_forms_by_tech = OrderedDict(
            (tech, []) for tech in tech_order)
        # Build a mapping from parameter id to technology ids (from WaterqualityParameterTechnologyJunction)
        wqp_tech_map = {}
        for junction in WaterqualityParameterTechnologyJunction.objects.filter(technology__in=tech_order):
            tid = junction.technology.id
            pid = junction.waterqualityparameter.id
            wqp_tech_map.setdefault(pid, set()).add(tid)
        # Assign forms to technologies
        for form in waterquality_formset.forms:
            param = getattr(form.instance, 'wq_tech_parameter', None)
            if param is not None:
                tech = param.technology
                if tech is not None:
                    waterquality_forms_by_tech[tech].append(form)

        context['forms_by_tech'] = forms_by_tech
        context['treatment_plant'] = treatment_plant
        context['formset'] = formset
        context['waterquality_formset'] = waterquality_formset
        context['waterquality_forms_by_tech'] = waterquality_forms_by_tech

        # --- Build waterquality_params_by_tech for new table rendering ---
        # Use technology id as key for grouping, then map back to tech 
        # instance for template
        wq_params_by_techid = {}
        for tech in tech_order:
            param_map = defaultdict(lambda: {
                'untreated': None,
                'target': None,
                'description': '',
                'unit': ''
                })
            forms = waterquality_forms_by_tech.get(tech, [])
            for form in forms:
                junction = getattr(form.instance, 'wq_tech_parameter', None)
                if not junction:
                    continue
                param = getattr(junction, 'waterqualityparameter', None)
                if not param:
                    continue
                name = param.name
                desc = param.description or ''
                unit = param.unit or ''
                is_input = getattr(junction, 'is_inputparameter', False)
                is_target = getattr(junction, 'is_targetparameter', False)
                value = form['value']
                if is_input:
                    param_map[name]['untreated'] = value
                if is_target:
                    param_map[name]['target'] = value
                param_map[name]['description'] = desc
                param_map[name]['unit'] = unit
            param_list = []
            for pname, pdata in param_map.items():
                param_list.append({
                    'name': pname,
                    'untreated': pdata['untreated'],
                    'target': pdata['target'],
                    'description': pdata['description'],
                    'unit': pdata['unit'],
                })
            wq_params_by_techid[tech.id] = param_list
        # Now build OrderedDict with tech instance as key for template
        waterquality_params_by_tech = OrderedDict()
        for tech in tech_order:
            waterquality_params_by_tech[tech] = wq_params_by_techid.get(
                tech.id, [])
        context['waterquality_params_by_tech'] = waterquality_params_by_tech
        # --- End new context variable ---
        return context


def db_stats(request: HttpResponse):
    """Puts database statistics in a dictionary. The corresponding HTML
    template is `db_stats.html`.

    Args:
        request (HttpResponse): http response object.

    Returns:
        Dict[str, Any]: dictionary with database statistics (counts, etc.)
    """
    num_compounds = Compound.objects.all().count()
    num_technologies = Technology.objects.all().count()

    context = {
        'num_compounds': num_compounds,
        'num_technologies': num_technologies,
    }
    return render(request, 'drinq/db_stats.html', context=context)


def compound_search(request: HttpResponse):
    pass


def compound_detail(request, cid):
    try:
        compound = Compound.objects.get(cid=cid)
    except Compound.DoesNotExist as err:
        raise Http404("Compound does not exist") from err
    try:
        cas_list = CompoundCas.objects.filter(cid=cid)
    except CompoundCas.DoesNotExist:
        cas_list = None

    svg_compound = smiles_to_svg(smiles=compound.isomeric_smiles)

    context = {'cid': compound.cid,
               'common_name': compound.common_name,
               'isomeric_smiles': compound.isomeric_smiles,
               'cas_list': cas_list,
               'svg_image': svg_compound,
               }
    return render(request, 'drinq/compound/detail.html', context)
