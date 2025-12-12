# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models
from django.utils.text import slugify
from accounts.models import CustomUser
from autoslug import AutoSlugField
from closuretree.models import ClosureModel


class Citation(models.Model):
    key = models.TextField(unique=True, blank=True, null=True)

    class Meta:
        # managed = False
        db_table = 'citation'


class CategoricalVariable(models.Model):
    id = models.AutoField(primary_key=True, null=False, unique=True)
    name = models.TextField(unique=True, null=False)
    n_levels = models.IntegerField(null=False)

    class Meta:
        # managed = False
        db_table = 'categoricalvariable'
        verbose_name_plural = 'categorical variables'

    def __str__(self) -> str:
        return f"Categorical variable (pk={self.id}): {self.name}"


class Compound(models.Model):
    cid = models.IntegerField(primary_key=True, unique=True, null=False)
    common_name = models.TextField(blank=True, null=True)
    isomeric_smiles = models.TextField(unique=True, blank=True, null=True)
    # user = models.ForeignKey(
    #     CustomUser, related_name='users', on_delete=models.SET_NULL,
    #     blank=True, null=True, db_index=True)
    slug = AutoSlugField(populate_from='cid')

    class Meta:
        # managed = False
        db_table = 'compound'

    def __str__(self):
        return f"CID: {self.cid}"


class CompoundCas(models.Model):
    id = models.AutoField(primary_key=True, null=False, unique=True)
    cid = models.ForeignKey(Compound, models.CASCADE, db_column='cid')
    cas = models.TextField(blank=True, null=True)
    slug = AutoSlugField(populate_from='cas', unique_with=['cid'])

    class Meta:
        # managed = False
        db_table = 'compound_cas'
        verbose_name_plural = "CAS registry numbers"

    def __str__(self):
        return f"{self.cas} ({self.cid})"


class CompoundSynonym(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    cid = models.ForeignKey(Compound, models.CASCADE, db_column='cid')
    synonym = models.TextField(blank=True, null=True)

    class Meta:
        # managed = False
        db_table = 'compound_synonym'
        verbose_name_plural = 'compound synonyms'

    def __str__(self) -> str:
        return f'{self.synonym} ({self.cid})'


class MultiStepConfiguration(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True, max_length=500)
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='multistepforms',
        db_column='user',
        blank=True, null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    water_source = models.ForeignKey(
        'DesignTree',
        on_delete=models.SET_NULL,
        db_column='water_source',
        related_name='multistepforms',
        blank=True, null=True)
    session_key = models.CharField(max_length=40)

    class Meta:
        db_table = 'form_multistep'

    def __str__(self) -> str:
        return f'{self.name} ({self.user.username})'


class QuestionAnswer(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    question = models.ForeignKey(
        'DecidingFactorQuestion',
        db_column='question',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='questionanswers')
    answer = models.ForeignKey(
        'DecidingFactorChoice',
        on_delete=models.CASCADE,
        db_column='answer',
        blank=False,
        related_name='questionanswers')
    configuration = models.ForeignKey(
        MultiStepConfiguration,
        db_column='configuration',
        on_delete=models.CASCADE,
        blank=False,
        related_name='questionanswers')
    decidingfactor = models.ForeignKey(
        'DecidingFactor',
        db_column='decidingfactor',
        on_delete=models.CASCADE,
        blank=False,
        related_name='questionanswers')

    class Meta:
        db_table = 'form_questionanswer'

    def __str__(self) -> str:
        return f'{self.id} (deciding factor: {self.decidingfactor})'


class DecidingFactorQuestion(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    name = models.TextField(null=False, unique=True)
    text = models.TextField(null=False, blank=True)
    categorical_variable = models.ForeignKey(
        CategoricalVariable, on_delete=models.CASCADE,
        db_column='categoricalvariable')

    class Meta:
        db_table = 'decidingfactorquestion'

    def __str__(self) -> str:
        return f'{self.text}'


class DecidingFactorChoice(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    name = models.TextField(null=False, unique=True)
    text = models.TextField(null=False, blank=True)
    question = models.ForeignKey(
        DecidingFactorQuestion,
        on_delete=models.CASCADE,
        db_column='question',
        related_name='decidingfactorchoices_question',
        blank=True, null=True)
    design_tree = models.ForeignKey(
        'DesignTree',
        on_delete=models.CASCADE,
        db_column='designtree',
        related_name='decidingfactorchoices_designtree',
        blank=True, null=True)

    class Meta:
        db_table = 'decidingfactorchoice'

    def __str__(self) -> str:
        return f'{self.text}'


class DecidingFactor(ClosureModel):
    id = models.AutoField(primary_key=True, unique=True)
    # name = models.TextField(null=False, unique=True)
    parent = models.ForeignKey(
        "self",
        related_name='children',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        db_column='parent')
    question = models.ForeignKey(
        DecidingFactorQuestion,
        db_column='question',
        on_delete=models.SET_NULL,
        related_name='decidingfactors',
        unique=True,
        blank=True, null=True)
    choice = models.ForeignKey(
        DecidingFactorChoice,
        db_column='choice',
        on_delete=models.CASCADE,
        related_name='decidingfactors',
        unique=True,
        blank=True, null=True)
    # form_label = models.TextField(unique=True)
    # NB: when specifying a foreign key where the column name has an
    # underscore, we have to specify db_column (otherwise, it searches for the
    # wrong table).
    design_tree = models.ForeignKey(
        "DesignTree",
        null=False,
        on_delete=models.CASCADE,
        db_column='designtree')

    class Meta:
        db_table = 'decidingfactor'
        # constraints = [
        #     models.UniqueConstraint(
        #         # condition=models.Q(choice__isnull=True),
        #         fields=['name', 'question'],
        #         name='unique_namequestion',),
        #     models.UniqueConstraint(
        #         # condition=models.Q(question__isnull=True),
        #         fields=['name', 'choice'],
        #         name='unique_namechoice',
        #         )
        # ]
        # condition = [
        #     models.Q(question__isnull=True) | models.Q(choice__isnull=True)
        #     ]
        verbose_name_plural = 'deciding factors'
    
    def __str__(self) -> str:
        return f'{self.id} (parent: {self.parent}, ' \
               f'question: {self.question}, choice: {self.choice}, ' \
               f'design tree: {self.design_tree})'


class TreatmentPlant(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    configuration = models.ForeignKey(
        MultiStepConfiguration, models.CASCADE, blank=True, null=True,
        db_column='configuration')
    option = models.IntegerField(
        blank=False, null=False,
        help_text="Identifying number in a set of preliminary treatment design options"
        )
    name = models.TextField(blank=True, null=False)
    description = models.TextField(blank=True, null=True)
    slug = models.SlugField(unique=True, blank=True)

    class Meta:
        # managed = False
        db_table = 'treatmentplant'
        verbose_name_plural = "treatment plants"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while TreatmentPlant.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Plant (id: {self.id}, option: {self.option}), name: {self.name}"  # noqa: E501


class TreatmentPlantLayout(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    treatmentplant = models.ForeignKey(
        TreatmentPlant, models.CASCADE, blank=True, null=True,
        db_column='treatmentplant')
    step = models.IntegerField(blank=True, null=False)
    technology = models.ForeignKey(
        'Technology', models.CASCADE, blank=True, null=True,
        db_column='technology'
    )
    # removal_efficiency = models.FloatField(blank=True, null=True)
    # removal_efficiency_log10 = models.BooleanField(blank=True, null=True)

    class Meta:
        # managed = False
        db_table = 'treatmentplantlayout'
        verbose_name_plural = "treatment plant layouts"

    def __str__(self):
        return f"{self.treatmentplant} ({self.id})"


class TreatmentplantDesignParameter(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    treatmentplant = models.ForeignKey(
        TreatmentPlant, models.CASCADE, blank=True, null=True,
        db_column='treatmentplant')
    designparameter = models.ForeignKey(
        'DesignParameter', models.CASCADE, blank=True, null=True,
        db_column='designparameter')
    value = models.FloatField(blank=True, null=False)

    class Meta:
        # managed = False
        db_table = 'treatmentplant_designparametervalue'
        verbose_name_plural = "treatment plant design parameters"

    def __str__(self):
        return f"{self.treatmentplant} ({self.designparameter}): {self.value}"


class TreatmentPlantPropertyValue(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    treatmentplant = models.ForeignKey(
        TreatmentPlant,
        on_delete=models.CASCADE, blank=True, null=True,
        db_column='treatmentplant')
    property = models.ForeignKey(
        'TreatmentPlantProperty',
        on_delete=models.CASCADE, blank=True, null=True,
        db_column='property')
    value = models.TextField(blank=True, null=False)

    class Meta:
        # managed = False
        db_table = 'treatmentplant_propertyvalue'
        verbose_name_plural = "treatment plant property values"

    def __str__(self):
        return f"{self.treatmentplant} ({self.property}): {self.value}"


class TreatmentPlantProperty(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    name = models.TextField(unique=True, null=False)
    description = models.TextField(blank=True, null=True)
    unit = models.TextField(blank=True, null=True)
    category = models.ForeignKey(
        'ParameterCategory', models.CASCADE, blank=True, null=True,
        db_column='category')

    class Meta:
        # managed = False
        db_table = 'treatmentplantproperty'
        verbose_name_plural = "treatment plant properties"

    def __str__(self):
        return f"{self.name} ({self.id})"


class TreatmentPlantTechnologyPropertyValue(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    treatmentplant = models.ForeignKey(
        TreatmentPlant,
        on_delete=models.CASCADE, blank=True, null=True,
        db_column='treatmentplant')
    technology = models.ForeignKey(
        'Technology',
        on_delete=models.CASCADE, blank=True, null=True,
        db_column='technology')
    technologyproperty = models.ForeignKey(
        'TechnologyProperty',
        on_delete=models.CASCADE, blank=True, null=True,
        db_column='technologyproperty')
    value = models.TextField(blank=True, null=False)

    class Meta:
        # managed = False
        db_table = 'treatmentplant_technologypropertyvalue'
        verbose_name_plural = "treatment plant technology property values"

    def __str__(self):
        return f"{self.treatmentplant} ({self.technologyproperty}): {self.value}"


class DesignParameter(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    name = models.TextField(unique=True, null=False)
    description = models.TextField(blank=True, null=True)
    unit = models.TextField(blank=True, null=True)
    category = models.ForeignKey(
        'ParameterCategory', models.CASCADE, blank=True, null=True,
        db_column='category')
    slug = AutoSlugField(populate_from='name', unique=True)

    class Meta:
        # managed = False
        db_table = 'designparameter'
        verbose_name_plural = "design parameters"

    def __str__(self) -> str:
        return f"{self.name} ({self.id})"


class ParameterCategory(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    name = models.TextField(unique=True, null=False)
    description = models.TextField(blank=True, null=True)

    class Meta:
        # managed = False
        db_table = 'parametercategory'
        verbose_name_plural = "parameter categories"

    def __str__(self) -> str:
        return f"{self.name} ({self.id})"


class Goal(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    goal = models.TextField(unique=True, null=False)
    description = models.TextField(blank=True, null=True)
    slug = AutoSlugField(populate_from='goal', )

    class Meta:
        db_table = 'goal'

    def __str__(self) -> str:
        return f'{self.goal}'


class GoalPerTechnology(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    goal = models.ForeignKey(Goal, models.CASCADE, blank=True, null=True)
    technology = models.ForeignKey(
        'Technology', models.CASCADE, blank=True, null=True)

    class Meta:
        # managed = False
        db_table = 'goal_per_technology'
        verbose_name_plural = 'technologies and goals'

    def __str__(self) -> str:
        return f'{self.technology} ({self.goal})'


class Process(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    name = models.TextField(unique=True, null=False)
    description = models.TextField(blank=True, null=True)
    stage = models.ForeignKey('Stage', models.CASCADE, blank=True, null=True)
    slug = AutoSlugField(populate_from='name')

    class Meta:
        # managed = False
        db_table = 'process'
        verbose_name_plural = "processes"

    def __str__(self):
        return f"{self.name}"


# class ProcessPerTechnology(models.Model):
#     id = models.AutoField(primary_key=True, unique=True)
#     # The composite primary key (process_id, technology_id) found, that is not supported. The first column is selected.
#     process = models.OneToOneField(
#         Process, models.DO_NOTHING, blank=True, null=True)
#     technology = models.ForeignKey(
#         'Technology', models.DO_NOTHING, blank=True, null=True)

#     class Meta:
#         # managed = False
#         db_table = 'process_per_technology'
#         verbose_name_plural = 'processes per technology'

#     def __str__(self):
#         return f"{self.technology} ({self.process})"


class RemovalEfficiency(models.Model):
    cid = models.ForeignKey(Compound, models.DO_NOTHING,
                            db_column='cid', blank=True, null=True)
    is_log10 = models.BooleanField(blank=True, null=True)
    # This field type is a guess.
    value = models.FloatField(blank=True, null=True)
    citation = models.ForeignKey(
        Citation, models.DO_NOTHING, blank=True, null=True)
    process = models.ForeignKey(
        Process, models.DO_NOTHING, blank=True, null=True)

    class Meta:
        # managed = False
        db_table = 'removalefficiency'
        verbose_name_plural = "removal efficiencies"

    def __str__(self):
        return f"Removal compound {self.cid}: {self.value}"


class Stage(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    name = models.TextField(unique=True, null=False)
    description = models.TextField(blank=True, null=True)
    slug = AutoSlugField(populate_from='name')

    class Meta:
        # managed = False
        db_table = 'stage'

    def __str__(self):
        return f"{self.name} (id: {self.id})"


class StageStage(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    stage_current = models.ForeignKey(
        Stage, on_delete=models.CASCADE, blank=True, null=True,
        related_name='current')
    stage_next = models.ForeignKey(
        Stage, on_delete=models.CASCADE, blank=True, null=True,
        related_name='next')

    class Meta:
        # managed = False
        db_table = 'stage_stage'

    def __str__(self):
        current_name, current_id = (
            self.stage_current.name, self.stage_current.id,)
        next_name, next_id = (
            self.stage_next.name, self.stage_next.id,)
        return (
            f"current [{current_id}]: {current_name} - next [{next_id}]: "
            f"{next_name})")


class Technology(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    name = models.TextField(unique=True, null=False)
    description = models.TextField(blank=True, null=True)
    slug = AutoSlugField(populate_from='name')
    advantage = models.TextField(null=True, max_length=500)
    disadvantage = models.TextField(null=True, max_length=500)

    class Meta:
        # managed = False
        db_table = 'technology'
        verbose_name_plural = "technologies"

    def __str__(self):
        return f"{self.name}"


class TechnologyProperty(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    name = models.TextField(unique=True, null=False)
    description = models.TextField(blank=True, null=True)
    unit = models.TextField(blank=True, null=True)
    category = models.ForeignKey(
        'ParameterCategory', models.CASCADE, blank=True, null=True, 
        db_column='category')
    parent_property = models.ForeignKey(
        'TechnologyProperty', models.CASCADE, blank=True, null=True,
        db_column='parent_property', related_name='child_properties')

    class Meta:
        # managed = False
        db_table = 'technologyproperty'
        verbose_name_plural = "technology parametric properties"

    def __str__(self):
        return f"{self.name} [unit {self.unit}] (id: {self.id})"


class TechnologyPropertyDefault(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    technology = models.ForeignKey(
        'Technology', on_delete=models.CASCADE,
        db_column='technology')
    property = models.ForeignKey(
        'TechnologyProperty', on_delete=models.CASCADE,
        db_column='property')
    defaultvalue = models.FloatField(blank=True, null=False)

    class Meta:
        # managed = False
        db_table = 'technology_property'
        verbose_name_plural = "technology properties and their default values"

    def __str__(self):
        return f"{self.technology}: {self.property} ({self.defaultvalue})"


class DesignTree(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    name = models.TextField(unique=True)
    description = models.TextField(null=True)

    class Meta:
        # managed = False
        db_table = 'designtree'
        verbose_name_plural = "design trees"

    def __str__(self):
        return f"{self.name}"


class TechnologyDecidingFactors(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    choice = models.ForeignKey(
        DecidingFactorChoice, on_delete=models.CASCADE,
        db_column='choice', related_name='decidingfactorchoices')
    effective_technology = models.ForeignKey(
        Technology, on_delete=models.CASCADE, db_column='effective_technology')
    threshold_value = models.FloatField(null=True, db_column='threshold_value')

    class Meta:
        db_table = 'technology_decidingfactors'
        verbose_name_plural = "technology deciding factors"

    def __str__(self) -> str:
        d_f = DecidingFactor.objects.get(pk=self.choice.pk)
        d_f_name = d_f.name.replace('_', ' ')
        eff_tech = Technology.objects.get(pk=self.effective_technology.pk)

        return f"Condition: '{d_f_name}' is True, eff. technology: {eff_tech.name}"


class TechnologyConstructionCostParameter(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    technology = models.ForeignKey(
        Technology, on_delete=models.CASCADE, db_column='technology')
    a = models.FloatField(blank=True, null=False)
    b = models.FloatField(blank=True, null=False)
    c = models.FloatField(blank=True, null=False)
    plantproperty = models.ForeignKey(
        'TreatmentPlantProperty', on_delete=models.CASCADE,
        db_column='plantproperty', blank=True, null=True)
    technologyproperty = models.ForeignKey(
        'TechnologyProperty', on_delete=models.CASCADE,
        db_column='technologyproperty', blank=True, null=True)

    class Meta:
        # managed = False
        db_table = 'technology_constructioncostparameter'
        verbose_name_plural = "technology construction cost parameters"

    def __str__(self):
        return f"{self.id} [{self.technology}] ({self.a}, {self.b}, {self.c})"


class ConfiguredTechnologies(models.Model):
    id = models.AutoField(primary_key=True, null=False, unique=True)
    configuration = models.ForeignKey(
        MultiStepConfiguration, on_delete=models.CASCADE)
    technology = models.ForeignKey(
        Technology, on_delete=models.CASCADE)
    order = models.IntegerField(null=True)

    class Meta:
        # managed = False
        db_table = 'configured_technologies'

    def __str__(self):
        configuration = DecidingFactor.objects.get(pk=self.configuration)
        tech = DecidingFactor.objects.get(pk=self.technology)
        return f"Configuration: {configuration.name}, technology: {tech.name}"


class StageTechnologies(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    stage = models.ForeignKey(
        Stage, on_delete=models.CASCADE, blank=True, null=True,
        db_column='stage')
    technology = models.ForeignKey(
        Technology, on_delete=models.CASCADE, blank=True, null=True,
        db_column='technology')

    class Meta:
        # managed = False
        db_table = 'stage_technologies'

    def __str__(self) -> str:
        stage_name = Stage.objects.get(pk=self.stage).name
        tech_name = Technology.objects.get(pk=self.technology).name
        return f"Stage: {stage_name}, technology: {tech_name}"


class TechnologyRelatedtechnology(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    technology = models.ForeignKey(
        Technology, on_delete=models.CASCADE, blank=True, null=True,
        db_column='technology', related_name='tech')
    related_technology = models.ForeignKey(
        Technology, on_delete=models.CASCADE, blank=True, null=True,
        db_column='relatedtechnology', related_name='related_tech')

    class Meta:
        # managed = False
        db_table = 'technology_relatedtechnology'

    def __str__(self) -> str:
        tech_name = Technology.objects.get(pk=self.technology).name
        relatedtech_name = Technology.objects.get(pk=self.related_technology).name
        return f"Technology: {tech_name}, related technology: {relatedtech_name}"


class Watercompany(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    name = models.TextField(unique=True, null=True, blank=True)

    class Meta:
        # managed = False
        db_table = 'watercompany'

    def __str__(self) -> str:
        return f"{self.name}"

