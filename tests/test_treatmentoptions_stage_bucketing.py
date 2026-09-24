import django
from django.test import TestCase
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "drinq.settings")
django.setup()

from drinq.models import Technology, TechnologyRelatedtechnology
from drinq.views import _append_stage_buckets, _build_choice_buckets


class BuildChoiceBucketsTests(TestCase):
    """Regression tests for the treatment-train stage bucketing logic.

    Two distinct bugs are covered here:

    1. When a choice has multiple interchangeable technologies for the
       same stage (e.g. two coagulation variants), all alternatives must
       stay in a single bucket instead of being split into one bucket
       per alternative (which produced repeated coagulation-flocculation
       dropdown pairs).
    2. Buckets contributed by different, sequential choices must never
       be combined by positional index. Doing so previously collapsed
       nearly all technologies into the first two buckets ("Screening"
       absorbing everything, "Algae screening" becoming a mix).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.coag_a = Technology.objects.create(name='Coagulation A')
        cls.coag_b = Technology.objects.create(name='Coagulation B')
        cls.floc = Technology.objects.create(name='Flocculation')

        # Both coagulation alternatives point to the same next-step
        # flocculation technology, as described in the bug report: the
        # duplication does not stem from the design choices themselves.
        TechnologyRelatedtechnology.objects.create(
            technology=cls.coag_a, related_technology=cls.floc,
            relatedtechnology_is_nextstep=True)
        TechnologyRelatedtechnology.objects.create(
            technology=cls.coag_b, related_technology=cls.floc,
            relatedtechnology_is_nextstep=True)

        cls.screening = Technology.objects.create(name='Screening')
        cls.algae_screening = Technology.objects.create(
            name='Algae screening')

    def test_current_stage_alternatives_share_one_bucket(self):
        technology_ids = (self.coag_a.id, self.coag_b.id)

        choice_buckets = _build_choice_buckets(technology_ids)

        self.assertEqual(
            choice_buckets,
            [[self.coag_a.id, self.coag_b.id], [self.floc.id]])

    def test_sequential_choices_do_not_merge_by_position(self):
        # Simulates two unrelated, sequential deciding-factor choices
        # (e.g. "screening" and "algae screening"), neither of which
        # has a previous/next relation. Each contributes exactly one
        # bucket of its own; they must remain distinct, in order.
        stage_buckets: list[list[int]] = []
        stage_buckets = _append_stage_buckets(
            stage_buckets, _build_choice_buckets((self.screening.id,)))
        stage_buckets = _append_stage_buckets(
            stage_buckets,
            _build_choice_buckets((self.algae_screening.id,)))

        self.assertEqual(
            stage_buckets,
            [[self.screening.id], [self.algae_screening.id]])

    def test_repeated_stage_further_down_the_train_is_preserved(self):
        # A stage that legitimately reappears later in the sequence
        # (not merged with the earlier occurrence) must remain its own
        # bucket.
        stage_buckets: list[list[int]] = []
        stage_buckets = _append_stage_buckets(
            stage_buckets, _build_choice_buckets((self.screening.id,)))
        stage_buckets = _append_stage_buckets(
            stage_buckets,
            _build_choice_buckets((self.algae_screening.id,)))
        stage_buckets = _append_stage_buckets(
            stage_buckets, _build_choice_buckets((self.screening.id,)))

        self.assertEqual(
            stage_buckets,
            [
                [self.screening.id],
                [self.algae_screening.id],
                [self.screening.id],
            ])

    def test_full_choice_loop_keeps_coag_floc_pair_and_other_stages_apart(
            self):
        # End-to-end style check combining both bug scenarios: a
        # multi-alternative stage followed by unrelated single-choice
        # stages must not cross-contaminate.
        stage_buckets: list[list[int]] = []
        stage_buckets = _append_stage_buckets(
            stage_buckets, _build_choice_buckets((self.screening.id,)))
        stage_buckets = _append_stage_buckets(
            stage_buckets,
            _build_choice_buckets((self.coag_a.id, self.coag_b.id)))
        stage_buckets = _append_stage_buckets(
            stage_buckets,
            _build_choice_buckets((self.algae_screening.id,)))

        self.assertEqual(
            stage_buckets,
            [
                [self.screening.id],
                [self.coag_a.id, self.coag_b.id],
                [self.floc.id],
                [self.algae_screening.id],
            ])
