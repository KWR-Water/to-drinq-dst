from django.shortcuts import render, redirect, get_object_or_404
import logging
import numpy as np
from warnings import warn
# from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin

from django.http import (
    HttpResponse, Http404, HttpResponseRedirect, JsonResponse,
    )
from django.views import generic
from django.forms import ValidationError
from django.urls import reverse, reverse_lazy
from drinq.models import (
    Compound,
    CompoundCas,
    Technology,
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
    TreatmentPlantPropertyValue,
    TreatmentPlantProperty,
    TreatmentPlantTechnologyPropertyValue,
    TechnologyConstructionCostParameter,
)
from drinq.forms import (
    ConfigurationNameForm,
    WaterSourceForm,
    QuestionWizardForm,
    SessionSelectForm,
    TreatmentDesignSelectionForm,
    DesignParameterValueFormSet,
    TechnologyPropertyValueFormSet,
    TechnologyPropertyValueForm,
    build_technology_property_initials,
    )
from drinq.chemistry_tools import smiles_to_svg
import drinq.decision_tree as dst
import drinq.api_calculation as dac
from drinq.api_calculation import (
    KPI_NOMINAL_FLOW_M3PERH,
    KPI_ENERGY_CONSUMPTION_KWHRPERM3,
    KPI_CONSTRUCTION_COSTS_EUR,
    KPI_FOOTPRINT_AREA_M2,
    KPI_OPER_AND_MAINT_COSTS,
    KPI_INVESTMENT_COSTS,
    TECHKPI_ENERGYCONSUMPTION_KWHRPERDAY,
    TECHKPI_FOOTPRINT_AREA_M2,
    TECHKPI_MASS_OF_CHEMICALS,
    TECHKPI_POWER_KW,
    TECHKPI_CO2_EMISSIONS_KGPERM3,
    )
# from drinq.api_views import TPPN  # Treatment Plant Property Names
from drinq.utils.treatmentkpi import TPPN, TPN


EXCLUDE_KEY = ['csrfmiddlewaretoken', 'next']
INITIAL_TOTAL_STEPS = 4
DECISION_TREE_MAX_STEPS = 50
PLANT_KPI_MAPPING = {
    KPI_NOMINAL_FLOW_M3PERH: TPPN['nominal_flow_rate_m3perh'],
    KPI_ENERGY_CONSUMPTION_KWHRPERM3: TPPN['energy_consumption_kwhperm3'],
    KPI_FOOTPRINT_AREA_M2: TPPN['footprint_area_m2'],
    KPI_CONSTRUCTION_COSTS_EUR: TPPN['construction_costs_eurperm3'],
    KPI_OPER_AND_MAINT_COSTS: TPPN['operation_and_maintenance_costs_eurperyr'],
    KPI_INVESTMENT_COSTS: TPPN['investment_costs'],
}
# SUMMED_TECHKPI_MAPPING = {
#     KPI_ENERGY_CONSUMPTION_KWHRPERM3: TPPN['energy_consumption_kwhperm3'],
#     TECHKPI_FOOTPRINT_AREA_M2: TPPN['footprint_area_m2'],
#     TECHKPI_CO2_EMISSIONS_KGPERM3: TPPN['co2_equivalent_emissions_kgperm3'],
# }

logger = logging.getLogger(__name__)


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
        results = QuestionAnswer.objects.filter(
            configuration__id=request.session['configuration_id'])
        if results.exists():
            context = self.get_context_data(results=results)
            # TODO: store the results in the database
            # Render the template with the context
            return render(
                request,
                template_name=self.template_name,
                context={'data': context})
        else:
            return HttpResponseRedirect(redirect('drinq_redirect'))

    def get_context_data(self, **kwargs):
        results = kwargs.get('results', None)
        choices, technologies, treatment_options = {}, [], []
        # session_key = self.request.session.session_key
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
            (
                treatment_options,
                treatment_maps,
                ) = dst.get_treatment_trains(
                    technology_tuples=technologies)
            for option_number, _ in treatment_options.items():
                treatment_options[option_number]['already_named'] = (
                    option_number in named_option_ids
                    )
            for plant in slugged_plants:
                if plant.slug is not None:
                    treatment_options[plant.option]['slug'] = plant.slug
            context['treatment_options'] = treatment_options
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
        context['treatment_plant'] = self.object
        context['treatment_layout'] = TreatmentPlantLayout.objects.filter(
            treatmentplant=self.object)
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

    def get_constructioncost_parameter_dict(self, technology_ids: list = None):
        if technology_ids is None:
            technology_ids = self.get_treatment_technology_ids()
        cost_parameters = {tech: {} for tech in technology_ids}
        for tech in technology_ids:
            # Fetch cost parameters for each technology
            tech_obj = Technology.objects.get(id=tech)
            cost_params = TechnologyConstructionCostParameter.objects.filter(
                technology=tech_obj).first()
            if cost_params:
                plantproperty = cost_params.plantproperty.name if cost_params.plantproperty else None  # noqa, E501
                technologyproperty = cost_params.technologyproperty.name if cost_params.technologyproperty else None  # noqa, E501
                if technologyproperty is not None:
                    technologyproperty_value = TreatmentPlantTechnologyPropertyValue.objects.filter(  # noqa, E501
                        treatmentplant=self.get_treatment_plant(),
                        technology=tech_obj,
                        technologyproperty=cost_params.technologyproperty
                    ).first()
                cost_parameters[tech] = {
                    'a': cost_params.a,
                    'b': cost_params.b,
                    'c': cost_params.c,
                    'plant_property': plantproperty,
                    'technology_property': technologyproperty,
                    'cost_function': cost_params.costfunction,
                }
            else:
                cost_parameters[tech] = None

        return cost_parameters

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

        # Process results after saving
        # self.process_results(treatment_plant)
        # After saving plant-wide design parameters, continue to
        # technology-level properties step before running calculations.
        return redirect('technology_properties', plant_id=treatment_plant.id)

    def form_invalid(self, formset):
        """Handle invalid form"""
        return self.render_to_response(self.get_context_data(formset=formset))

    def process_results(self, treatment_plant):
        stages = self.get_treatment_stage_names()
        technologies = self.get_treatment_technology_names()

        # Initialize the treatment plant performance calculator
        plant_calculator = dac.TreatmentPlantPerformanceCalculator(
            treatmentplant_id=treatment_plant.id,
            stages=stages,
            technologies=technologies,
            design_parameters={
                dp.designparameter.name: dp.value
                for dp in TreatmentplantDesignParameter.objects.filter(
                    treatmentplant=treatment_plant
                )
            }
            )

        # Calculate and store plant properties
        # TODO: Is this processed???
        nominal_flow_value = plant_calculator.update_nominal_flow_m3perhr()
        nominal_flow, _ = TreatmentPlantProperty.objects.get_or_create(
            name=TPPN["nominal_flow_rate_m3perh"])
        plant_calculator.set_constructioncosts(
            cost_parameters=self.get_constructioncost_parameter_dict(),
        )
        TreatmentPlantPropertyValue.objects.update_or_create(
            treatmentplant=treatment_plant,
            property=nominal_flow,
            defaults={'value': str(nominal_flow_value)}
        )

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
        context['properties'] = TreatmentPlantPropertyValue.objects.filter(
            treatmentplant=self.object
        )
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
    form_class = TechnologyPropertyValueFormSet

    def get_treatment_plant(self):
        return get_object_or_404(TreatmentPlant, pk=self.kwargs['plant_id'])

    def get_form(self, form_class=None):
        treatment_plant = self.get_treatment_plant()
        # Only include properties where is_digested is False
        # Get all property IDs for this plant's technologies where is_digested is False
        tech_ids = TreatmentPlantLayout.objects.filter(
            treatmentplant=treatment_plant).values_list('technology', flat=True)
        non_digested_prop_ids = TechnologyPropertyJunction.objects.filter(
            technology__in=tech_ids, is_digested=False
        ).values_list('property', flat=True)
        queryset = TreatmentPlantTechnologyPropertyValue.objects.filter(
            treatmentplant=treatment_plant,
            technologyproperty_id__in=non_digested_prop_ids
        )
        initial = []
        if not queryset.exists():
            initial = build_technology_property_initials(treatment_plant)

        # If there are no persisted rows, create a dynamic formset with
        # `extra=len(initial)` so the provided initial entries are
        # rendered as editable forms.
        if not queryset.exists() and initial:
            from django.forms import modelformset_factory
            DynamicTechFormSet = modelformset_factory(
                TreatmentPlantTechnologyPropertyValue,
                form=TechnologyPropertyValueForm,
                extra=len(initial)
            )
            if self.request.method == 'POST':
                return DynamicTechFormSet(
                    self.request.POST, queryset=queryset, initial=initial)
            return DynamicTechFormSet(queryset=queryset, initial=initial)

        if self.request.method == 'POST':
            return TechnologyPropertyValueFormSet(
                self.request.POST, queryset=queryset, initial=initial)
        return TechnologyPropertyValueFormSet(
            queryset=queryset, initial=initial)

    def form_valid(self, formset):
        treatment_plant = self.get_treatment_plant()
        if not formset.is_valid():
            return self.form_invalid(formset)

        saved = []
        for form in formset.forms:
            if getattr(form, 'cleaned_data', None) is None:
                form.full_clean()
            if not form.cleaned_data:
                continue
            if form.cleaned_data.get('DELETE', False):
                if form.instance.pk:
                    form.instance.delete()
                continue
            instance = form.save(commit=False)
            if getattr(instance, 'treatmentplant', None) is None:
                instance.treatmentplant = treatment_plant
            instance.save()
            saved.append(instance)

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

        plant_calculator = dac.TreatmentPlantPerformanceCalculator(
            treatmentplant_id=treatment_plant.id,
            stages=stage_names,
            technologies=technology_names,
            design_parameters=design_parameters,
            plant_kpis={},
            db_kpi_mapping=PLANT_KPI_MAPPING,
        )
        # Step 1: set the nominal flow
        # ------------------------------        
        if plant_calculator.nominal_flow_m3perhr.value is None:
            plant_calculator.update_nominal_flow_m3perhr()
            plant_calculator.update_plant_kpis()  # to set nominal flow KPI
        wq_parameters = {tech: None for tech in technology_names}

        # plant_calculator.plant_kpis[TPPN['nominal_flow_rate_m3perh']] = (
        #     plant_calculator.nominal_flow_m3perhr.value)

        # Step 2: initialize technology-dependent calculations
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
            digested_tech_prop_names[technology.name] = []
            defaultval_tech_props[technology.name] = {}
            for def_tp in TechnologyPropertyJunction.objects.filter(
                        technology=technology, is_designparameter=False):
                if all_tech_properties.get(id=def_tp.property.id).parent_property is None:  # noqa, E501
                    defaultval_tech_props[technology.name].update(
                        {
                            def_tp.property.name: def_tp.default_value
                        })
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
        tech_calculator = dac.TechnologyPerformanceCalculator(
            treatmentplant_id=treatment_plant.id,
            stages=stage_names,
            technologies=technology_names,
            design_parameters=design_parameters,
            tech_parameters=tech_properties,
            waterquality_parameters=wq_parameters,
            plant_kpis=plant_calculator.plant_kpis,
            tech_kpinames=technology_kpis,
            digested_tech_parameter_list=digested_tech_prop_names,
        )
        tech_calculator.calculate_kpi()  # TODO: debug. Microstrainer works!
        tech_calculator.sum_kpis()
        
        # Assign the summed technology KPIs to the plant calculator
        summed_kpis = tech_calculator.summed_kpis
        plant_calculator.energyconsumption_kwhrperday.value = summed_kpis.get(  # noqa, E501
            TECHKPI_ENERGYCONSUMPTION_KWHRPERDAY, None)
        plant_calculator.energyconsumption_kwhrperm3.value = plant_calculator.get_energyconsumption_per_m3()  # noqa, E501
        plant_calculator.power_kw.value = summed_kpis.get(
            TECHKPI_POWER_KW, None)
        plant_calculator.co2_emissions_kgperm3.value = summed_kpis.get(  # noqa, E501
            TECHKPI_CO2_EMISSIONS_KGPERM3, None)
        plant_calculator.footprint_area_m2.value = summed_kpis.get(
            TECHKPI_FOOTPRINT_AREA_M2, None)

        # Save the digested technology properties back to the database
        for tech_name in technology_names:
            for prop_name in tech_calculator.digested_tech_parameter_list[tech_name]:  # noqa, E501
                try:
                    prop_value = tech_calculator.tech_parameters[tech_name][prop_name]  # noqa, E501
                    tech_obj = Technology.objects.get(name=tech_name)
                    prop_obj = TechnologyProperty.objects.get(name=prop_name)
                    TreatmentPlantTechnologyPropertyValue.objects.update_or_create(  # noqa, E501
                        treatmentplant=treatment_plant,
                        technology=tech_obj,
                        technologyproperty=prop_obj,
                        defaults={'value': str(prop_value)}
                    )
                except TechnologyProperty.DoesNotExist:
                    continue
        
        # Step 3: compute plant-wide properties
        # --------------------------------------
        plant_calculator.update_plant_kpis()

        # compute construction costs if possible (replicate existing helper)
        constrcosts = {}
        for tech_id in tech_ids:
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
                                f"technologyproperty={tccp.technologyproperty}"
                            )
                            warn(
                                f"Missing TreatmentPlantTechnologyPropertyValue"  # noqa, E501
                                f" for technology_id={tech_id} and "
                                f"technologyproperty={tccp.technologyproperty}"
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
                                plantprop_value = plant_calculator.plant_kpis.get(  # noqa, E501
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
        try:
            plant_calculator.set_constructioncosts(cost_parameters=constrcosts)
        except KeyError or Exception:
            # TODO: raise the error in future versions
            # perf_indic.update({TPPN['construction_costs_eurperm3']: None})
            logger.warning(
                "Failed to calculate construction costs", exc_info=True)

        # Calculate investment and maintenance costs
        # TODO: implement

        # Step 4: update plant-wide properties (KPIs)
        # --------------------------------------------
        plant_calculator.update_plant_kpis()  # update cost related KPIs
        for prop_name, val in plant_calculator.plant_kpis.items():
            value = np.round(val, 3)
            if val is None:
                continue
            prop_obj, _ = TreatmentPlantProperty.objects.get_or_create(name=prop_name)  # noqa, E501
            TreatmentPlantPropertyValue.objects.update_or_create(
                treatmentplant=treatment_plant,
                property=prop_obj,
                defaults={'value': str(value)}
            )

        return redirect(
            'design_parameter_results', plant_id=treatment_plant.id)

    def form_invalid(self, formset):
        return self.render_to_response(self.get_context_data(formset=formset))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        treatment_plant = self.get_treatment_plant()
        formset = context.get('form') or self.get_form()

        # Build ordered technologies from TreatmentPlantLayout (by step)
        layouts = TreatmentPlantLayout.objects.filter(
            treatmentplant=treatment_plant).order_by('step').select_related('technology')
        tech_order = [lay.technology for lay in layouts]

        # Map tech id to Technology instance
        tech_map = {tech.id: tech for tech in tech_order}

        # Group forms by technology id preserving order
        from collections import OrderedDict
        forms_by_tech = OrderedDict()
        for tech in tech_order:
            forms_by_tech[tech] = []

        # For each form in the formset, determine its technology and attach
        # the form along with the human-readable property name
        from drinq.models import TechnologyProperty
        for form in formset.forms:
            # determine technology id from instance (saved) or initial
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

        context['forms_by_tech'] = forms_by_tech
        context['treatment_plant'] = treatment_plant
        context['formset'] = formset
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
