# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models
from autoslug import AutoSlugField
from closuretree.models import ClosureModel


# class UserSetting(models.Model):
#     user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
#     theme = models.CharField(
#         max_length=100, choices=[('light', 'Light'), ('dark', 'Dark')],
#         default='light')
#     notifications = models.BooleanField(default=True)

#     def __str__(self):
#         return f"{self.user.username}'s settings"


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


class Configuration(models.Model):
    id = models.AutoField(primary_key=True, null=False, unique=True)
    name = models.TextField(unique=True, null=False)
    date_created = models.DateTimeField()

    class Meta:
        # managed = False
        db_table = 'configuration'

    def __str__(self):
        return f"Configuration: {self.name}"


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


class DecidingFactor(ClosureModel):
    id = models.AutoField(primary_key=True, unique=True)
    name = models.TextField(null=False, unique=True)
    parent = models.ForeignKey(
        "self",
        related_name='children',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        db_column='parent')
    description = models.TextField(blank=True, null=True)
    form_label = models.TextField(unique=True)
    # NB: when specifying a foreign key where the column name has an
    # underscore, we have to specify db_column (otherwise, it searches for the
    # wrong table).
    categorical_variable = models.ForeignKey(
        CategoricalVariable, on_delete=models.CASCADE,
        db_column='categorical_variable')
    design_tree = models.ForeignKey(
        "DesignTree",
        null=False,
        on_delete=models.CASCADE,
        db_column='design_tree')

    class Meta:
        # managed = False
        db_table = 'decidingfactor'

    def __str__(self) -> str:
        return f'{self.name}'


class Goal(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    goal = models.TextField(unique=True, null=False)
    description = models.TextField(blank=True, null=True)
    slug = AutoSlugField(populate_from='goal', )

    class Meta:
        # managed = False
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
    deciding_factor_true = models.ForeignKey(
        DecidingFactor, on_delete=models.CASCADE,
        db_column='deciding_factor')
    effective_technology = models.ForeignKey(
        Technology, on_delete=models.CASCADE, db_column='effective_technology')
    threshold_value = models.FloatField(null=True, db_column='threshold_value')

    class Meta:
        db_table = 'technology_decidingfactors'
        verbose_name_plural = "technology deciding factors"

    def __str__(self) -> str:
        d_f = DecidingFactor.objects.get(pk=self.deciding_factor_true.pk)
        d_f_name = d_f.name.replace('_', ' ')
        eff_tech = Technology.objects.get(pk=self.effective_technology.pk)

        return f"Condition: '{d_f_name}' is True, eff. technology: {eff_tech.name}"


# class DesignTreeDecidingFactors(ClosureModel):
#     id = models.AutoField(primary_key=True, unique=True)
#     parent = models.ForeignKey(
#         DecidingFactor,
#         related_name='children',
#         null=True,
#         blank=True,
#         on_delete=models.CASCADE,
#         db_column='parent')
#     child = models.ForeignKey(
#         DecidingFactor,
#         null=True,
#         blank=True,
#         on_delete=models.CASCADE,
#         db_column='child',
#         related_name='parent')
#     design_tree = models.ForeignKey(
#         DesignTree,
#         on_delete=models.CASCADE,
#         db_column='design_tree')
#     path_length = models.IntegerField(null=False)

#     class Meta:
#         # managed = False
#         db_table = 'designtree_decidingfactors'
#         verbose_name_plural = "design tree deciding factors"

#     def __unicode__(self):
#         return f"{self.id}"

#     def __str__(self) -> str:
#         return (
#             f"Form {self.id}, parent deciding factor: "
#             f"{self.parent}, child deciding factor: "
#             f"{self.child} and design tree id "
#             f"{self.design_tree}"
#         )


class ConfiguredTechnologies(models.Model):
    id = models.AutoField(primary_key=True, null=False, unique=True)
    configuration = models.ForeignKey(Configuration, models.CASCADE)
    technology = models.ForeignKey(Technology, models.CASCADE)
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
        Stage, on_delete=models.CASCADE, blank=True, null=True)
    technology = models.ForeignKey(
        Technology, on_delete=models.CASCADE, blank=True, null=True)

    class Meta:
        # managed = False
        db_table = 'stage_technologies'

    def __str__(self) -> str:
        stage_name = Stage.objects.get(pk=self.stage).name
        tech_name = Technology.objects.get(pk=self.technology).name
        return f"Stage: {stage_name}, technology: {tech_name}"


# class TC(ClosureModel):
#     """A test model."""

#     parent2 = models.ForeignKey(
#         "self",
#         related_name="children",
#         null=True,
#         blank=True,
#         on_delete=models.CASCADE,
#     )
#     name = models.CharField(max_length=32)
#     blah = models.ForeignKey(
#         "Blah", related_name="tcs", null=True, blank=True, on_delete=models.CASCADE,
#     )

#     class ClosureMeta(object):
#         """Closure options."""
#         parent_attr = "parent2"

#     def __unicode__(self):
#         return "%s: %s" % (self.pk, self.name)


# class Blah(models.Model):
#     """A test model for foreign keys"""
#     # class Meta:  # added by DV
#         # app_label = 'closuretree'  # added by DV
#     thing = models.CharField(max_length=32)


# class TCSUB(TC):
#     """Testing closure subclasses."""
#     # class Meta:
#         # app_label = 'closuretree_testcase'

#     extrafield = models.IntegerField()


# class TCSUB2(TCSUB):
#     """Testing closure subclasses."""
#     ef = models.IntegerField()


# class TCNoMeta(ClosureModel):
#     """A test model without a ClosureMeta."""
#     parent = models.ForeignKey(
#         "self",
#         related_name="children",
#         null=True,
#         blank=True,
#         on_delete=models.CASCADE,
#     )
#     name = models.CharField(max_length=32)


# class SentinelModel(ClosureModel):
#     """A model using a sentinel attribute."""
#     location = models.ForeignKey(
#         "IntermediateModel",
#         null=True,
#         blank=True,
#         on_delete=models.CASCADE,
#     )

#     @property
#     def parent(self):
#         """Return the object's parent."""
#         if self.location:
#             return self.location.real_parent

#     class ClosureMeta(object):
#         """Closure options."""
#         sentinel_attr = "location"
#         parent_attr = "parent"


# class IntermediateModel(models.Model):
#     """The intermediate model between the sentinel model
#         and its parent (itself).
#     """
#     real_parent = models.ForeignKey(
#         'SentinelModel',
#         null=True,
#         blank=True,
#         on_delete=models.CASCADE,
#     )


# class TCAbstract(ClosureModel):
#     """A test model with Meta.abstract = True."""

#     class Meta:
#         abstract = True

#     parent = models.ForeignKey(
#         "self",
#         related_name="children",
#         null=True,
#         blank=True,
#         on_delete=models.CASCADE,
#     )
#     name = models.CharField(max_length=32)


# class TCConcrete(TCAbstract):
#     """A test model inheriting from abstract base model."""
#     pass

# class UUIDTC(ClosureModel):
#     '''Testing support for models with a UUID primary key. See #30'''
#     primary_key = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     parent2 = models.ForeignKey(
#         "self",
#         related_name="children",
#         null=True,
#         blank=True,
#         on_delete=models.CASCADE,
#     )
#     name = models.CharField(max_length=32)

#     class ClosureMeta(object):
#         """Closure options."""
#         parent_attr = "parent2"

#     def __unicode__(self):
#         return "%s: %s" % (self.pk, self.name)