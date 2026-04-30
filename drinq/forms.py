from django import forms
from django.contrib.auth import authenticate
# from django.contrib.auth.models import User
from accounts.models import CustomUser, UserProfile
from betterforms.multiform import MultiForm, MultiModelForm
from accounts.forms import (
    CustomUserAuthForm, CustomUserProfileForm)
from drinq.models import (
    MultiStepConfiguration,
    QuestionAnswer,
    DecidingFactor,
    DecidingFactorChoice,
    DecidingFactorQuestion,
    DesignTree,
    TreatmentPlant,
    TreatmentPlantLayout,
    TreatmentplantDesignParameter,
    DesignParameter,
    TreatmentPlantTechnologyPropertyValue,
    TechnologyPropertyJunction,
    TreatmentPlantWaterQualityParameterValue,
    WaterqualityParameter,
    # DecisionConfiguration,
    )

"""
Note 1. - When to use ModelForm (and when not)

See https://docs.djangoproject.com/en/5.0/topics/forms/modelforms/#django.forms.ModelForm

If you’re building a database-driven app, chances are you’ll have forms 
that map closely to Django models. For instance, you might have a BlogComment 
model, and you want to create a form that lets people submit comments. 
In this case, it would be redundant to define the field types in your form, 
because you’ve already defined the fields in your model.
For this reason, Django provides a helper class that lets you create a 
Form class from a Django model.

Note 2. - handling of forms in SessionWizardView is broken, or does not work as 
expected. I encountered a similar problem with the SessionWizardView as posted 
on StackOverflow:
https://stackoverflow.com/questions/33623023/sessionwizardview-state-only-saved-on-final-form-done-not-executed 
"""

AUTH_NAME = "user"
WATERSOURCE_NAME = "watersource"
WATERSOURCE_QUESTION_NAME = "q_sourcewater"
CONFIG_NAME = "configuration"

QUESTION_STEPS = [
    # AUTH_NAME,
    CONFIG_NAME,
    WATERSOURCE_NAME,
    'deciding_step1',
    'deciding_step2',
    'deciding_step3',
]   


class AuthMultiForm(MultiModelForm):
    """
    A MultiForm that wraps the custom authentication form and any additional
    info.
    """
    base_fields = {}
    # form_classes = {
    #     'auth_form': CustomUserAuthForm,
    #     'additional_form': CustomUserProfileForm,
    # }
    form_classes = {
        AUTH_NAME: CustomUserAuthForm,
        # 'profile': CustomUserProfileForm,
    }

    def clean(self):
        """
        If you need to validate interdependent data between the sub-forms,
        do so here and raise forms.ValidationError if needed.
        """
        cleaned_data = super().clean()
        identifier = cleaned_data[AUTH_NAME].get("username")
        password = cleaned_data[AUTH_NAME].get("password")
        # Adjust the parameters as needed for your authentication backend
        user = authenticate(username=identifier, password=password)
        if user is None:
            raise forms.ValidationError(
                "Invalid credentials. Please try again.")
        self.user = user  # Store the user for later use
        # self.profile = cleaned_data["profile"]  # Store the user for later use
        return cleaned_data

    def save(self, commit=True):
        # NB the save method can only be called from a MultiModelFormn
        objects = super(AuthMultiForm, self).save(commit=False)
        if commit:
            user = objects['user']
            user.save()
            # profile = objects['profile']
            # profile.user = user
            # profile.save()
        return objects


class ConfigurationNameForm(forms.ModelForm):
    class Meta:
        model = MultiStepConfiguration
        fields = ['name', 'description']


class WaterSourceForm(forms.ModelForm):
    class Meta:
        model = MultiStepConfiguration
        fields = ['water_source']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['water_source'].queryset = DesignTree.objects.all()
        watersource_q = DecidingFactorQuestion.objects.get(
            name=WATERSOURCE_QUESTION_NAME)
        self.fields['water_source'].label = watersource_q.text.capitalize()


class QuestionAnswerForm(forms.ModelForm):
    class Meta:
        model = QuestionAnswer
        fields = ['question', 'answer']


class QuestionWizardForm(forms.Form):
    def __init__(self, decidingfactor_id: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # id = kwargs.get('id', None)
        if decidingfactor_id is not None:
            deciding_factor = DecidingFactor.objects.get(pk=decidingfactor_id)
            # TODO: fix ugly code
            if deciding_factor.question is not None:
                self.set_form_fields(question=deciding_factor.question)
        else:
            raise forms.ValidationError("No deciding factor available.")

    def get_next_deciding_factor(self, deciding_factor):
        """
        Get the next deciding factor based on the current one.
        """
        try:
            next_deciding_factor = deciding_factor.get_children().first()
            return next_deciding_factor
        except DecidingFactor.DoesNotExist:
            return None

    def set_form_fields(self, question):
        """
        Set the form fields based on the current deciding factor.
        """
        queryset = DecidingFactorChoice.objects.filter(
            question=question)
        if len(queryset) == 0:
            raise forms.ValidationError(
                "No choices available for this question.")
        self.fields['choice'] = forms.ModelChoiceField(
            queryset=queryset,
            widget=forms.RadioSelect,
            label=question.text.capitalize(),
        )


class SessionSelectForm(forms.Form):
    config_objects = MultiStepConfiguration.objects
    session = forms.ModelChoiceField(
        queryset=config_objects.none(),
        label="Select a configuration",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['session'].queryset = self.config_objects.filter(
                user=user)


class TreatmentDesignSelectionForm(forms.ModelForm):
    option = forms.IntegerField(widget=forms.HiddenInput(), initial=None)

    class Meta:
        model = TreatmentPlant
        fields = ['name', 'description', 'option']
        widgets = {
            'option': forms.HiddenInput(),
            'name': forms.Textarea(attrs={'rows': 1}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def clean_name(self) -> str | None:
        cleaned_data = super(TreatmentDesignSelectionForm, self).clean()
        if 'name' in cleaned_data.keys():
            name = cleaned_data['name']
            if len(name) < 3:
                raise forms.ValidationError(
                    "The name must be at least 3 characters long.")
            return name

    def clean_option(self):
        option = self.cleaned_data.get('option', None)
        if option is None:
            option = self.instance.option
            self.initial['option'] = option
            self.cleaned_data['option'] = option
        if option:
            return option
        raise forms.ValidationError(
                "The option number of the treatment plant is required.")


class DesignParameterValueForm(forms.ModelForm):
    class Meta:
        model = TreatmentplantDesignParameter
        fields = ['designparameter', 'value']
        widgets = {
            'designparameter': forms.HiddenInput(),
            'value': forms.NumberInput(attrs={'class': 'parameter-value'}),
        }


DesignParameterValueFormSet = forms.modelformset_factory(
    TreatmentplantDesignParameter,
    form=DesignParameterValueForm,
    extra=0
)


class PlantDesignParametersForm(forms.ModelForm):
    """Wrapper ModelForm for a TreatmentPlant that exposes hidden ids and
    provides a helper to build a design-parameter formset for rendering.
    """
    treatmentplant_id = forms.IntegerField(widget=forms.HiddenInput)
    configuration_id = forms.IntegerField(widget=forms.HiddenInput)

    class Meta:
        model = TreatmentPlant
        fields = []

    def __init__(self, *args, designparameters_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        if designparameters_qs is None:
            designparameters_qs = DesignParameter.objects.all()
        self.designparameters_qs = designparameters_qs

    def get_designparameter_formset(self, treatmentplant=None):
        """Return a modelformset for `TreatmentplantDesignParameter` for the
        given `treatmentplant`. If no existing rows, create initial rows
        from `self.designparameters_qs` so the formset can render editable
        fields for each design parameter.
        """
        if treatmentplant is None:
            qs = TreatmentplantDesignParameter.objects.none()
        else:
            qs = TreatmentplantDesignParameter.objects.filter(treatmentplant=treatmentplant)

        if qs.exists():
            return DesignParameterValueFormSet(queryset=qs)

        # create initial data from designparameters
        initial = []
        for dp in self.designparameters_qs:
            initial.append({'designparameter': dp.id, 'value': None})
        return DesignParameterValueFormSet(queryset=qs, initial=initial)


class TreatmentTechPropertyValueForm(forms.ModelForm):
    class Meta:
        model = TreatmentPlantTechnologyPropertyValue
        fields = ['technology', 'technologyproperty', 'value']
        widgets = {
            'technology': forms.HiddenInput(),
            'technologyproperty': forms.HiddenInput(),
            'value': forms.NumberInput(attrs={'class': 'parameter-value'}),
        }


TreatmentPlantTechPropertyValueFormSet = forms.modelformset_factory(
    TreatmentPlantTechnologyPropertyValue,
    form=TreatmentTechPropertyValueForm,
    extra=0
)


class WaterQualityParameterValueForm(forms.ModelForm):
    class Meta:
        model = TreatmentPlantWaterQualityParameterValue
        fields = ['wq_tech_parameter', 'value']
        widgets = {
            'wq_tech_parameter': forms.HiddenInput(),
            'value': forms.NumberInput(attrs={'class': 'parameter-value'}),
        }


WaterQualityParameterValueFormSet = forms.modelformset_factory(
    TreatmentPlantWaterQualityParameterValue,
    form=WaterQualityParameterValueForm,
    extra=0,
    can_delete=False
)


def build_technology_property_initials(treatmentplant):
    """Return initial data for `TechnologyPropertyValueFormSet` by
    enumerating `TechnologyPropertyDefault` objects flagged as design
    parameters for the plant's technologies.
    """
    techs = TreatmentPlantLayout.objects.filter(treatmentplant=treatmentplant)
    tech_ids = techs.values_list('technology', flat=True)
    defaults = TechnologyPropertyJunction.objects.filter(
        technology__in=tech_ids,
        is_designparameter=1,
        is_digested=0,  # only include non-digestion params
    ).select_related('technology', 'property')

    initials = []
    # Only include properties with is_digested=0, even if they exist in the DB
    for td in defaults:
        # Defensive: skip if is_digested is True (shouldn't be in defaults,
        # but just in case)
        if getattr(td, 'is_digested', False):
            continue
        existing = TreatmentPlantTechnologyPropertyValue.objects.filter(
            treatmentplant=treatmentplant,
            technology=td.technology,
            technologyproperty=td.property,
        ).first()
        initials.append({
            'technology': td.technology.id,
            'technologyproperty': td.property.id,
            'value': existing.value if existing else td.default_value,
        })
    return initials
