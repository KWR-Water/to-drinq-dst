# from multiform import MultiFormMixin
# from formtools.wizard.views import SessionWizardView
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin

from django.http import HttpResponse, Http404, HttpResponseRedirect, QueryDict
# from formtools.wizard.views import SessionWizardView
from django.views import generic
from django.forms import ValidationError
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect
from accounts.models import CustomUser
from drinq.models import (
    Compound,
    CompoundCas,
    Technology,
    DecidingFactor,
    DecidingFactorQuestion,
    DecidingFactorChoice,
    QuestionAnswer,
    MultiStepConfiguration,
)
from drinq.forms import (
    ConfigurationNameForm,
    WaterSourceForm,
    QuestionWizardForm,
    SessionSelectForm
    )
from drinq.chemistry_tools import smiles_to_svg
import drinq.decision_tree as dst


EXCLUDE_KEY = ['csrfmiddlewaretoken', 'next']
INITIAL_TOTAL_STEPS = 4
DECISION_TREE_MAX_STEPS = 100


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
        QuestionAnswer.objects.create(
            configuration=configuration,
            question=deciding_factor.question,
            decidingfactor=deciding_factor,
            answer=choice
        )
        current_decidingfactor = deciding_factor.get_children().get(
            choice=choice)
        next_decidingfactor, goto_next_step = self.get_next_decidingfactor(
            current_decidingfactor=current_decidingfactor)
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
                        decidingfactor_children = next_deciding_factor.get_children()  # noqa, E501
                else:
                    # No more children, break the loop
                    next_deciding_factor = None
                    goto_next_step = False
                    break
            if counter == DECISION_TREE_MAX_STEPS:
                goto_next_step = False
            return next_deciding_factor, goto_next_step
        except DecidingFactor.DoesNotExist:
            return None, False


class QuestionsCompleteView(generic.TemplateView):
    template_name = "drinq/form_complete.html"

    def dispatch(self, request, *args, **kwargs):
        session_key = kwargs.get('session_key', None)
        session = request.session
        if session_key is None:
            session_key = session.get('session_key', None)
        if 'configuration_id' not in session and session_key is not None:
            configuration_id = MultiStepConfiguration.objects.filter(
                session_key=session_key).first()
            if configuration_id is not None:
                session['configuration_id'] = configuration_id.id
        return super().dispatch(request, *args, **kwargs)

    def get(self, request: HttpResponse, *args, **kwargs):
        # querydata = process_form_data(post_request=request.POST)
        results = QuestionAnswer.objects.filter(
            configuration__id=request.session['configuration_id'])
        if results.exists():
            context = self.get_context_data(results=results)
            return render(
                request,
                template_name=self.template_name,
                context={'data': context})
        else:
            return HttpResponseRedirect(redirect('drinq_redirect'))

    def get_context_data(self, **kwargs):
        results = kwargs.get('results', None)
        choices, technologies, treatment_options = {}, [], []
        context = {
            'choices': choices,
            'technologies': technologies,
            'treatment_options': treatment_options,
        }
        if results is not None:
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
            context['treatment_options'] = dst.get_treatment_trains(
                technology_tuples=technologies)

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
    except Compound.DoesNotExist:
        raise Http404("Compound does not exist")
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
