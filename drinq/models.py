# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models
from autoslug import AutoSlugField
from users.models import CustomUser


class Citation(models.Model):
    key = models.TextField(unique=True, blank=True, null=True)

    class Meta:
        # managed = False
        db_table = 'citation'


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


class DesignParameter(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    name = models.TextField(blank=True, null=True)
    units = models.TextField(blank=True, null=True)

    class Meta:
        # managed = False
        db_table = 'design_parameter'


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


class ProcessPerTechnology(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    # The composite primary key (process_id, technology_id) found, that is not supported. The first column is selected.
    process = models.OneToOneField(
        Process, models.DO_NOTHING, blank=True, null=True)
    technology = models.ForeignKey(
        'Technology', models.DO_NOTHING, blank=True, null=True)

    class Meta:
        # managed = False
        db_table = 'process_per_technology'
        verbose_name_plural = 'processes per technology'

    def __str__(self):
        return f"{self.technology} ({self.process})"


class RemovalEfficiency(models.Model):
    cid = models.ForeignKey(Compound, models.DO_NOTHING,
                            db_column='cid', blank=True, null=True)
    is_log10 = models.BooleanField(blank=True, null=True)
    # This field type is a guess.
    value = models.TextField(blank=True, null=True)
    citation = models.ForeignKey(
        Citation, models.DO_NOTHING, blank=True, null=True)
    process = models.ForeignKey(
        Process, models.DO_NOTHING, blank=True, null=True)

    class Meta:
        # managed = False
        db_table = 'removal_efficiency'
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


class Technology(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    name = models.TextField(unique=True, null=False)
    description = models.TextField(blank=True, null=True)
    slug = AutoSlugField(populate_from='name')

    class Meta:
        # managed = False
        db_table = 'technology'
        verbose_name_plural = "technologies"

    def __str__(self):
        return f"{self.name}"


class ConfiguredTechnologies(models.Model):
    id = models.AutoField(primary_key=True, null=False, unique=True)
    configuration = models.ForeignKey(
        Configuration, models.CASCADE, db_column='id')
    technology = models.ForeignKey(Technology, models.CASCADE, db_column='id')
    order = models.IntegerField(null=True)

    class Meta:
        # managed = False
        db_table = 'configured_technologies'

    def __str__(self):
        return f"Configuration {self.configuration}, technology: {self.technology}"
