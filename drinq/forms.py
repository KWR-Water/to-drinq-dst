from django import forms
from drinq.models import (
    Configuration, DesignTreeDecidingFactors, DecidingFactor
    )

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


# class TechnologyQuestionnaireDecidingFactors(forms.ModelForm):

#     def __init__(self,  *args, **kwargs):
#         # choice = kwargs.pop('choice', None)
#         # deciding_factors = None
#         form_flavour = kwargs.pop('form_flavour', 'simple')
#         selected = TechnologyQuestionnaireDecidingFactors.objects.filter(
#             form_flavour=form_flavour).only()
#         flavour_id = [f.id for f in selected]
#         self.select_by_form_flavour(form_flavour_id=flavour_id)

#         super(TechnologyQuestionnaireDecidingFactors, self).__init__(
#             *args, **kwargs)

#     def select_by_form_flavour(self, form_flavour_id: int):
#         entries_of_form_flavour = DesignTreeDecidingFactors.objects.filter(
#             form_flavour=form_flavour_id).all()

#         for entry in entries_of_form_flavour:
#             pk_deciding_factor = entry.deciding_factor
#             deciding_factor = DecidingFactor.objects.get(id=pk_deciding_factor)
#             forms.BooleanField(
#                 label=deciding_factor.description, required=False
#             )

#     class Meta:
#         model = DesignTreeDecidingFactors


# class UserForm(forms.ModelForm):
#     CHOICES = [
#         (choice.pk, choice.email) for choice in CustomUser.objects.all()]
#     username = forms.ChoiceField(
#         label='Your email (is username)', choices=CHOICES, required=True)

#     class Meta:
#         model = CustomUser
#         fields = ['username']


# Example from co-pilot:
#
# # forms.py
# from django import forms

# class EnqueteForm(forms.Form):
#     vraag1 = forms.ChoiceField(choices=[('ja', 'Ja'), ('nee', 'Nee')])
#     vraag2 = forms.CharField(required=False)
#     # Voeg andere velden toe zoals nodig

# # views.py
# from django.shortcuts import render
# from .forms import EnqueteForm

# def enquete_view(request):
#     if request.method == 'POST':
#         form = EnqueteForm(request.POST)
#         if form.is_valid():
#             antwoord_vraag1 = form.cleaned_data['vraag1']
#             # Voeg logica toe om de volgende vraag te bepalen op basis van antwoord_vraag1
#             # Bijvoorbeeld:
#             if antwoord_vraag1 == 'ja':
#                 volgende_vraag = 'Wat is je favoriete kleur?'
#             else:
#                 volgende_vraag = 'Wat is je leeftijd?'
#     else:
#         form = EnqueteForm()

#     return render(request, 'enquete.html', {'form': form, 'volgende_vraag': volgende_vraag})

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
