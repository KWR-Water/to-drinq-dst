from django.contrib import admin
from .models import (
    Compound, CompoundCas, CompoundSynonym, Technology, Process,
    Stage, Goal, RemovalEfficiency, ProcessPerTechnology,
    GoalPerTechnology, DesignParameter
    )

# Register your models here.
model_classes = [
    Compound, CompoundCas, CompoundSynonym, Technology, Process, Stage, Goal,
    RemovalEfficiency, ProcessPerTechnology, GoalPerTechnology,
]

slug_field_mapping = {
    Compound.__name__: ('cid'),
    CompoundCas.__name__: ('cas'),
    CompoundSynonym.__name__: None,
    Technology.__name__: ('name'),
    Process.__name__: ('name'),
    Stage.__name__: '(name)',
    Goal.__name__: '(goal)',
    RemovalEfficiency.__name__: None,
    ProcessPerTechnology.__name__: None,
    GoalPerTechnology.__name__: None,
    DesignParameter.__name__: None,
}

for model_class in model_classes:
    slug_value = slug_field_mapping[model_class.__name__]
    if slug_value is not None:
        prepopulated_fields = {'slug': slug_value}
        readonly_fields = 'slug'

admin.site.register(tuple(model_classes))
