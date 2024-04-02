from django import forms

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
