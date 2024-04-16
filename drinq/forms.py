from django import forms
from drinq.models import (CustomUser, Configuration)

"""
Note - When to use ModelForm (and when not)

See https://docs.djangoproject.com/en/5.0/topics/forms/modelforms/#django.forms.ModelForm

If you’re building a database-driven app, chances are you’ll have forms 
that map closely to Django models. For instance, you might have a BlogComment 
model, and you want to create a form that lets people submit comments. 
In this case, it would be redundant to define the field types in your form, 
because you’ve already defined the fields in your model.
For this reason, Django provides a helper class that lets you create a 
Form class from a Django model."""


class TechnologyForm(forms.Form):
    source_is_surfacewater = forms.BooleanField(
        label="Intake of surface water", required=False,
    )
    algae_high = forms.BooleanField(
        label="Has large amounts of algae", required=False,
    )
    nom_high = forms.BooleanField(
        label="Has high levels of NOM (> 5 ppm, or > 10 mg/l)",
        required=False,
    )

# class UserForm(forms.ModelForm):
#     CHOICES = [
#         (choice.pk, choice.email) for choice in CustomUser.objects.all()]
#     username = forms.ChoiceField(
#         label='Your email (is username)', choices=CHOICES, required=True)

#     class Meta:
#         model = CustomUser
#         fields = ['username']


class ConfigurationForm(forms.ModelForm):

    def __init__(self,  *args, **kwargs):
        choice = kwargs.pop('choice', None)
        super(Configuration, self).__init__(*args, **kwargs)

        if choice is not None:
            self.fields['name'] = forms.ChoiceField(
                choices=choice)

    class Meta:
        model = Configuration
        # fields = ['name']
        exclude = ['id']


# class DecidingFactorsForm(forms.ModelForm):
#     """_summary_

#     Args:
#         forms (_type_): _description_
#     """
#     pass
# class TechnologyStepsForm(forms.ModelForm):
#     """Form which guides user in the different technology design choices
#     TODO: this will replace the TechnologyForm above.
#     """

#     def __init__(self, *args, **kwargs):
#         choice = kwargs.pop('choice', None)
#         super(TechnologyStepsForm, self).__init__(*args, **kwargs)

#         if choice is not None:
#             self.fields['decisionchoices'] = forms.ChoiceField(
#                 choices=choice, label="Existing decisions")

#     class Meta:
#         model = Technology
        
#         # exclude = ['dataset']