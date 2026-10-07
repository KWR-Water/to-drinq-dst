from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from drinq.admin import NameLockedAdmin, ReadOnlyAdmin
from drinq.models import (
    ChemicalAgent,
    DecidingFactor,
    DecidingFactorChoice,
    DecidingFactorQuestion,
    DesignTree,
    MultiStepConfiguration,
    QuestionAnswer,
    Stage,
    StageTechnologies,
    Technology,
    TechnologyChemicalagentJunction,
    TechnologyDecidingFactorJunction,
    TechnologyKPI,
    TechnologyRelatedtechnology,
    TreatmentPlant,
    WaterqualityParameter,
    WaterqualityParameterTechnologyJunction,
)

DECISION_TREE_MODELS = (
    DesignTree,
    DecidingFactor,
    DecidingFactorQuestion,
    DecidingFactorChoice,
    TechnologyDecidingFactorJunction,
    TechnologyRelatedtechnology,
    QuestionAnswer,
)


class AdminCoverageTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.admin_user = user_model.objects.create_superuser(
            username='admin', password='secretpass', email='a@example.org')
        self.client.force_login(self.admin_user)

    def test_decision_tree_models_are_not_registered(self) -> None:
        for model in DECISION_TREE_MODELS:
            with self.subTest(model=model.__name__):
                self.assertFalse(admin.site.is_registered(model))

    def test_catalogue_models_are_registered(self) -> None:
        for model in (
            Technology, TechnologyKPI, WaterqualityParameter, ChemicalAgent,
            StageTechnologies, MultiStepConfiguration, TreatmentPlant,
        ):
            with self.subTest(model=model.__name__):
                self.assertTrue(admin.site.is_registered(model))

    def test_all_changelists_render(self) -> None:
        for model in admin.site._registry:
            opts = model._meta
            url = reverse(
                f'admin:{opts.app_label}_{opts.model_name}_changelist')
            with self.subTest(model=model.__name__):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_changelists_render_rows_of_junction_models(self) -> None:
        stage = Stage.objects.create(name='Stage A')
        technology = Technology.objects.create(name='Tech A')
        agent = ChemicalAgent.objects.create(name='Agent', slug='agent')
        parameter = WaterqualityParameter.objects.create(name='DOC')
        StageTechnologies.objects.create(stage=stage, technology=technology)
        TechnologyChemicalagentJunction.objects.create(
            technology=technology, chemical_agent=agent)
        WaterqualityParameterTechnologyJunction.objects.create(
            technology=technology, waterqualityparameter=parameter)
        for model in (
            StageTechnologies, TechnologyChemicalagentJunction,
            WaterqualityParameterTechnologyJunction,
        ):
            opts = model._meta
            url = reverse(
                f'admin:{opts.app_label}_{opts.model_name}_changelist')
            with self.subTest(model=model.__name__):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_read_only_models_cannot_be_added_or_changed(self) -> None:
        request = RequestFactory().get('/')
        request.user = self.admin_user
        for model, model_admin in admin.site._registry.items():
            if not isinstance(model_admin, ReadOnlyAdmin):
                continue
            with self.subTest(model=model.__name__):
                self.assertFalse(model_admin.has_add_permission(request))
                self.assertFalse(model_admin.has_change_permission(request))
                self.assertTrue(model_admin.has_view_permission(request))

    def test_name_is_read_only_after_creation(self) -> None:
        request = RequestFactory().get('/')
        request.user = self.admin_user
        kpi = TechnologyKPI.objects.create(name='power', unit='kW')
        model_admin = admin.site._registry[TechnologyKPI]
        self.assertIsInstance(model_admin, NameLockedAdmin)
        self.assertNotIn('name', model_admin.get_readonly_fields(request))
        self.assertIn('name', model_admin.get_readonly_fields(request, kpi))

    def test_technology_and_stage_names_are_locked(self) -> None:
        request = RequestFactory().get('/')
        request.user = self.admin_user
        objects = {
            Technology: Technology.objects.create(name='Tech'),
            Stage: Stage.objects.create(name='Stage'),
        }
        for model, instance in objects.items():
            model_admin = admin.site._registry[model]
            with self.subTest(model=model.__name__):
                self.assertIsInstance(model_admin, NameLockedAdmin)
                self.assertIn(
                    'name', model_admin.get_readonly_fields(request, instance))
