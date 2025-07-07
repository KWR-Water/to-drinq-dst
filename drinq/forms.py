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
    TreatmentPlantLayout
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

    # def __init__(self, **kwargs):
    #     initial = kwargs.pop('initial', None)
    #     option = initial.get('option', None) if initial else None
    #     # slug = initial.get('slug', None) if initial else None
    #     instance = kwargs.get('instance', None)
    #     if option is None and instance is not None:
    #         option = instance.option
    #     # if slug is None and instance is not None:
    #     #     slug = instance.slug
    #     super(TreatmentDesignSelectionForm, self).__init__(**kwargs)
    #     if option is not None:
    #         self.fields['option'].initial = option

    def clean_name(self):cleaned_data = super(TreatmentDesignSelectionForm, self).clean()
        if 'name' in cleaned_data.keys():
            name = cleaned_data['name']
            if len(name) < 3:
                raise forms.ValidationError(
                    "The name must be at least 3 characters long.")
            return name

    def clean_option(self):
        if self.cleaned_data['option'] is None:
            option = self.instance.option
            self.initial['option'] = option
            if option is not None:
                self.cleaned_data['option'] = option
                return option
        raise forms.ValidationError(
                "The option number of the treatment plant is required.")

