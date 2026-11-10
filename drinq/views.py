 
from django.shortcuts import render, redirect, get_object_or_404

from collections import OrderedDict, defaultdict
import json
import csv
import hashlib
import subprocess
import shutil
import os
import threading
import uuid
from pathlib import Path
from datetime import datetime

import logging
import numpy as np
import pystimela
from pystimela_optim.scripts import run_all_optimizations
from pystimela_optim.api import optimize_process
from pystimela_optim.scripts.coag_floc_prepare_config import (
    generate_config_from_csv as prepare_coag_floc_config,
)
from pystimela_optim.scripts.filtration_prepare_config import (
    generate_config_from_csv as prepare_filtration_config,
)
from pystimela_optim.scripts.dual_filtration_prepare_config import (
    generate_config_from_csv as prepare_dual_filtration_config,
)
from pystimela_optim.scripts.gac_prepare_config import (
    generate_config_from_csv as prepare_gac_config,
)
from pystimela_optim.scripts.chlorination_prepare_config import (
    generate_config_from_csv as prepare_chlorination_config,
)
from pystimela_optim.scripts.ozonation_prepare_config import (
    generate_config_from_csv as prepare_ozonation_config,
)
from pystimela_optim.scripts.coag_floc_optim_update import (
    update_wq_from_results as update_coag_floc_wq,
)
from pystimela_optim.scripts.filtration_optim_update import (
    update_wq_from_results as update_filtration_wq,
)
from pystimela_optim.scripts.dual_filtration_optim_update import (
    update_wq_from_results as update_dual_filtration_wq,
)
from pystimela_optim.scripts.gac_optim_update import (
    update_wq_from_results as update_gac_wq,
)
from pystimela_optim.scripts.chlorination_optim_update import (
    update_wq_from_results as update_chlorination_wq,
)
from pystimela_optim.scripts.ozonation_optim_update import (
    update_wq_from_results as update_ozonation_wq,
)
from warnings import warn
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache

from django.http import (
    HttpResponse, Http404, HttpResponseRedirect, JsonResponse,
    )
from django.views import generic
from django.forms import ValidationError, modelformset_factory
from django.urls import reverse
from django.db.models import Avg, Count
from django.db import (
    IntegrityError,
    transaction,
    connection,
    close_old_connections,
)
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
    TreatmentPlantTechnologyOptimizationStatus,
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
    TreatmentPlantComparisonForm,
    TreatmentDesignSelectionForm,
    DesignParameterValueFormSet,
    TreatmentPlantTechPropertyValueFormSet,
    TreatmentTechPropertyValueForm,
    WaterQualityParameterValueFormSet,
    build_technology_property_initials,
    )
from drinq.chemistry_tools import smiles_to_svg
from drinq.access import user_can_access_plant
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


class TreatmentPlantAccessMixin(LoginRequiredMixin):
    """Limit a plant page to the owner of its configuration and staff.

    The plant is resolved from the ``plant_id`` or ``slug`` URL kwarg. Other
    users get a 404, so the existence of a plant is not disclosed.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if 'plant_id' in kwargs:
            plant = get_object_or_404(TreatmentPlant, pk=kwargs['plant_id'])
        else:
            plant = get_object_or_404(TreatmentPlant, slug=kwargs['slug'])
        if not user_can_access_plant(request.user, plant):
            raise Http404('Treatment plant does not exist.')
        return super().dispatch(request, *args, **kwargs)


def _optimizer_status_cache_key(plant_id, user_id):
    return f'optimizer_status:plant:{plant_id}:user:{user_id}'


@login_required
def optimizer_status(request, plant_id):
    plant = get_object_or_404(TreatmentPlant, pk=plant_id)
    if not user_can_access_plant(request.user, plant):
        raise Http404('Treatment plant does not exist.')
    user_id = getattr(request.user, 'id', 0)
    cache_key = _optimizer_status_cache_key(plant_id, user_id)
    status = cache.get(cache_key) or {
        'state': 'idle',
        'message': '',
        'updated_rows': [],
        'progress': {},
        'completed_processes': [],
        'action': '',
    }
    return JsonResponse(status)


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


class SessionSelectView(LoginRequiredMixin, generic.edit.FormView):
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


def _dedupe_ids(technology_ids: list[int]) -> list[int]:
    deduped: list[int] = []
    for technology_id in technology_ids:
        if technology_id not in deduped:
            deduped.append(technology_id)
    return deduped


def _build_choice_buckets(technology_ids: tuple[int, ...]) -> list[list[int]]:
    """Build the stage buckets contributed by a single deciding-factor
    choice: an optional previous-step bucket, the current stage's
    technology alternatives (all kept together in one bucket), and an
    optional next-step bucket.
    """
    tech_related_objs = TechnologyRelatedtechnology.objects
    previous_ids: list[int] = []
    next_ids: list[int] = []
    for technology_id in technology_ids:
        related_tech_previous = tech_related_objs.filter(
            technology_id=technology_id,
            relatedtechnology_is_previousstep=True,
        ).first()
        if related_tech_previous is not None:
            related_id = related_tech_previous.related_technology_id
            if related_id not in previous_ids:
                previous_ids.append(related_id)

        related_tech_next = tech_related_objs.filter(
            technology_id=technology_id,
            relatedtechnology_is_nextstep=True,
        ).first()
        if related_tech_next is not None:
            related_id = related_tech_next.related_technology_id
            if related_id not in next_ids:
                next_ids.append(related_id)

    choice_buckets: list[list[int]] = []
    if previous_ids:
        choice_buckets.append(previous_ids)
    choice_buckets.append(_dedupe_ids(list(technology_ids)))
    if next_ids:
        choice_buckets.append(next_ids)
    return choice_buckets


def _append_stage_buckets(
    stage_buckets: list[list[int]],
    choice_buckets: list[list[int]],
) -> list[list[int]]:
    """Append a choice's buckets to the running, in-order stage sequence.

    A bucket that exactly repeats the immediately preceding one is
    skipped (e.g. a next-step bucket already introduced by an earlier
    choice's current or previous bucket). Genuine repeats that occur
    later in the sequence are preserved as their own buckets.
    """
    for bucket in choice_buckets:
        if stage_buckets and stage_buckets[-1] == bucket:
            continue
        stage_buckets.append(bucket)
    return stage_buckets


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


class QuestionsCompleteView(LoginRequiredMixin, generic.TemplateView):
    template_name = "drinq/form_complete.html"

    def _get_configuration_or_404(
            self,
            *,
            session_key: str | None = None,
            configuration_id: int | None = None) -> MultiStepConfiguration:
        queryset = MultiStepConfiguration.objects
        if self.request.user.is_authenticated:
            queryset = queryset.filter(user=self.request.user)

        if session_key is not None:
            queryset = queryset.filter(session_key=session_key)
        if configuration_id is not None:
            queryset = queryset.filter(id=configuration_id)

        try:
            return queryset.get()
        except MultiStepConfiguration.DoesNotExist:
            raise Http404('Configuration does not exist.')

    def dispatch(self, request, *args, **kwargs):
        session_key = kwargs.get('session_key', None)
        session = request.session
        if session_key is None:
            session_key = session.get('session_key', None)
        if session_key is not None:
            configuration = self._get_configuration_or_404(
                session_key=session_key)
            session['configuration_id'] = configuration.id
            session['session_key'] = configuration.session_key
        return super().dispatch(request, *args, **kwargs)

    def get(self, request: HttpResponse, *args, **kwargs):
        session_key = kwargs.get('session_key', None)
        configuration = self._get_configuration_or_404(session_key=session_key)
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
        configuration = self._get_configuration_or_404(
            configuration_id=config_id)
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
            stage_buckets: list[list[int]] = []
            for choice in choices:
                if choice is not None:
                    choice_description = dst.get_choice_description(
                        choice=choice, query_set=None)
                    if choice_description is not None:
                        context['choices'].update({choice: choice_description})
                    technology_ids = dst.get_technology_of_choice(
                        choice=choice)
                    if technology_ids:
                        stage_buckets = _append_stage_buckets(
                            stage_buckets,
                            _build_choice_buckets(technology_ids),
                        )

            technologies = stage_buckets
            context['technologies'] = [tuple(bucket) for bucket in technologies]
            treatment_options, treatment_maps = dst.get_treatment_trains(
                technology_tuples=context['technologies'])

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


class NamedDesignCreateView(LoginRequiredMixin, generic.CreateView):
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
        configuration = get_object_or_404(
            MultiStepConfiguration, id=configuration_id, user=request.user)
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


class NamedDesignUpdateView(TreatmentPlantAccessMixin, generic.UpdateView):
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


class TreatmentDesignDetailView(TreatmentPlantAccessMixin, generic.DetailView):
    model = TreatmentPlantLayout
    template_name = 'drinq/treatmentdesign_details.html'

    def get_object(self):
        return get_object_or_404(
            TreatmentPlant,
            slug=self.kwargs.get('slug')
        )

    def get_context_data(self, **kwargs):
        context = {}
        has_plant_kpi_results = TreatmentPlantPropertyValue.objects.filter(
            treatmentplant=self.object,
        ).exists()
        has_technology_kpi_results = (
            TreatmentPlantTechnologyKPIValue.objects.filter(
                treatmentplant=self.object,
            ).exists()
        )
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
        context['has_kpi_results'] = (
            has_plant_kpi_results or has_technology_kpi_results
        )
        return context


class DesignParameterInputView(TreatmentPlantAccessMixin, generic.FormView):
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
                defaults={'value': param.defaultvalue}
            )
        queryset = TreatmentplantDesignParameter.objects.filter(
            treatmentplant=treatment_plant,
            designparameter__in=design_parameters
        ).select_related('designparameter')
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


class DesignParameterResultsView(TreatmentPlantAccessMixin, generic.DetailView):
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

        # Group by technology id so the display can follow the treatment
        # layout order while still showing the same KPI set per technology.
        tech_kpis_by_id = defaultdict(list)
        for kpi_value in tech_kpi_qs:
            tech_kpis_by_id[kpi_value.technology_id].append(kpi_value)

        # Get the ordered list of technologies by step from
        # TreatmentPlantLayout.
        layout_qs = TreatmentPlantLayout.objects.filter(
            treatmentplant=self.object
        ).select_related('technology').order_by('step')
        ordered_layouts = [layout for layout in layout_qs if layout.technology]

        ordered_techs = []
        seen_technology_ids = set()
        for layout in ordered_layouts:
            tech_id = layout.technology_id
            if tech_id in seen_technology_ids:
                continue
            ordered_techs.append(layout.technology)
            seen_technology_ids.add(tech_id)

        adaptability_data = get_adaptability_scores_for_technologies(ordered_techs)

        # Build an ordered list of technology KPI blocks.
        technology_kpis_ordered = []
        for layout in ordered_layouts:
            tech = layout.technology
            tech_kpis = tech_kpis_by_id.get(layout.technology_id, [])
            if tech_kpis:
                technology_kpis_ordered.append({
                    'step': layout.step,
                    'technology': tech,
                    'kpis': tech_kpis,
                    'kpi_count': len(tech_kpis),
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


class DesignParameterResultsExportCsvView(TreatmentPlantAccessMixin, generic.View):
    """Export treatment plant KPI results to CSV."""

    def get(self, request, *args, **kwargs):
        treatment_plant = get_object_or_404(
            TreatmentPlant,
            pk=kwargs.get('plant_id'),
        )

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = (
            'attachment; '
            f'filename="treatmentplant_kpis_{treatment_plant.id}.csv"'
        )

        writer = csv.writer(response)
        writer.writerow([
            'section',
            'category_or_step',
            'technology',
            'kpi_or_property',
            'value',
            'unit',
        ])

        plant_properties = (
            TreatmentPlantPropertyValue.objects
            .filter(treatmentplant=treatment_plant)
            .select_related('property__category')
            .order_by('property__category__name', 'property__name')
        )

        for property_value in plant_properties:
            category = getattr(property_value.property, 'category', None)
            category_name = category.name if category else 'Uncategorized'
            writer.writerow([
                'plant',
                category_name,
                '',
                property_value.property.name,
                property_value.value,
                property_value.property.unit or '',
            ])

        tech_kpi_qs = (
            TreatmentPlantTechnologyKPIValue.objects
            .filter(treatmentplant=treatment_plant)
            .select_related('technology', 'kpi')
        )
        tech_kpis = defaultdict(list)
        for kpi_value in tech_kpi_qs:
            tech_kpis[kpi_value.technology_id].append(kpi_value)

        layouts = (
            TreatmentPlantLayout.objects
            .filter(treatmentplant=treatment_plant)
            .select_related('technology')
            .order_by('step')
        )

        for layout in layouts:
            if layout.technology_id is None:
                continue
            for kpi_value in tech_kpis.get(layout.technology_id, []):
                writer.writerow([
                    'technology',
                    f'Step {layout.step}',
                    layout.technology.name,
                    kpi_value.kpi.name,
                    kpi_value.value,
                    kpi_value.kpi.unit or '',
                ])

        return response


class TreatmentPlantComparisonView(LoginRequiredMixin, generic.FormView):
    template_name = 'drinq/treatmentplant_compare.html'
    form_class = TreatmentPlantComparisonForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        if self.request.GET:
            kwargs['data'] = self.request.GET
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        left_plant_id = self.request.GET.get('left_plant')
        right_plant_id = self.request.GET.get('right_plant')
        if left_plant_id:
            initial['left_plant'] = left_plant_id
        if right_plant_id:
            initial['right_plant'] = right_plant_id
        return initial

    def _build_properties_by_category(
        self,
        left_plant: TreatmentPlant,
        right_plant: TreatmentPlant,
    ):
        left_values = {
            prop_value.property_id: prop_value
            for prop_value in (
                TreatmentPlantPropertyValue.objects
                .filter(treatmentplant=left_plant)
                .select_related('property__category')
            )
        }
        right_values = {
            prop_value.property_id: prop_value
            for prop_value in (
                TreatmentPlantPropertyValue.objects
                .filter(treatmentplant=right_plant)
                .select_related('property__category')
            )
        }

        property_ids = set(left_values.keys()) | set(right_values.keys())
        properties = (
            TreatmentPlantProperty.objects
            .filter(id__in=property_ids)
            .select_related('category')
            .order_by('category__name', 'name')
        )

        properties_by_category = defaultdict(list)
        for property_obj in properties:
            category = getattr(property_obj, 'category', None)
            category_name = category.name if category else 'Uncategorized'
            left_prop = left_values.get(property_obj.id)
            right_prop = right_values.get(property_obj.id)
            properties_by_category[category_name].append({
                'property': property_obj,
                'left_value': (
                    left_prop.value if left_prop is not None else None
                ),
                'right_value': (
                    right_prop.value if right_prop is not None else None
                ),
            })
        return properties_by_category.items()

    def _to_float(self, value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            try:
                return float(stripped)
            except ValueError:
                try:
                    return float(stripped.replace(',', '.'))
                except ValueError:
                    return None
        return None

    def _build_category_radar_payload(
        self,
        properties_by_category,
        left_plant_name: str,
        right_plant_name: str,
    ):
        labels = []
        left_scores = []
        right_scores = []

        for category_name, category_rows in properties_by_category:
            left_normalized_values = []
            right_normalized_values = []

            for row in category_rows:
                left_value = self._to_float(row.get('left_value'))
                right_value = self._to_float(row.get('right_value'))

                if left_value is None and right_value is None:
                    continue

                left_abs = abs(left_value) if left_value is not None else 0.0
                right_abs = (
                    abs(right_value) if right_value is not None else 0.0
                )
                largest_value = max(left_abs, right_abs)
                axis_max = largest_value if largest_value > 0 else 1.0

                left_normalized_values.append(
                    (left_value if left_value is not None else 0.0) / axis_max
                )
                right_normalized_values.append(
                    (
                        right_value if right_value is not None else 0.0
                    ) / axis_max
                )

            if not left_normalized_values and not right_normalized_values:
                continue

            labels.append(str(category_name).capitalize())
            left_scores.append(
                round(float(np.mean(left_normalized_values)), 3)
                if left_normalized_values else 0.0
            )
            right_scores.append(
                round(float(np.mean(right_normalized_values)), 3)
                if right_normalized_values else 0.0
            )

        return {
            'labels': labels,
            'left_label': left_plant_name,
            'right_label': right_plant_name,
            'left_data': left_scores,
            'right_data': right_scores,
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context['form']

        context['left_plant'] = None
        context['right_plant'] = None
        context['properties_by_category'] = []

        if form.is_bound and form.is_valid():
            left_plant = form.cleaned_data.get('left_plant')
            right_plant = form.cleaned_data.get('right_plant')
            context['left_plant'] = left_plant
            context['right_plant'] = right_plant
            if left_plant is not None and right_plant is not None:
                properties_by_category = list(
                    self._build_properties_by_category(
                        left_plant=left_plant,
                        right_plant=right_plant,
                    )
                )
                context['properties_by_category'] = properties_by_category
                radar_payload = self._build_category_radar_payload(
                    properties_by_category=properties_by_category,
                    left_plant_name=left_plant.name,
                    right_plant_name=right_plant.name,
                )
                context['show_radar_chart'] = len(radar_payload['labels']) > 0
                context['radar_chart_data_json'] = json.dumps(radar_payload)
        return context


class TechnologyParameterOverviewSelectionView(
    LoginRequiredMixin, generic.TemplateView
):
    """Show treatment designs that can be opened in the technology overview."""

    template_name = 'drinq/technology_parameter_overview_select.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = (
            TreatmentPlant.objects
            .select_related('configuration')
            .order_by('configuration__name', 'option', 'name')
        )
        if self.request.user.is_authenticated:
            queryset = queryset.filter(configuration__user=self.request.user)
        context['treatment_plants'] = queryset
        return context


class TechnologyParameterOverviewView(
    TreatmentPlantAccessMixin, generic.DetailView
):
    """Read-only overview of technology properties and water quality values."""

    model = TreatmentPlant
    template_name = 'drinq/technology_parameter_overview.html'
    pk_url_kwarg = 'plant_id'

    def _get_chemicalagent_emission_factors(
        self,
        chemical_agent_ids: list[int],
    ) -> dict[int, dict[str, float | str | None]]:
        if not chemical_agent_ids:
            return {}

        table_names = connection.introspection.table_names()
        if 'chemicalagent_emissionfactor' not in table_names:
            return {}

        placeholders = ','.join(['%s'] * len(chemical_agent_ids))
        sql = (
            'SELECT chemicalagent, co2_emissionfactor, emissionfactor_unit '
            'FROM chemicalagent_emissionfactor '
            f'WHERE chemicalagent IN ({placeholders})'
        )
        with connection.cursor() as cursor:
            cursor.execute(sql, chemical_agent_ids)
            rows = cursor.fetchall()

        return {
            int(chemicalagent_id): {
                'value': co2_emissionfactor,
                'unit': emissionfactor_unit,
            }
            for (
                chemicalagent_id,
                co2_emissionfactor,
                emissionfactor_unit,
            ) in rows
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        treatment_plant = self.object

        layouts = list(
            TreatmentPlantLayout.objects
            .filter(treatmentplant=treatment_plant)
            .select_related('technology')
            .order_by('step')
        )
        technology_ids = [
            layout.technology_id
            for layout in layouts
            if layout.technology_id is not None
        ]

        value_rows = TreatmentPlantTechnologyPropertyValue.objects.filter(
            treatmentplant=treatment_plant,
            technology_id__in=technology_ids,
        )
        value_map = {
            (row.technology_id, row.technologyproperty_id): row.value
            for row in value_rows
        }

        junctions = list(
            TechnologyPropertyJunction.objects
            .filter(
                technology_id__in=technology_ids,
                property__parent_property__isnull=True,
            )
            .select_related('technology', 'property')
            .order_by('technology_id', 'property__name')
        )
        properties_by_technology = defaultdict(list)
        technology_chemical_emission_factors = {}
        for junction in junctions:
            stored_value = value_map.get(
                (junction.technology_id, junction.property_id)
            )
            resolved_value = (
                stored_value
                if stored_value is not None
                else junction.default_value
            )
            value_source = (
                'Stored value'
                if stored_value is not None
                else 'Default value'
            )

            if junction.is_designparameter and junction.is_digested:
                parameter_type = 'User-specified and calculated'
                parameter_type_short = 'User-specified'
            elif junction.is_designparameter:
                parameter_type = 'User-specified design parameter'
                parameter_type_short = 'User-specified'
            elif junction.is_digested:
                parameter_type = 'Calculated by application'
                parameter_type_short = 'Calculated'
            else:
                parameter_type = 'Fixed technology parameter'
                parameter_type_short = 'Fixed'
            is_fixed_parameter = (
                not junction.is_designparameter
                and not junction.is_digested
            )

            if junction.property.name == TPN['chemical_emission_factor']:
                technology_chemical_emission_factors[
                    junction.technology_id
                ] = {
                    'value': resolved_value,
                    'source': value_source,
                    'unit': junction.property.unit,
                }
                continue

            properties_by_technology[junction.technology_id].append({
                'name': junction.property.name,
                'description': junction.property.description,
                'unit': junction.property.unit,
                'is_designparameter': junction.is_designparameter,
                'is_digested': junction.is_digested,
                'value': resolved_value,
                'value_source': value_source,
                'parameter_type': parameter_type,
                'parameter_type_short': parameter_type_short,
                'is_fixed_parameter': is_fixed_parameter,
            })

        technology_chemicalagent_junctions = list(
            TechnologyChemicalagentJunction.objects
            .filter(technology_id__in=technology_ids)
            .select_related('chemical_agent')
            .order_by('technology_id', 'chemical_agent__name')
        )
        chemical_agent_ids = sorted({
            row.chemical_agent_id
            for row in technology_chemicalagent_junctions
            if row.chemical_agent_id is not None
        })

        default_price_rows = ChemicalagentPrice.objects.filter(
            chemical_agent_id__in=chemical_agent_ids,
        )
        default_price_map = {
            row.chemical_agent_id: {
                'value': row.default_value,
                'unit': row.units,
            }
            for row in default_price_rows
        }

        plant_price_rows = (
            TreatmentPlantChemicalagentPriceJunction.objects
            .filter(
                treatmentplant=treatment_plant,
                chemicalagent_id__in=chemical_agent_ids,
            )
        )
        plant_price_map = {
            row.chemicalagent_id: row.price
            for row in plant_price_rows
        }

        chemicalagent_emission_factor_map = (
            self._get_chemicalagent_emission_factors(chemical_agent_ids)
        )

        chemical_agents_by_technology = defaultdict(list)
        for junction in technology_chemicalagent_junctions:
            if junction.chemical_agent is None:
                continue

            default_price = default_price_map.get(junction.chemical_agent_id)
            stored_price = plant_price_map.get(junction.chemical_agent_id)
            if stored_price is not None:
                price_value = stored_price
                price_source = 'Stored value'
            elif default_price is not None:
                price_value = default_price.get('value')
                price_source = 'Default value'
            else:
                price_value = None
                price_source = None

            emission_factor = chemicalagent_emission_factor_map.get(
                junction.chemical_agent_id,
                {},
            )
            technology_emission_factor = (
                technology_chemical_emission_factors.get(
                    junction.technology_id,
                )
            )
            if technology_emission_factor is not None:
                emission_factor_value = technology_emission_factor.get('value')
                emission_factor_unit = technology_emission_factor.get('unit')
                emission_factor_source = 'Technology-specific'
            else:
                emission_factor_value = emission_factor.get('value')
                emission_factor_unit = emission_factor.get('unit')
                if emission_factor_value is not None:
                    emission_factor_source = 'Plant-wide fallback'
                else:
                    emission_factor_source = None

            chemical_agents_by_technology[junction.technology_id].append({
                'name': junction.chemical_agent.name,
                'description': junction.chemical_agent.description,
                'price_value': price_value,
                'price_source': price_source,
                'price_unit': (
                    default_price.get('unit')
                    if default_price is not None
                    else None
                ),
                'emission_factor': emission_factor_value,
                'emission_factor_source': emission_factor_source,
                'emission_factor_unit': emission_factor_unit,
            })

        wq_junctions = list(
            WaterqualityParameterTechnologyJunction.objects
            .filter(technology_id__in=technology_ids)
            .select_related('waterqualityparameter')
            .order_by('technology_id', 'waterqualityparameter__name')
        )
        wq_value_rows = (
            TreatmentPlantWaterQualityParameterValue.objects.filter(
                treatmentplant=treatment_plant,
                wq_tech_parameter_id__in=[
                    junction.id
                    for junction in wq_junctions
                ],
            )
        )
        wq_value_map = {
            row.wq_tech_parameter_id: row.value
            for row in wq_value_rows
        }

        water_quality_by_technology = defaultdict(dict)
        for junction in wq_junctions:
            parameter = junction.waterqualityparameter
            per_tech = water_quality_by_technology[junction.technology_id]
            if parameter.id not in per_tech:
                per_tech[parameter.id] = {
                    'name': parameter.name,
                    'description': parameter.description,
                    'unit': parameter.unit,
                    'input_value': None,
                    'input_source': None,
                    'target_value': None,
                    'target_source': None,
                }

            stored_value = wq_value_map.get(junction.id)
            resolved_value = (
                stored_value
                if stored_value is not None
                else junction.default_value
            )
            value_source = (
                'Stored value'
                if stored_value is not None
                else 'Default value'
            )

            if junction.is_inputparameter:
                per_tech[parameter.id]['input_value'] = resolved_value
                per_tech[parameter.id]['input_source'] = value_source
            if junction.is_targetparameter:
                per_tech[parameter.id]['target_value'] = resolved_value
                per_tech[parameter.id]['target_source'] = value_source

        technology_sections = []
        for layout in layouts:
            if layout.technology is None:
                continue
            technology_sections.append({
                'step': layout.step,
                'technology': layout.technology,
                'property_rows': properties_by_technology.get(
                    layout.technology_id,
                    [],
                ),
                'water_quality_rows': sorted(
                    water_quality_by_technology.get(
                        layout.technology_id,
                        {},
                    ).values(),
                    key=lambda row: row['name'].lower(),
                ),
                'chemical_agent_rows': chemical_agents_by_technology.get(
                    layout.technology_id,
                    [],
                ),
            })

        context['technology_sections'] = technology_sections
        context['treatment_plant'] = treatment_plant
        return context


class DesignParameterOverviewView(
    TreatmentPlantAccessMixin, generic.DetailView
):
    """Read-only overview of plant-wide design parameter values."""

    model = TreatmentPlant
    template_name = 'drinq/design_parameter_overview.html'
    pk_url_kwarg = 'plant_id'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        treatment_plant = self.object

        parameter_rows = list(
            TreatmentplantDesignParameter.objects
            .filter(treatmentplant=treatment_plant)
            .select_related('designparameter', 'designparameter__category')
            .order_by('designparameter__name')
        )

        design_parameter_rows = []
        for parameter_row in parameter_rows:
            design_parameter = parameter_row.designparameter
            if design_parameter is None:
                continue

            stored_value = parameter_row.value
            resolved_value = (
                stored_value
                if stored_value is not None
                else design_parameter.defaultvalue
            )

            category_name = None
            if design_parameter.category is not None:
                category_name = design_parameter.category.name

            design_parameter_rows.append({
                'name': design_parameter.name,
                'category': category_name,
                'description': design_parameter.description,
                'unit': design_parameter.unit,
                'value': resolved_value,
                'value_source': (
                    'Stored value'
                    if stored_value is not None
                    else 'Default value'
                ),
            })

        context['design_parameter_rows'] = design_parameter_rows
        context['treatment_plant'] = treatment_plant
        return context


class AdaptabilityDetailView(TreatmentPlantAccessMixin, generic.DetailView):
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


class TechnologyPropertiesView(TreatmentPlantAccessMixin, generic.FormView):
    """Collect technology-level property values (those flagged as
    design parameters). Persist them, run the performance calculator and
    redirect to the results page.
    """
    template_name = 'drinq/form_technology-properties.html'
    form_class = TreatmentPlantTechPropertyValueFormSet

    def _get_treatment_plant_technology_ids(self, treatment_plant):
        return list(
            TreatmentPlantLayout.objects.filter(
                treatmentplant=treatment_plant
            ).values_list('technology', flat=True)
        )

    def _has_optimizer_targets(self, treatment_plant):
        tech_ids = self._get_treatment_plant_technology_ids(treatment_plant)
        if not tech_ids:
            return False
        return (
            TechnologyPropertyJunction.objects.filter(
                technology__in=tech_ids,
                sent_to_optimizer=True,
            ).exists()
            or WaterqualityParameterTechnologyJunction.objects.filter(
                technology__in=tech_ids,
                sent_to_optimizer=True,
            ).exists()
        )

    def _build_optimizer_payload(self, treatment_plant):
        tech_ids = self._get_treatment_plant_technology_ids(treatment_plant)
        flagged_tech_props = list(
            TechnologyPropertyJunction.objects
            .filter(technology__in=tech_ids, sent_to_optimizer=True)
            .select_related('technology', 'property')
            .order_by('technology_id', 'property__name')
        )
        flagged_wq_junctions = list(
            WaterqualityParameterTechnologyJunction.objects
            .filter(technology__in=tech_ids, sent_to_optimizer=True)
            .select_related('technology', 'waterqualityparameter')
            .order_by('technology_id', 'waterqualityparameter__name')
        )

        tech_prop_values = {
            (row.technology_id, row.technologyproperty_id): row.value
            for row in TreatmentPlantTechnologyPropertyValue.objects.filter(
                treatmentplant=treatment_plant,
                technology_id__in=tech_ids,
            )
        }
        wq_values = {
            row.wq_tech_parameter_id: row.value
            for row in TreatmentPlantWaterQualityParameterValue.objects.filter(
                treatmentplant=treatment_plant,
                wq_tech_parameter_id__in=[j.id for j in flagged_wq_junctions],
            )
        }

        payload = {
            'treatment_plant': {
                'id': treatment_plant.id,
                'name': treatment_plant.name,
                'slug': treatment_plant.slug,
            },
            'generated_at': timezone.now().isoformat(),
            'technology_properties': [],
            'waterquality_parameters': [],
        }

        for junction in flagged_tech_props:
            payload['technology_properties'].append({
                'technology_id': junction.technology_id,
                'technology_name': junction.technology.name,
                'technologyproperty_id': junction.property_id,
                'technologyproperty_name': junction.property.name,
                'unit': junction.property.unit,
                'value': tech_prop_values.get(
                    (junction.technology_id, junction.property_id),
                    junction.default_value,
                ),
                'source_table': 'technology_property',
            })

        for junction in flagged_wq_junctions:
            wq_parameter = junction.waterqualityparameter
            payload['waterquality_parameters'].append({
                'junction_id': junction.id,
                'technology_id': junction.technology_id,
                'technology_name': junction.technology.name,
                'waterqualityparameter_id': wq_parameter.id,
                'waterqualityparameter_name': wq_parameter.name,
                'unit': wq_parameter.unit,
                'is_inputparameter': junction.is_inputparameter,
                'is_targetparameter': junction.is_targetparameter,
                'value': wq_values.get(junction.id, junction.default_value),
                'source_table': 'waterqualityparameter_technology',
            })

        return payload

    def _write_optimizer_payload(self, treatment_plant, payload=None):
        output_dir = (
            Path(settings.BASE_DIR)
            / 'research'
            / 'data'
            / 'processed'
            / 'optimizer_inputs'
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = (
            output_dir
            / f'treatmentplant_{treatment_plant.id}_optimization_input.json'
        )

        if payload is None:
            payload = self._build_optimizer_payload(treatment_plant)
        with output_path.open('w', encoding='utf-8') as fp:
            json.dump(payload, fp, indent=2)

        return output_path

    def _optimizer_workspace_root(self):
        return (
            Path(settings.BASE_DIR)
            / 'research'
            / 'pystimela_optim'
        )

    def _optimizer_required_script_stems(self):
        return [
            'coag_floc_prepare_config',
            'coag_floc_optim',
            'coag_floc_optim_update',
            'filtration_prepare_config',
            'filtration_optim',
            'filtration_optim_update',
            'dual_filtration_prepare_config',
            'dual_filtration_optim',
            'dual_filtration_optim_update',
            'gac_prepare_config',
            'gac_optim',
            'gac_optim_update',
            'chlorination_prepare_config',
            'chlorination_optim',
            'chlorination_optim_update',
            'ozonation_prepare_config',
            'ozonation_optim',
            'ozonation_optim_update',
            'run_all_optimizations',
        ]

    def _ensure_optimizer_script_wrappers(self, workspace_root):
        scripts_dir = workspace_root / 'scripts'
        scripts_dir.mkdir(parents=True, exist_ok=True)
        init_path = scripts_dir / '__init__.py'
        if not init_path.exists():
            init_path.write_text('', encoding='utf-8')

        for stem in self._optimizer_required_script_stems():
            target = scripts_dir / f'{stem}.py'
            wrapper_code = (
                'import runpy\n\n'
                'if __name__ == "__main__":\n'
                '    runpy.run_module('
                f'"pystimela_optim.scripts.{stem}", run_name="__main__")\n'
            )
            if target.exists():
                existing = target.read_text(encoding='utf-8')
                if existing == wrapper_code:
                    continue
            target.write_text(wrapper_code, encoding='utf-8')

    def _optimizer_status_key(self, treatment_plant_id):
        user_id = getattr(self.request.user, 'id', 0)
        return _optimizer_status_cache_key(treatment_plant_id, user_id)

    def _set_optimizer_status(self, treatment_plant_id, payload):
        cache.set(
            self._optimizer_status_key(treatment_plant_id),
            payload,
            timeout=60 * 60 * 6,
        )

    def _get_optimizer_status(self, treatment_plant_id):
        status = cache.get(self._optimizer_status_key(treatment_plant_id))
        if status is None:
            return {
                'state': 'idle',
                'message': '',
                'updated_rows': [],
                'progress': {},
                'completed_processes': [],
                'action': '',
            }
        return status

    def _mark_optimizer_status_seen(self, treatment_plant_id):
        status = self._get_optimizer_status(treatment_plant_id)
        if status.get('state') == 'done' and not status.get('seen', False):
            status['seen'] = True
            self._set_optimizer_status(treatment_plant_id, status)

    def _sanitize_optimizer_key(self, value):
        if value is None:
            return ''
        return ''.join(
            c.lower() if c.isalnum() else '_'
            for c in str(value)
        ).strip('_')

    def _infer_enabled_optimizer_processes(self, payload):
        tech_names = {
            row.get('technology_name', '')
            for row in payload.get('technology_properties', [])
        }
        tech_names.update(
            row.get('technology_name', '')
            for row in payload.get('waterquality_parameters', [])
        )

        process_order = [
            'coagulation-flocculation',
            'filtration_single',
            'filtration_dual',
            'gac',
            'chlorination',
            'ozonation',
        ]
        enabled = set()
        for technology_name in tech_names:
            process_key = dac.get_optimizer_process_key_for_technology(
                technology_name
            )
            if process_key:
                enabled.add(process_key)

        return [proc for proc in process_order if proc in enabled]

    def _write_optimizer_csv_inputs(self, treatment_plant, payload):
        workspace_root = self._optimizer_workspace_root()
        inputs_dir = workspace_root / 'inputs'
        outputs_dir = workspace_root / 'outputs'
        configs_dir = workspace_root / 'configs'
        inputs_dir.mkdir(parents=True, exist_ok=True)
        outputs_dir.mkdir(parents=True, exist_ok=True)
        configs_dir.mkdir(parents=True, exist_ok=True)

        enabled_processes = self._infer_enabled_optimizer_processes(payload)
        enabled_path = outputs_dir / 'enabled_processes.json'
        with enabled_path.open('w', encoding='utf-8') as fp:
            json.dump({'enabled': enabled_processes}, fp, indent=2)

        canonical_wq_keys = {
            'flow': ('flow', 'm3/h', 100.0),
            'temperature': ('temperature', 'degC', 12.0),
            'doc': ('DOC', 'mg/L', 3.0),
            'ammonia': ('ammonia', 'mg/L', 0.05),
            'ph': ('pH', '-', 7.0),
            'uv254': ('uv254', '1/m', 0.1),
            'bromide': ('bromide', 'mg/L', 0.02),
            'suspended_solids': ('suspended_solids', 'mg/L', 5.0),
            'conductivity': ('conductivity', 'mS/m', 300.0),
            'm_number': ('m-number', 'mmol/L', 0.0),
            'bromate': ('bromate', 'ug/L', 1.0),
            'ecoli': ('ecoli', 'cfu/100mL', 0.0),
            'aoc': ('AOC', 'ug/L', 30.0),
        }
        input_wq = {
            canonical: {'value': default_value, 'unit': default_unit}
            for _, (canonical, default_unit, default_value) in (
                canonical_wq_keys.items()
            )
        }

        wq_aliases = {
            'doc': 'doc',
            'dissolved organic carbon': 'doc',
            'ph': 'ph',
            'p_h': 'ph',
            'tss': 'suspended_solids',
            'total suspended solids': 'suspended_solids',
            'm number': 'm_number',
            'm-number': 'm_number',
            'mnumber': 'm_number',
            'suspended solids': 'suspended_solids',
            'suspended_solids': 'suspended_solids',
        }

        def _normalize_wq_name(name):
            normalized = ''.join(
                c.lower() if c.isalnum() else ' '
                for c in str(name)
            )
            normalized = ' '.join(normalized.split())
            if normalized in wq_aliases:
                normalized = wq_aliases[normalized]
            return normalized

        process_input_wq = {
            process_key: {}
            for process_key in enabled_processes
        }
        fallback_input_wq = {}

        for row in payload.get('waterquality_parameters', []):
            if not row.get('is_inputparameter', False):
                continue
            name = row.get('waterqualityparameter_name')
            if not name:
                continue
            normalized_name = _normalize_wq_name(name)
            canonical_tuple = canonical_wq_keys.get(normalized_name)
            if canonical_tuple is None:
                continue
            canonical_name, default_unit, _ = canonical_tuple
            process_key = dac.get_optimizer_process_key_for_technology(
                row.get('technology_name', '')
            )
            input_payload = {
                'value': row.get('value'),
                'unit': row.get('unit') or default_unit,
            }
            if process_key in process_input_wq:
                process_input_wq[process_key][canonical_name] = input_payload
            fallback_input_wq.setdefault(canonical_name, input_payload)

        selected_input_keys = set()
        if enabled_processes:
            first_process = enabled_processes[0]
            for canonical_name, input_payload in process_input_wq.get(
                first_process, {}
            ).items():
                input_wq[canonical_name] = input_payload
                selected_input_keys.add(canonical_name)

        for canonical_name, input_payload in fallback_input_wq.items():
            if canonical_name in selected_input_keys:
                continue
            input_wq[canonical_name] = input_payload

        nominal_flow = (
            TreatmentPlantPropertyValue.objects
            .filter(
                treatmentplant=treatment_plant,
                property__name__iexact=KPI_NOMINAL_FLOW_M3PERH,
            )
            .values_list('value', flat=True)
            .first()
        )
        if nominal_flow is not None:
            input_wq['flow'] = {
                'value': float(nominal_flow),
                'unit': canonical_wq_keys['flow'][1],
            }

        in_wq_path = configs_dir / 'in_wq_params.json'
        in_wq_payload = {
            'treatment_plant_id': treatment_plant.id,
            'timestamps': [0.0, 60.0, 120.0],
            'WQ_parameters': input_wq,
            'wq_parameters': input_wq,
        }
        with in_wq_path.open('w', encoding='utf-8') as fp:
            json.dump(in_wq_payload, fp, indent=2)

        process_csv_map = {
            'coagulation-flocculation': (
                inputs_dir / 'config_coagulation_flocculation.csv'
            ),
            'filtration_single': inputs_dir / 'config_filtration_single.csv',
            'filtration_dual': inputs_dir / 'config_filtration_dual.csv',
            'gac': inputs_dir / 'config_gac.csv',
            'chlorination': inputs_dir / 'config_chlorination.csv',
            'ozonation': inputs_dir / 'config_ozonation.csv',
        }

        process_rows = {proc: [] for proc in enabled_processes}
        for process_key in enabled_processes:
            for section, parameter, value in dac.get_optimizer_csv_defaults(
                process_key
            ):
                process_rows[process_key].append(
                    {
                        'section': section,
                        'parameter': parameter,
                        'value': value,
                    }
                )

        for row in payload.get('technology_properties', []):
            process_key = dac.get_optimizer_process_key_for_technology(
                row.get('technology_name', '')
            )
            if process_key not in process_rows:
                continue
            technology = Technology.objects.filter(
                name__iexact=row.get('technology_name', '')
            ).first()
            prop_name = row.get('technologyproperty_name', '')
            mapping = dac.resolve_optimizer_csv_mapping(
                technology=technology,
                process_key=process_key,
                source_kind='technology_properties',
                source_name=prop_name,
            )
            if mapping is None:
                logger.info(
                    'No optimizer CSV mapping for process=%s property=%s; '
                    'falling back to model_parameters.',
                    process_key,
                    prop_name,
                )
                mapping = (
                    'model_parameters',
                    self._sanitize_optimizer_key(prop_name),
                )
            if not mapping[1]:
                continue
            process_rows[process_key].append(
                {
                    'section': mapping[0],
                    'parameter': mapping[1],
                    'value': row.get('value'),
                }
            )

        for row in payload.get('waterquality_parameters', []):
            process_key = dac.get_optimizer_process_key_for_technology(
                row.get('technology_name', '')
            )
            if process_key not in process_rows:
                continue
            technology = Technology.objects.filter(
                name__iexact=row.get('technology_name', '')
            ).first()
            wq_name = row.get('waterqualityparameter_name', '')
            mapping = dac.resolve_optimizer_csv_mapping(
                technology=technology,
                process_key=process_key,
                source_kind='waterquality_parameters',
                source_name=wq_name,
            )
            if mapping is None:
                logger.info(
                    'No optimizer CSV mapping for process=%s wq=%s; '
                    'falling back to constraints.',
                    process_key,
                    wq_name,
                )
                mapping = (
                    'constraints',
                    self._sanitize_optimizer_key(wq_name),
                )
            if not mapping[1]:
                continue
            process_rows[process_key].append(
                {
                    'section': mapping[0],
                    'parameter': mapping[1],
                    'value': row.get('value'),
                }
            )

        for process_key, csv_path in process_csv_map.items():
            if process_key not in enabled_processes:
                continue
            rows = process_rows.get(process_key, [])
            if not rows:
                rows = [
                    {
                        'section': 'metadata',
                        'parameter': 'treatment_plant_id',
                        'value': treatment_plant.id,
                    }
                ]
            with csv_path.open('w', encoding='utf-8', newline='') as fp:
                writer = csv.writer(fp)
                writer.writerow(['section', 'parameter', 'value'])
                for csv_row in rows:
                    writer.writerow(
                        [
                            csv_row['section'],
                            csv_row['parameter'],
                            csv_row['value'],
                        ]
                    )

        # Prepare shared baseline/support files expected by prepare scripts.
        timestamps_dir = inputs_dir / 'timestamps'
        timestamps_dir.mkdir(parents=True, exist_ok=True)
        timestamp_files = [
            'coagulation_flocculation.csv',
            'filtration_single.csv',
            'filtration_dual.csv',
            'gac.csv',
            'chlorination.csv',
            'ozonation.csv',
        ]
        for filename in timestamp_files:
            t_path = timestamps_dir / filename
            if not t_path.exists():
                with t_path.open('w', encoding='utf-8', newline='') as fp:
                    writer = csv.writer(fp)
                    writer.writerow(['time_s'])
                    writer.writerow([0])
                    writer.writerow([60])
                    writer.writerow([120])

        plant_design_path = inputs_dir / 'django_plant_design.csv'
        with plant_design_path.open('w', encoding='utf-8', newline='') as fp:
            writer = csv.writer(fp, delimiter=';')
            writer.writerow(['parameters', 'value'])
            writer.writerow(['n_years', 40])
            writer.writerow(['r_nom', 0.05])
            writer.writerow(['infl', 0.031])

        baseline_defaults = {
            'chlorination_volume': 10.0,
            'chlorination_chemical_dose': 1.5,
            'single_filtration_surface': 10.0,
            'single_filtration_depth': 1.2,
            'single_filtration_grain_size_a': 0.7,
            'dual_filtration_surface': 12.0,
            'dual_filtration_depth': 1.0,
            'dual_filtration_depth_b': 0.8,
            'dual_filtration_grain_size_a': 0.9,
            'dual_filtration_grain_size_b': 1.2,
            'gac_surface': 8.0,
            'gac_depth': 1.5,
            'coagulation_volume': 10.0,
            'coagulation_chemical_dose': 0.08,
            'flocculation_surface': 20.0,
            'flocculation_length': 4.0,
            'ozonation_area': 8.0,
            'ozonation_height': 3.0,
            'ozonation_chemical_dose': 1.0,
        }

        for row in payload.get('technology_properties', []):
            process_key = dac.get_optimizer_process_key_for_technology(
                row.get('technology_name', '')
            )
            value = row.get('value')
            if not isinstance(value, (int, float)):
                continue
            prop_name = self._sanitize_optimizer_key(
                row.get('technologyproperty_name', '')
            )
            if process_key == 'chlorination':
                if 'volume' in prop_name:
                    baseline_defaults['chlorination_volume'] = float(value)
                if 'dose' in prop_name:
                    baseline_defaults['chlorination_chemical_dose'] = (
                        float(value)
                    )
            if process_key == 'filtration_single':
                if 'surface' in prop_name:
                    baseline_defaults['single_filtration_surface'] = float(
                        value
                    )
                if 'depth' in prop_name:
                    baseline_defaults['single_filtration_depth'] = float(value)
                if 'grain' in prop_name:
                    baseline_defaults['single_filtration_grain_size_a'] = (
                        float(value)
                    )
                if 'diam' in prop_name:
                    baseline_defaults['single_filtration_grain_size_a'] = (
                        float(value)
                    )
            if process_key == 'filtration_dual':
                if 'surface' in prop_name:
                    baseline_defaults['dual_filtration_surface'] = float(value)
                if 'depth' in prop_name:
                    if 'depth_b' in prop_name or prop_name.endswith('_b'):
                        baseline_defaults['dual_filtration_depth_b'] = float(
                            value
                        )
                    else:
                        baseline_defaults['dual_filtration_depth'] = float(
                            value
                        )
                if 'grain' in prop_name or 'diam' in prop_name:
                    if (
                        'grain_size_b' in prop_name
                        or 'diam_b' in prop_name
                        or prop_name.endswith('_b')
                    ):
                        baseline_defaults['dual_filtration_grain_size_b'] = (
                            float(value)
                        )
                    else:
                        baseline_defaults['dual_filtration_grain_size_a'] = (
                            float(value)
                        )
            if process_key == 'gac':
                if 'surface' in prop_name:
                    baseline_defaults['gac_surface'] = float(value)
                if 'depth' in prop_name or 'bed_height' in prop_name:
                    baseline_defaults['gac_depth'] = float(value)
            if process_key == 'coagulation-flocculation':
                if 'coag' in prop_name and 'volume' in prop_name:
                    baseline_defaults['coagulation_volume'] = float(value)
                if (
                    ('coag' in prop_name or 'coagulant' in prop_name)
                    and 'dose' in prop_name
                ):
                    baseline_defaults['coagulation_chemical_dose'] = float(
                        value
                    )
                if 'floc' in prop_name and 'surface' in prop_name:
                    baseline_defaults['flocculation_surface'] = float(value)
                if 'floc' in prop_name and 'length' in prop_name:
                    baseline_defaults['flocculation_length'] = float(value)
            if process_key == 'ozonation':
                if 'area' in prop_name:
                    baseline_defaults['ozonation_area'] = float(value)
                if 'height' in prop_name:
                    baseline_defaults['ozonation_height'] = float(value)
                if 'dose' in prop_name:
                    baseline_defaults['ozonation_chemical_dose'] = float(
                        value
                    )

        django_outputs_path = configs_dir / 'django_outputs.json'
        process_outputs = {
            key: {'value': val}
            for key, val in baseline_defaults.items()
        }
        with django_outputs_path.open('w', encoding='utf-8') as fp:
            json.dump({'Process_outputs': process_outputs}, fp, indent=2)

        return {
            'workspace_root': workspace_root,
            'enabled_processes': enabled_processes,
            'enabled_path': enabled_path,
            'in_wq_path': in_wq_path,
        }

    def _run_optimizer_pipeline(self, workspace_root, on_progress=None):
        _ = run_all_optimizations.__name__
        _ = pystimela.__name__

        enabled_path = workspace_root / 'outputs' / 'enabled_processes.json'
        in_wq_path = workspace_root / 'configs' / 'in_wq_params.json'
        if not enabled_path.exists():
            raise FileNotFoundError(
                f'Missing {enabled_path}. Enable processes first.'
            )
        if not in_wq_path.exists():
            raise FileNotFoundError(
                f'Missing {in_wq_path}. Provide optimizer inlet WQ config.'
            )

        with enabled_path.open('r', encoding='utf-8') as fp:
            enabled_processes = json.load(fp).get('enabled', [])

        outputs_dir = workspace_root / 'outputs'
        run_dir = outputs_dir / datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        run_dir.mkdir(parents=True, exist_ok=True)

        process_config = {
            'coagulation-flocculation': {
                'csv': workspace_root / 'inputs' / 'config_coagulation_flocculation.csv',
                'config_json': workspace_root / 'configs' / 'coagulation-flocculation_config.json',
                'result_name': 'coag_floc_results.json',
                'prepare': prepare_coag_floc_config,
                'update': update_coag_floc_wq,
            },
            'filtration_single': {
                'csv': workspace_root / 'inputs' / 'config_filtration_single.csv',
                'config_json': workspace_root / 'configs' / 'filtration_config.json',
                'result_name': 'filtration_results.json',
                'prepare': prepare_filtration_config,
                'update': update_filtration_wq,
            },
            'filtration_dual': {
                'csv': workspace_root / 'inputs' / 'config_filtration_dual.csv',
                'config_json': workspace_root / 'configs' / 'dual_filtration_config.json',
                'result_name': 'dual_filtration_results.json',
                'prepare': prepare_dual_filtration_config,
                'update': update_dual_filtration_wq,
            },
            'gac': {
                'csv': workspace_root / 'inputs' / 'config_gac.csv',
                'config_json': workspace_root / 'configs' / 'gac_config.json',
                'result_name': 'gac_results.json',
                'prepare': prepare_gac_config,
                'update': update_gac_wq,
            },
            'chlorination': {
                'csv': workspace_root / 'inputs' / 'config_chlorination.csv',
                'config_json': workspace_root / 'configs' / 'chlorination_config.json',
                'result_name': 'chlorination_results.json',
                'prepare': prepare_chlorination_config,
                'update': update_chlorination_wq,
            },
            'ozonation': {
                'csv': workspace_root / 'inputs' / 'config_ozonation.csv',
                'config_json': workspace_root / 'configs' / 'ozonation_config.json',
                'result_name': 'ozonation_results.json',
                'prepare': prepare_ozonation_config,
                'update': update_ozonation_wq,
            },
        }

        current_wq_path = in_wq_path
        previous_cwd = Path.cwd()
        total_processes = len(enabled_processes)
        try:
            os.chdir(workspace_root)
            for index, process_key in enumerate(enabled_processes, start=1):
                proc = process_config.get(process_key)
                if proc is None:
                    logger.warning(
                        "Unknown optimizer process '%s' - skipping",
                        process_key,
                    )
                    continue
                if not proc['csv'].exists():
                    logger.warning(
                        "Optimizer CSV config not found for '%s': %s",
                        process_key,
                        proc['csv'],
                    )
                    continue

                if on_progress is not None:
                    on_progress(process_key, 'started', index, total_processes)

                proc['prepare'](str(proc['csv']), str(current_wq_path))
                result_payload = optimize_process(
                    process_key,
                    str(proc['config_json']),
                )

                result_path = run_dir / proc['result_name']
                with result_path.open('w', encoding='utf-8') as fp:
                    json.dump(result_payload, fp, indent=2)

                proc['update'](
                    str(current_wq_path),
                    str(result_path),
                    str(current_wq_path),
                )

                if on_progress is not None:
                    on_progress(process_key, 'done', index, total_processes)
        finally:
            os.chdir(previous_cwd)

        shutil.copy(
            current_wq_path,
            run_dir / 'final_wq_params.json',
        )

        return run_dir

    def _format_optimizer_exception(self, exc):
        if isinstance(exc, subprocess.CalledProcessError):
            stderr = (exc.stderr or '').strip()
            stdout = (exc.stdout or '').strip()
            if stderr:
                last_line = stderr.splitlines()[-1]
                return (
                    'Optimizer subprocess failed. '
                    f'{last_line}'
                )
            if stdout:
                last_line = stdout.splitlines()[-1]
                return (
                    'Optimizer subprocess failed. '
                    f'{last_line}'
                )
        return str(exc)

    def _flatten_json(self, data, prefix=''):
        rows = []
        if isinstance(data, dict):
            for key, value in data.items():
                next_prefix = f'{prefix}.{key}' if prefix else str(key)
                rows.extend(self._flatten_json(value, prefix=next_prefix))
            return rows
        if isinstance(data, list):
            for index, value in enumerate(data):
                next_prefix = f'{prefix}[{index}]'
                rows.extend(self._flatten_json(value, prefix=next_prefix))
            return rows
        rows.append((prefix, data))
        return rows

    def _write_json_as_csv(self, input_json_path, output_csv_path):
        with input_json_path.open('r', encoding='utf-8') as fp:
            payload = json.load(fp)
        flattened_rows = self._flatten_json(payload)
        with output_csv_path.open('w', encoding='utf-8', newline='') as fp:
            writer = csv.writer(fp)
            writer.writerow(['key', 'value'])
            for key, value in flattened_rows:
                writer.writerow([key, value])

    def _export_optimizer_results_to_processed(
        self,
        treatment_plant,
        payload_path,
        workspace_root,
        run_output_dir,
    ):
        processed_root = (
            Path(settings.BASE_DIR)
            / 'research'
            / 'data'
            / 'processed'
            / 'optimizer_runs'
        )
        run_id = timezone.now().strftime('%Y%m%d_%H%M%S')
        processed_dir = (
            processed_root / f'plant_{treatment_plant.id}_{run_id}'
        )
        processed_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy(payload_path, processed_dir / payload_path.name)

        inputs_dir = workspace_root / 'inputs'
        configs_dir = workspace_root / 'configs'
        outputs_dir = workspace_root / 'outputs'
        if (outputs_dir / 'enabled_processes.json').exists():
            shutil.copy(
                outputs_dir / 'enabled_processes.json',
                processed_dir / 'enabled_processes.json',
            )
        if (configs_dir / 'in_wq_params.json').exists():
            shutil.copy(
                configs_dir / 'in_wq_params.json',
                processed_dir / 'in_wq_params.json',
            )
        for csv_input in inputs_dir.glob('config_*.csv'):
            shutil.copy(csv_input, processed_dir / csv_input.name)

        for result_json in run_output_dir.glob('*.json'):
            csv_path = processed_dir / f'{result_json.stem}.csv'
            self._write_json_as_csv(result_json, csv_path)
            shutil.copy(result_json, processed_dir / result_json.name)

        return processed_dir

    def _get_process_from_result_filename(self, filename):
        process_map = {
            'chlorination_results.json': 'chlorination',
            'coag_floc_results.json': 'coagulation-flocculation',
            'filtration_results.json': 'filtration_single',
            'dual_filtration_results.json': 'filtration_dual',
            'gac_results.json': 'gac',
            'ozonation_results.json': 'ozonation',
        }
        return process_map.get(filename)

    def _get_technology_for_process(self, treatment_plant, process_key):
        tech_ids = self._get_treatment_plant_technology_ids(treatment_plant)
        if not tech_ids:
            return None
        technologies = list(Technology.objects.filter(id__in=tech_ids))
        for tech in technologies:
            mapped = dac.get_optimizer_process_key_for_technology(tech.name)
            if mapped == process_key:
                return tech
        return None

    def _iter_numeric_result_values(self, report):
        sections = [
            'optimal variables',
            'outputs',
            'costs',
            'costs_breakdown',
            'economics',
            'derived',
        ]
        numeric_values = {}
        for section in sections:
            data = report.get(section, {})
            if not isinstance(data, dict):
                continue
            for key, value in data.items():
                if isinstance(value, (int, float)):
                    numeric_values[key] = float(value)
        return numeric_values

    def _build_update_row(
        self,
        technology,
        row_type,
        name,
        value,
        unit=''
    ):
        return {
            'technology_id': technology.id,
            'technology_name': technology.name,
            'row_type': row_type,
            'name': name,
            'value': value,
            'unit': unit or '',
        }

    def _merge_updated_rows(self, *row_lists):
        """Merge updated-row lists, later lists overriding earlier ones."""
        merged = OrderedDict()
        for rows in row_lists:
            for row in rows:
                key = (row['technology_id'], row['row_type'], row['name'])
                merged[key] = row
        return list(merged.values())

    def _sort_updated_rows(self, rows, tech_order_index):
        row_type_order = {
            'property': 0,
            'waterquality': 1,
            'kpi': 2,
        }
        return sorted(
            rows,
            key=lambda row: (
                tech_order_index.get(
                    row.get('technology_id'),
                    len(tech_order_index),
                ),
                row_type_order.get(row.get('row_type'), len(row_type_order)),
                str(row.get('name') or ''),
            ),
        )

    def _compute_technology_input_hash(self, treatment_plant, technology):
        """Hash the inputs that determine a technology's optimized result.

        Covers plant-wide design parameters plus the technology's
        non-digested property values and water-quality parameters. Any
        change to these inputs should invalidate a prior optimizer result
        for this technology.
        """
        design_values = {
            dp.designparameter.name: dp.value
            for dp in TreatmentplantDesignParameter.objects.filter(
                treatmentplant=treatment_plant)
        }
        non_digested_ids = list(
            TechnologyPropertyJunction.objects.filter(
                technology=technology, is_digested=False,
            ).values_list('property_id', flat=True)
        )
        property_values = {
            str(row.technologyproperty_id): row.value
            for row in TreatmentPlantTechnologyPropertyValue.objects.filter(
                treatmentplant=treatment_plant,
                technology=technology,
                technologyproperty_id__in=non_digested_ids,
            )
        }
        wq_values = {
            str(row.wq_tech_parameter_id): row.value
            for row in TreatmentPlantWaterQualityParameterValue.objects.filter(  # noqa, E501
                treatmentplant=treatment_plant,
                wq_tech_parameter__technology=technology,
            )
        }
        payload = json.dumps(
            {
                'design': design_values,
                'properties': property_values,
                'wq': wq_values,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

    def _mark_technology_optimized(self, treatment_plant, technology):
        """Record that `technology` now holds a fresh optimizer result."""
        input_hash = self._compute_technology_input_hash(
            treatment_plant, technology)
        TreatmentPlantTechnologyOptimizationStatus.objects.update_or_create(
            treatmentplant=treatment_plant,
            technology=technology,
            defaults={
                'is_optimized': True,
                'optimized_at': timezone.now(),
                'input_snapshot_hash': input_hash,
            },
        )

    def _invalidate_stale_optimized_technologies(self, treatment_plant):
        """Clear is_optimized for technologies whose inputs changed since
        their last optimizer run, so the calculation pipeline stops
        reusing stale optimizer values for them."""
        statuses = (
            TreatmentPlantTechnologyOptimizationStatus.objects
            .filter(treatmentplant=treatment_plant, is_optimized=True)
            .select_related('technology')
        )
        for status in statuses:
            current_hash = self._compute_technology_input_hash(
                treatment_plant, status.technology)
            if current_hash != status.input_snapshot_hash:
                status.is_optimized = False
                status.save(update_fields=['is_optimized'])

    def _persist_optimizer_results_to_db(
        self,
        treatment_plant,
        run_output_dir,
    ):
        persisted_properties = 0
        persisted_kpis = 0
        persisted_wq = 0
        updated_rows = []

        for result_path in run_output_dir.glob('*_results.json'):
            process_key = self._get_process_from_result_filename(
                result_path.name
            )
            if process_key is None:
                continue

            technology = self._get_technology_for_process(
                treatment_plant,
                process_key,
            )
            if technology is None:
                logger.warning(
                    'No technology found for optimizer process %s in plant %s',
                    process_key,
                    treatment_plant.id,
                )
                continue

            with result_path.open('r', encoding='utf-8') as fp:
                report = json.load(fp)

            numeric_values = self._iter_numeric_result_values(report)
            technology_properties_persisted = 0

            for optimizer_key, numeric_value in numeric_values.items():
                prop_obj = dac.get_optimizer_output_property_for_technology(
                    technology, optimizer_key,
                )
                if prop_obj is None:
                    property_candidates = (
                        dac.get_optimizer_output_db_candidates(
                            process_key,
                            'properties',
                            optimizer_key,
                        )
                    )
                    if optimizer_key not in property_candidates:
                        property_candidates.append(
                            optimizer_key.replace('_', ' '))
                    for property_name in property_candidates:
                        prop_obj = TechnologyProperty.objects.filter(
                            name__iexact=property_name
                        ).first()
                        if prop_obj is not None:
                            break

                if prop_obj is not None:
                    (
                        TreatmentPlantTechnologyPropertyValue.objects
                        .update_or_create(
                            treatmentplant=treatment_plant,
                            technology=technology,
                            technologyproperty=prop_obj,
                            defaults={
                                'value': numeric_value,
                                'source': (
                                    TreatmentPlantTechnologyPropertyValue
                                    .SOURCE_OPTIMIZED
                                ),
                            },
                        )
                    )
                    persisted_properties += 1
                    technology_properties_persisted += 1
                    updated_rows.append(
                        self._build_update_row(
                            technology=technology,
                            row_type='property',
                            name=prop_obj.name,
                            value=numeric_value,
                            unit=prop_obj.unit,
                        )
                    )

                junction = (
                    dac.get_optimizer_output_wq_junction_for_technology(
                        technology, optimizer_key,
                    )
                )
                if junction is None:
                    wq_candidates = []
                    if hasattr(dac, 'get_optimizer_output_wq_candidates'):
                        wq_candidates = dac.get_optimizer_output_wq_candidates(
                            process_key,
                            optimizer_key,
                        )
                    if optimizer_key not in wq_candidates:
                        wq_candidates.append(optimizer_key.replace('_', ' '))

                    for wq_name in wq_candidates:
                        junction = (
                            WaterqualityParameterTechnologyJunction.objects
                            .filter(
                                technology=technology,
                                waterqualityparameter__name__iexact=wq_name,
                            )
                            .select_related('waterqualityparameter')
                            .first()
                        )
                        if junction is not None:
                            break

                if junction is not None:
                    (
                        TreatmentPlantWaterQualityParameterValue.objects
                        .update_or_create(
                            treatmentplant=treatment_plant,
                            wq_tech_parameter=junction,
                            defaults={'value': numeric_value},
                        )
                    )
                    persisted_wq += 1
                    updated_rows.append(
                        self._build_update_row(
                            technology=technology,
                            row_type='waterquality',
                            name=junction.waterqualityparameter.name,
                            value=numeric_value,
                            unit=junction.waterqualityparameter.unit,
                        )
                    )

                kpi_candidates = dac.get_optimizer_output_db_candidates(
                    process_key,
                    'kpis',
                    optimizer_key,
                )
                if optimizer_key not in kpi_candidates:
                    kpi_candidates.append(optimizer_key.replace('_', ' '))

                for kpi_name in kpi_candidates:
                    kpi_obj = TechnologyKPI.objects.filter(
                        name__iexact=kpi_name
                    ).first()
                    if kpi_obj is None:
                        continue
                    TreatmentPlantTechnologyKPIValue.objects.update_or_create(
                        treatmentplant=treatment_plant,
                        technology=technology,
                        kpi=kpi_obj,
                        defaults={'value': numeric_value},
                    )
                    persisted_kpis += 1
                    updated_rows.append(
                        self._build_update_row(
                            technology=technology,
                            row_type='kpi',
                            name=kpi_obj.name,
                            value=numeric_value,
                            unit=kpi_obj.unit,
                        )
                    )
                    break

            if technology_properties_persisted > 0:
                self._mark_technology_optimized(treatment_plant, technology)

        return {
            'properties': persisted_properties,
            'waterquality': persisted_wq,
            'kpis': persisted_kpis,
            'updated_rows': updated_rows,
        }

    def _optimizer_process_display_name(self, treatment_plant, process_key):
        technology = self._get_technology_for_process(
            treatment_plant, process_key,
        )
        return technology.name if technology else process_key

    def _report_optimizer_progress(
        self, treatment_plant, process_key, phase, index, total,
    ):
        label = self._optimizer_process_display_name(
            treatment_plant, process_key,
        )
        status = self._get_optimizer_status(treatment_plant.id)
        status['state'] = 'running'
        status['progress'] = {
            'index': index,
            'total': total,
            'process': label,
            'phase': phase,
        }
        completed = status.setdefault('completed_processes', [])
        if phase == 'started':
            status['message'] = (
                f'Optimizing {label} ({index} of {total})...'
            )
        elif phase == 'done':
            if label not in completed:
                completed.append(label)
            status['message'] = (
                f'Finished optimizing {label} ({index} of {total}).'
            )
        self._set_optimizer_status(treatment_plant.id, status)

    def _run_calculation_pipeline(self, treatment_plant):
        """Recompute technology digestion, tech KPIs, and plant KPIs.

        Reads all inputs from the database (design parameters, saved
        technology property values, water quality junctions), runs the
        performance/digestion calculators, persists the results, and
        returns the list of updated-row dicts (digested properties and
        technology KPIs) for display, in the same shape as optimizer
        updated rows.
        """
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
        optimized_tech_prop_names = {}
        all_tech_properties = TechnologyProperty.objects.all()
        for tech_id in tech_ids:
            technology = Technology.objects.get(id=tech_id)
            tech_properties[technology.name] = {}
            wq_parameters[technology.name] = {}
            digested_tech_prop_names[technology.name] = []
            optimized_tech_prop_names[technology.name] = []
            defaultval_tech_props[technology.name] = {}
            for wq_input in WaterqualityParameterTechnologyJunction.objects.filter(  # noqa, E501
                        technology=technology,
                        is_inputparameter=True,
                        is_targetparameter=False):
                wq_p = WaterqualityParameterData(
                    name=wq_input.waterqualityparameter.name,
                    input_label=INPUT_WQPARAMETER_KEY,
                    input_value=wq_input.default_value)
                wq_parameters[technology.name].update(wq_p.to_dict())
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
                        technology=technology, is_digested=False):
                if all_tech_properties.get(id=def_tp.property.id).parent_property is None:  # noqa, E501
                    defaultval_tech_props[technology.name].update(
                        {def_tp.property.name: def_tp.default_value})
            for isdigested_tp in TechnologyPropertyJunction.objects.filter(
                        technology=technology, is_digested=True):
                digested_tech_prop_names[technology.name] += [isdigested_tp.property.name]  # noqa, E501
            is_technology_optimized = (
                TreatmentPlantTechnologyOptimizationStatus.objects
                .filter(
                    treatmentplant=treatment_plant,
                    technology=technology,
                    is_optimized=True,
                ).exists()
            )
            if is_technology_optimized:
                for optimized_tp in TechnologyPropertyJunction.objects.filter(
                            technology=technology, is_digested=True,
                            sent_to_optimizer=True):
                    optimized_tech_prop_names[technology.name] += [
                        optimized_tp.property.name]
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
            optimized_tech_parameter_list=optimized_tech_prop_names,
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
        calculation_updated_rows = []
        for tech_name in technology_names:
            for prop_name in kpi_calculator.digested_tech_parameter_list[tech_name]:  # noqa, E501
                try:
                    prop_value = kpi_calculator.tech_parameters[tech_name][prop_name]  # noqa, E501
                    tech = Technology.objects.get(name=tech_name)
                    prop_obj = TechnologyProperty.objects.get(name=prop_name)
                    is_optimized_value = (
                        prop_name in optimized_tech_prop_names[tech_name])
                    TreatmentPlantTechnologyPropertyValue.objects.update_or_create(  # noqa, E501
                        treatmentplant=treatment_plant,
                        technology=tech,
                        technologyproperty=prop_obj,
                        defaults={
                            'value': str(prop_value),
                            'source': (
                                TreatmentPlantTechnologyPropertyValue.SOURCE_OPTIMIZED  # noqa, E501
                                if is_optimized_value
                                else TreatmentPlantTechnologyPropertyValue.SOURCE_DIGESTED  # noqa, E501
                            ),
                        }
                    )
                    calculation_updated_rows.append(
                        self._build_update_row(
                            technology=tech,
                            row_type='property',
                            name=prop_obj.name,
                            value=prop_value,
                            unit=prop_obj.unit,
                        )
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
                    calculation_updated_rows.append(
                        self._build_update_row(
                            technology=tech,
                            row_type='kpi',
                            name=kpi.name,
                            value=kpi_value,
                            unit=kpi.unit,
                        )
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
                related_tech = TechnologyRelatedtechnology.objects.filter(
                    relatedtechnology_is_currentstep=True).get(
                        technology_id=tech_id)
                related_tech_id = related_tech.id
            except TechnologyRelatedtechnology.DoesNotExist:
                related_tech = None
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
        return calculation_updated_rows

    def _run_optimizer_job(
        self,
        treatment_plant,
        payload_path,
        workspace_root,
    ):
        close_old_connections()
        status = self._get_optimizer_status(treatment_plant.id)
        status.update(
            {
                'state': 'running',
                'message': 'Optimization is running in the background.',
                'progress': {},
                'completed_processes': [],
                'action': 'optimize',
            }
        )
        self._set_optimizer_status(treatment_plant.id, status)

        def on_progress(process_key, phase, index, total):
            self._report_optimizer_progress(
                treatment_plant, process_key, phase, index, total,
            )

        try:
            run_output_dir = self._run_optimizer_pipeline(
                workspace_root, on_progress=on_progress,
            )
            persisted = self._persist_optimizer_results_to_db(
                treatment_plant=treatment_plant,
                run_output_dir=run_output_dir,
            )
            calculation_rows = self._run_calculation_pipeline(
                treatment_plant)
            processed_dir = self._export_optimizer_results_to_processed(
                treatment_plant=treatment_plant,
                payload_path=payload_path,
                workspace_root=workspace_root,
                run_output_dir=run_output_dir,
            )
            done_payload = {
                'state': 'done',
                'seen': False,
                'action': 'optimize',
                'message': (
                    'Optimization finished. '
                    f"Updated {persisted['properties']} properties, "
                    f"{persisted['waterquality']} water quality values, and "
                    f"{persisted['kpis']} KPI values. "
                    f'Recalculated {len(calculation_rows)} digested '
                    'properties and technology KPI values.'
                ),
                'updated_rows': self._merge_updated_rows(
                    persisted.get('updated_rows', []), calculation_rows,
                ),
                'processed_dir': str(processed_dir),
            }
            self._set_optimizer_status(treatment_plant.id, done_payload)
        except Exception as exc:
            logger.exception('Background optimizer execution failed: %s', exc)
            error_message = self._format_optimizer_exception(exc)
            current_status = self._get_optimizer_status(treatment_plant.id)
            failed_process = (
                current_status.get('progress') or {}
            ).get('process')
            message = 'Optimizer failed. '
            if failed_process:
                message += f'Failed while optimizing {failed_process}. '
            message += error_message
            self._set_optimizer_status(
                treatment_plant.id,
                {
                    'state': 'failed',
                    'seen': False,
                    'action': 'optimize',
                    'message': message,
                    'updated_rows': [],
                    'progress': current_status.get('progress', {}),
                    'completed_processes': current_status.get(
                        'completed_processes', [],
                    ),
                },
            )
        finally:
            close_old_connections()

    def get_treatment_plant(self):
        return get_object_or_404(TreatmentPlant, pk=self.kwargs['plant_id'])

    def _apply_optimizer_field_locking(self, formset, treatment_plant):
        """Highlight optimizer-managed non-digested fields without locking edits."""
        tech_ids = TreatmentPlantLayout.objects.filter(
            treatmentplant=treatment_plant
        ).values_list('technology', flat=True)
        locked_pairs = {
            (junction.technology_id, junction.property_id)
            for junction in TechnologyPropertyJunction.objects.filter(
                technology__in=tech_ids,
                is_digested=False,
                sent_to_optimizer=True,
            )
        }

        if not locked_pairs:
            return formset

        for form in formset.forms:
            tech_id = None
            prop_id = None
            if getattr(form.instance, 'technology_id', None):
                tech_id = form.instance.technology_id
            else:
                tech_id = form.initial.get('technology')
            if getattr(form.instance, 'technologyproperty_id', None):
                prop_id = form.instance.technologyproperty_id
            else:
                prop_id = form.initial.get('technologyproperty')

            if (tech_id, prop_id) not in locked_pairs:
                continue

            if 'value' in form.fields:
                css_class = form.fields['value'].widget.attrs.get('class', '')
                css_class = (css_class + ' optimizer-managed-input').strip()
                form.fields['value'].widget.attrs['class'] = css_class
                form.fields['value'].widget.attrs['title'] = (
                    'This value is sent to the optimizer, but you can still '
                    'edit it before calculating or optimizing.'
                )

        return formset

    def get_form(self, form_class=None):
        treatment_plant = self.get_treatment_plant()
        tech_ids = TreatmentPlantLayout.objects.filter(
            treatmentplant=treatment_plant).values_list(
                'technology', flat=True)

        # Persist rows for required (technology-level) design parameters so
        # unchanged default values are still present during calculations.
        required_defaults = TechnologyPropertyJunction.objects.filter(
            technology__in=tech_ids,
            is_designparameter=True,
            is_digested=False,
        ).select_related('technology', 'property')
        for junction in required_defaults:
            TreatmentPlantTechnologyPropertyValue.objects.get_or_create(
                treatmentplant=treatment_plant,
                technology=junction.technology,
                technologyproperty=junction.property,
                defaults={'value': junction.default_value},
            )

        non_digested_prop_ids = required_defaults.values_list(
            'property', flat=True)
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
            return self._apply_optimizer_field_locking(
                formset,
                treatment_plant,
            )
        # For GET: if queryset is empty and initial is non-empty, set extra
        if not queryset.exists() and initial:
            DynamicFormSet = modelformset_factory(
                TreatmentPlantTechnologyPropertyValue,
                form=TreatmentTechPropertyValueForm,
                extra=len(initial),
            )
            formset = DynamicFormSet(
                queryset=queryset, initial=initial, prefix=prefix)
            return self._apply_optimizer_field_locking(
                formset,
                treatment_plant,
            )
        formset = TreatmentPlantTechPropertyValueFormSet(
            queryset=queryset, initial=initial, prefix=prefix)
        return self._apply_optimizer_field_locking(
            formset,
            treatment_plant,
        )

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
        action = self.request.POST.get('action', 'calculate')
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

        # Any edited inputs may invalidate a technology's prior optimizer
        # result; recompute this before deciding what to (re)calculate.
        self._invalidate_stale_optimized_technologies(treatment_plant)

        if action == 'reset_optimization':
            TreatmentPlantTechnologyOptimizationStatus.objects.filter(
                treatmentplant=treatment_plant,
            ).update(is_optimized=False)
            calculation_updated_rows = self._run_calculation_pipeline(
                treatment_plant)
            self._set_optimizer_status(
                treatment_plant.id,
                {
                    'state': 'done',
                    'seen': False,
                    'action': 'calculate',
                    'message': (
                        'Optimized values cleared. Recalculated '
                        f'{len(calculation_updated_rows)} properties and '
                        'KPI values using default/user-specified inputs.'
                    ),
                    'updated_rows': calculation_updated_rows,
                    'progress': {},
                    'completed_processes': [],
                },
            )
            return redirect(
                'technology_properties', plant_id=treatment_plant.id)

        if action == 'optimize':
            payload = self._build_optimizer_payload(treatment_plant)
            output_path = self._write_optimizer_payload(
                treatment_plant,
                payload=payload,
            )
            csv_info = self._write_optimizer_csv_inputs(
                treatment_plant,
                payload,
            )
            run_async = getattr(settings, 'OPTIMIZER_ASYNC', True)
            if run_async:
                task_id = str(uuid.uuid4())
                self._set_optimizer_status(
                    treatment_plant.id,
                    {
                        'state': 'running',
                        'seen': False,
                        'action': 'optimize',
                        'task_id': task_id,
                        'message': (
                            'Optimization started. '
                            'Showing updated results can take a while.'
                        ),
                        'updated_rows': [],
                        'progress': {},
                        'completed_processes': [],
                    },
                )
                worker = threading.Thread(
                    target=self._run_optimizer_job,
                    kwargs={
                        'treatment_plant': treatment_plant,
                        'payload_path': output_path,
                        'workspace_root': csv_info['workspace_root'],
                    },
                    daemon=True,
                )
                worker.start()
                messages.info(
                    self.request,
                    'Optimization started in the background. '
                    'Updated values will appear after completion.'
                )
            else:
                try:
                    run_output_dir = self._run_optimizer_pipeline(
                        csv_info['workspace_root']
                    )
                    persisted = self._persist_optimizer_results_to_db(
                        treatment_plant=treatment_plant,
                        run_output_dir=run_output_dir,
                    )
                    calculation_rows = self._run_calculation_pipeline(
                        treatment_plant)
                    processed_dir = self._export_optimizer_results_to_processed(
                        treatment_plant=treatment_plant,
                        payload_path=output_path,
                        workspace_root=csv_info['workspace_root'],
                        run_output_dir=run_output_dir,
                    )
                    messages.success(
                        self.request,
                        'Optimization completed. Persisted '
                        f"{persisted['properties']} properties, "
                        f"{persisted['waterquality']} water quality values, "
                        f"and {persisted['kpis']} KPI values. Recalculated "
                        f"{len(calculation_rows)} digested properties and "
                        'technology KPI values. '
                        f'Results exported to {processed_dir}'
                    )
                except Exception as exc:
                    logger.exception('Optimizer execution failed: %s', exc)
                    messages.error(
                        self.request,
                        'Optimizer inputs were written, but running '
                        f'pystimela_optim failed: {exc}'
                    )
            return redirect(
                'technology_properties',
                plant_id=treatment_plant.id,
            )

        # Step 2: Calculate technology-specific and plant-wide KPIs
        calculation_updated_rows = self._run_calculation_pipeline(
            treatment_plant)

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

        digested_count = sum(
            1 for row in calculation_updated_rows
            if row['row_type'] == 'property'
        )
        kpi_count = sum(
            1 for row in calculation_updated_rows
            if row['row_type'] == 'kpi'
        )
        self._set_optimizer_status(
            treatment_plant.id,
            {
                'state': 'done',
                'seen': False,
                'action': 'calculate',
                'message': (
                    'Calculation finished. '
                    f'Updated {digested_count} digested properties and '
                    f'{kpi_count} technology KPI values.'
                ),
                'updated_rows': calculation_updated_rows,
                'progress': {},
                'completed_processes': [],
            },
        )
        return redirect(
            'technology_properties', plant_id=treatment_plant.id)

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
        tech_order_index = {}
        for index, tech in enumerate(tech_order):
            tech_order_index.setdefault(tech.id, index)

        # Map tech id to Technology instance
        tech_map = {tech.id: tech for tech in tech_order}

        value_map = {
            (row.technology_id, row.technologyproperty_id): row.value
            for row in TreatmentPlantTechnologyPropertyValue.objects.filter(
                treatmentplant=treatment_plant,
                technology_id__in=[tech.id for tech in tech_order],
            )
        }
        junction_map = {
            (junction.technology_id, junction.property_id): junction
            for junction in TechnologyPropertyJunction.objects.filter(
                technology__in=[tech.id for tech in tech_order],
            ).select_related('property')
        }

        # Group forms by technology id preserving order
        forms_by_tech = OrderedDict()
        for tech in tech_order:
            forms_by_tech[tech] = []

        digested_properties_by_tech = OrderedDict((tech.id, []) for tech in tech_order)
        for tech in tech_order:
            for junction in (
                j for (tech_id, _), j in junction_map.items()
                if tech_id == tech.id and j.is_digested
            ):
                # Only show digested properties once a calculation or
                # optimization has actually produced a persisted value.
                value_key = (junction.technology_id, junction.property_id)
                if value_key not in value_map:
                    continue
                digested_properties_by_tech[tech.id].append({
                    'name': junction.property.name,
                    'value': value_map[value_key],
                    'unit': junction.property.unit,
                    'description': junction.property.description,
                    'sent_to_optimizer': junction.sent_to_optimizer,
                })
            digested_properties_by_tech[tech.id].sort(
                key=lambda row: row['name'] or ''
            )

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
            junction = junction_map.get((tech_id, prop_id))
            if tech is not None:
                forms_by_tech[tech].append({
                    'form': form,
                    'prop_name': prop_name,
                    'prop_unit': prop_unit,
                    'prop_help': prop_help,
                    'is_optimizer_managed': bool(
                        junction
                        and junction.sent_to_optimizer
                        and not junction.is_digested
                    ),
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
        context['digested_properties_by_tech'] = digested_properties_by_tech

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

        optimizer_status = self._get_optimizer_status(treatment_plant.id)
        updated_rows = optimizer_status.get('updated_rows', [])

        updated_properties_by_tech = defaultdict(set)
        updated_wq_by_tech = defaultdict(set)
        for row in updated_rows:
            tech_id = row.get('technology_id')
            row_type = row.get('row_type')
            name = row.get('name')
            if not tech_id or not name:
                continue
            if row_type == 'property':
                updated_properties_by_tech[tech_id].add(name)
            if row_type == 'waterquality':
                updated_wq_by_tech[tech_id].add(name)

        context['optimizer_status'] = optimizer_status
        # KPI values are shown on the KPI results page, not this summary.
        context['optimizer_updated_rows'] = self._sort_updated_rows(
            [row for row in updated_rows if row.get('row_type') != 'kpi'],
            tech_order_index,
        )
        context['optimizer_updated_properties_by_tech'] = {
            key: sorted(list(value))
            for key, value in updated_properties_by_tech.items()
        }
        context['optimizer_updated_wq_by_tech'] = {
            key: sorted(list(value))
            for key, value in updated_wq_by_tech.items()
        }

        self._mark_optimizer_status_seen(treatment_plant.id)

        optimization_statuses = {
            status.technology_id: status
            for status in TreatmentPlantTechnologyOptimizationStatus.objects.filter(  # noqa, E501
                treatmentplant=treatment_plant,
                technology_id__in=[tech.id for tech in tech_order],
            )
        }
        technology_optimization_status = {
            tech.id: {
                'is_optimized': (
                    optimization_statuses[tech.id].is_optimized
                    if tech.id in optimization_statuses else False
                ),
                'optimized_at': (
                    optimization_statuses[tech.id].optimized_at
                    if tech.id in optimization_statuses else None
                ),
            }
            for tech in tech_order
        }
        context['technology_optimization_status'] = (
            technology_optimization_status)
        optimized_technologies = []
        seen_optimized_technology_ids = set()
        for tech in tech_order:
            if tech.id in seen_optimized_technology_ids:
                continue
            if not technology_optimization_status[tech.id]['is_optimized']:
                continue
            optimized_technologies.append(tech)
            seen_optimized_technology_ids.add(tech.id)
        context['optimized_technologies'] = optimized_technologies
        context['any_technology_optimized'] = any(
            status['is_optimized']
            for status in technology_optimization_status.values()
        )

        context['show_optimize_button'] = self._has_optimizer_targets(
            treatment_plant)
        # --- End new context variable ---
        return context


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
