"""Test portable removal exports and their database integrity rules."""

import csv
import hashlib
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase as DjangoTestCase
from django.urls import reverse

from drinq.models import (
    Citation,
    Compound,
    CompoundCas,
    CompoundRemovalSummary,
    CompoundSynonym,
    Process,
    RemovalDataset,
)
from research.export_removal_data import (
    DATASET_KEY,
    PROCESSED_DIRECTORY,
    SOURCE_KEYS,
    export_removal_data,
    load_summaries,
    normalize_identifier,
    read_csv_rows,
    resolve_cid,
    valid_cas,
)


class RemovalExportTests(TestCase):
    """Check that the CSV export preserves identity and source statistics."""

    def test_all_compounds_are_covered_without_merging_synonyms(self) -> None:
        summaries = load_summaries(PROCESSED_DIRECTORY)
        self.assertEqual(len(summaries), 201)
        self.assertEqual(len({row.compound_cid for row in summaries}), 46)
        self.assertEqual(sum(row.std_percent is None for row in summaries), 9)
        self.assertTrue(all(row.sample_count is None for row in summaries))
        uv_rows = [
            row
            for row in summaries
            if row.compound_cid == 2336 and row.process_name == 'UV'
        ]
        self.assertEqual(len(uv_rows), 2)
        self.assertEqual(
            {row.source_substance_label for row in uv_rows},
            {'Benzo(a)pyrene', 'Benzopyrene'},
        )
        self.assertEqual(summaries[0].source_row_number, 4)
        self.assertEqual(summaries[-1].source_row_number, 204)

    def test_identifier_resolution_is_conservative(self) -> None:
        lookup = {'benzopyrene': {2336}, 'ambiguous': {1, 2}}
        self.assertEqual(resolve_cid(' Benzopyrene ', lookup), 2336)
        for label in ('unknown', 'ambiguous'):
            with self.subTest(label=label), self.assertRaises(ValueError):
                resolve_cid(label, lookup)
        self.assertNotEqual(
            normalize_identifier('acesulfame'),
            normalize_identifier('acesulfame-k'),
        )
        self.assertTrue(valid_cas('58-08-2'))
        self.assertFalse(valid_cas('58-08-3'))
        self.assertFalse(valid_cas('None'))

    def test_exports_are_reproducible_and_preserve_nulls(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            for name in (
                'table_compound.csv',
                'table_synonyms_cid.csv',
                'table_cas_cid.csv',
                'cecs_removal_eff_mean_std.csv',
            ):
                (directory / name).write_bytes(
                    (PROCESSED_DIRECTORY / name).read_bytes()
                )
            self.assertEqual(export_removal_data(directory), 201)
            destination = directory / 'removal'
            before = {
                path.name: path.read_bytes()
                for path in destination.glob('*.csv')
            }
            export_removal_data(directory)
            self.assertEqual(
                before,
                {
                    path.name: path.read_bytes()
                    for path in destination.glob('*.csv')
                },
            )
            dataset_rows = read_csv_rows(destination / 'removal_dataset.csv')
            dataset = dict(zip(dataset_rows[0], dataset_rows[1], strict=True))
            self.assertEqual(dataset.get('key'), DATASET_KEY)
            self.assertEqual(
                dataset.get('source_sha256'),
                hashlib.sha256(
                    (directory / 'cecs_removal_eff_mean_std.csv').read_bytes()
                ).hexdigest(),
            )
            self.assertEqual(
                read_csv_rows(destination / 'removal_dataset_source.csv'),
                [['dataset_key', 'citation_key']]
                + [[DATASET_KEY, key] for key in SOURCE_KEYS],
            )
            self.assertNotIn('source_citation_keys', dataset)
            self.assertNotIn('provided_by', dataset)
            self.assertNotIn(
                'Annemarie van Wezel', dataset.get('provenance_notes', '')
            )
            citation_rows = read_csv_rows(destination / 'citation.csv')
            self.assertEqual(
                citation_rows[0],
                [
                    'key',
                    'reference',
                    'doi',
                    'url',
                    'notes',
                ],
            )
            self.assertEqual(len(citation_rows), 5)
            self.assertEqual(
                {row[0] for row in citation_rows[1:]},
                {dataset.get('publication_key'), *SOURCE_KEYS},
            )
            self.assertTrue(all(row[1] for row in citation_rows[1:]))
            self.assertEqual(
                citation_rows[1][2], '10.1016/j.jenvman.2017.02.002'
            )
            self.assertTrue(all(row[2] == '' for row in citation_rows[2:]))
            self.assertTrue(all(row[4] for row in citation_rows[2:]))
            self.assertEqual(len(before), 5)
            with (destination / 'compound_removal_summary.csv').open(
                encoding='utf-8',
                newline='',
            ) as stream:
                rows = list(csv.DictReader(stream, delimiter=';'))
            self.assertEqual(len(rows), 201)
            self.assertEqual(
                sum(row.get('std_percent') == '' for row in rows), 9
            )


class RemovalImportTests(DjangoTestCase):
    """Verify atomic, repeatable imports on a disposable database."""

    def test_import_is_repeatable_and_keeps_source_rows(self) -> None:
        call_command('import_removal_data', stdout=StringIO())
        first_counts = (
            Compound.objects.count(),
            CompoundCas.objects.count(),
            CompoundSynonym.objects.count(),
        )
        call_command('import_removal_data', stdout=StringIO())
        self.assertEqual(CompoundRemovalSummary.objects.count(), 201)
        self.assertEqual(Compound.objects.count(), 46)
        self.assertEqual(Citation.objects.count(), 4)
        self.assertEqual(Process.objects.count(), 7)
        self.assertEqual(
            first_counts,
            (
                Compound.objects.count(),
                CompoundCas.objects.count(),
                CompoundSynonym.objects.count(),
            ),
        )
        self.assertFalse(CompoundCas.objects.filter(cas='None').exists())
        self.assertEqual(
            CompoundRemovalSummary.objects.filter(std_percent=None).count(), 9
        )
        self.assertEqual(
            CompoundRemovalSummary.objects.filter(
                compound_id=2336,
                process__name='UV',
            ).count(),
            2,
        )

    def test_dry_run_does_not_insert_data(self) -> None:
        call_command('import_removal_data', dry_run=True, stdout=StringIO())
        self.assertEqual(Compound.objects.count(), 0)
        self.assertEqual(Citation.objects.count(), 0)
        self.assertEqual(RemovalDataset.objects.count(), 0)

    def test_conflicting_snapshot_rolls_back(self) -> None:
        call_command('import_removal_data', stdout=StringIO())
        summary = CompoundRemovalSummary.objects.first()
        self.assertIsNotNone(summary)
        if summary is None:
            self.fail('Import did not create summaries.')
        summary.mean_percent = 1
        summary.save()
        with self.assertRaises(CommandError):
            call_command('import_removal_data', stdout=StringIO())
        summary.refresh_from_db()
        self.assertEqual(summary.mean_percent, 1)
        self.assertEqual(CompoundRemovalSummary.objects.count(), 201)


class RemovalPageTests(DjangoTestCase):
    """Exercise identifier lookup, reverse browsing, and provenance display."""

    @classmethod
    def setUpTestData(cls) -> None:
        call_command('import_removal_data', stdout=StringIO())
        get_user_model().objects.create_user(username='removal-browser-test')

    def setUp(self) -> None:
        self.client.force_login(
            get_user_model().objects.get(username='removal-browser-test')
        )

    def test_requires_login(self) -> None:
        self.client.logout()
        response = self.client.get(reverse('removal_rates'))
        self.assertEqual(response.status_code, 302)

    def test_menu_and_both_lookup_modes_are_available(self) -> None:
        response = self.client.get(reverse('removal_rates'))
        self.assertContains(response, 'Substance removal rates')
        self.assertContains(response, 'By substance')
        self.assertContains(response, 'By technology')
        self.assertContains(response, 'CAS number, synonym, or CID')

    def test_cas_and_synonym_find_the_same_compound(self) -> None:
        for search in ('58-08-2', '1,3,7-trimethylxanthine', '2519'):
            with self.subTest(search=search):
                response = self.client.get(
                    reverse('removal_rates'),
                    {'q': search},
                )
                self.assertContains(response, 'caffeine')
                self.assertContains(response, 'CID 2519')
                self.assertContains(response, 'References')

    def test_suggestions_find_names_cas_synonyms_and_cids(self) -> None:
        for search in ('caffe', '58-08-2', '1,3,7-trimethylxanthine', '2519'):
            with self.subTest(search=search):
                response = self.client.get(
                    reverse('removal_rates'),
                    {
                        'suggest': '1',
                        'q': search,
                    },
                )
                self.assertEqual(response.status_code, 200)
                results = response.json().get('results', [])
                caffeine = [row for row in results if row.get('cid') == 2519]
                self.assertEqual(len(caffeine), 1)
                self.assertIn('58-08-2', caffeine[0].get('cas_numbers', []))

    def test_suggestions_are_bounded_and_prefer_common_name_prefixes(
        self,
    ) -> None:
        response = self.client.get(
            reverse('removal_rates'),
            {
                'suggest': '1',
                'q': 'ca',
            },
        )
        results = response.json().get('results', [])
        self.assertLessEqual(len(results), 15)
        self.assertEqual(results[0].get('name'), 'caffeine')
        self.assertEqual(
            len({row.get('cid') for row in results}), len(results)
        )
        Compound.objects.create(cid=999999, common_name='caffeine unreported')
        response = self.client.get(
            reverse('removal_rates'),
            {
                'suggest': '1',
                'q': 'caffeine unreported',
            },
        )
        self.assertEqual(response.json().get('results'), [])

    def test_met_does_not_match_inside_systematic_synonyms(self) -> None:
        for parameters in ({'q': 'met'}, {'q': 'met', 'suggest': '1'}):
            with self.subTest(parameters=parameters):
                response = self.client.get(
                    reverse('removal_rates'),
                    parameters,
                )
                if parameters.get('suggest'):
                    cids = {
                        row.get('cid')
                        for row in response.json().get('results', [])
                    }
                else:
                    cids = {
                        compound.pk
                        for compound in response.context['compounds']
                    }
                self.assertNotIn(2256, cids)
                self.assertNotIn(3036, cids)
                self.assertTrue({4169, 4171, 594330}.issubset(cids))

    def test_synonym_prefix_and_common_name_substring_still_match(
        self,
    ) -> None:
        for query, cid in (('PARACE', 1983), ('methox', 5329)):
            with self.subTest(query=query):
                response = self.client.get(
                    reverse('removal_rates'),
                    {
                        'suggest': '1',
                        'q': query,
                    },
                )
                self.assertIn(
                    cid,
                    {
                        row.get('cid')
                        for row in response.json().get('results', [])
                    },
                )

    def test_selected_substance_shows_five_distinct_synonyms_in_grey(
        self,
    ) -> None:
        CompoundSynonym.objects.filter(cid_id=2519).delete()
        for index in range(12):
            CompoundSynonym.objects.create(
                cid_id=2519,
                synonym=f'Alias {index:02}',
            )
        for synonym in ('Alias 00', 'alias 00', 'CAFFEINE', '', None):
            CompoundSynonym.objects.create(cid_id=2519, synonym=synonym)
        response = self.client.get(
            reverse('removal_rates'),
            {'compound': 2519},
        )
        self.assertEqual(
            response.context['synonyms'],
            [f'Alias {index:02}' for index in range(5)],
        )
        self.assertTrue(response.context['more_synonyms'])
        self.assertContains(
            response,
            '<p class="text-muted removal-identifiers">Synonyms:',
        )
        self.assertContains(response, 'List truncated (5 shown)')
        self.assertNotContains(response, 'Alias 05')

    def test_identifier_aliases_are_removed_before_the_display_limit(
        self,
    ) -> None:
        CompoundSynonym.objects.filter(cid_id=2519).delete()
        identifiers = (
            '07e4fb58-fd79-4175-8e3d-05bf96954522',
            '0123456789abcdef0123456789abcdef',
            '0123456789ABCDEF0123456789ABCDEF',
            'RYYVLZVUVIJVGH-UHFFFAOYSA-N',
            '58-08-2',
            '1gfz',
            '3g6a5w338e',
            'CHEBI:27732',
            'CHEMBL113',
            'DTXSID0020232',
            'NSC-5036',
            'MFCD00005758',
            'InChI=1S/C8H10N4O2',
        )
        names = ('1,3,7-trimethylxanthine', 'guaranine', 'theine')
        for synonym in (*identifiers, *names):
            CompoundSynonym.objects.create(cid_id=2519, synonym=synonym)
        response = self.client.get(
            reverse('removal_rates'),
            {'compound': 2519},
        )
        self.assertEqual(response.context['synonyms'], list(names))
        self.assertFalse(response.context['more_synonyms'])
        self.assertNotContains(response, 'List truncated')
        for identifier in identifiers:
            with self.subTest(identifier=identifier):
                self.assertNotIn(identifier, response.context['synonyms'])
        self.assertContains(response, 'CAS 58-08-2')
        self.assertNotContains(
            response,
            '07e4fb58-fd79-4175-8e3d-05bf96954522',
        )

    def test_exactly_five_names_does_not_claim_truncation(self) -> None:
        CompoundSynonym.objects.filter(cid_id=2519).delete()
        for index in range(5):
            CompoundSynonym.objects.create(
                cid_id=2519,
                synonym=f'Chemical name {index}',
            )
        response = self.client.get(
            reverse('removal_rates'),
            {'compound': 2519},
        )
        self.assertEqual(len(response.context['synonyms']), 5)
        self.assertFalse(response.context['more_synonyms'])
        self.assertNotContains(response, 'List truncated')

    def test_substance_without_synonyms_omits_empty_synonym_line(self) -> None:
        CompoundSynonym.objects.filter(cid_id=2519).delete()
        response = self.client.get(
            reverse('removal_rates'),
            {'compound': 2519},
        )
        self.assertNotContains(response, 'Synonyms:')
        self.assertFalse(response.context['more_synonyms'])

    def test_suggestions_validate_query_and_require_login(self) -> None:
        for search in ('', 'c', 'not-a-real-substance'):
            with self.subTest(search=search):
                response = self.client.get(
                    reverse('removal_rates'),
                    {
                        'suggest': '1',
                        'q': search,
                    },
                )
                self.assertEqual(response.json().get('results'), [])
        response = self.client.get(
            reverse('removal_rates'),
            {
                'suggest': '1',
                'q': 'c' * 201,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.client.logout()
        response = self.client.get(
            reverse('removal_rates'),
            {
                'suggest': '1',
                'q': 'ca',
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_selected_substance_keeps_duplicate_source_summaries(self) -> None:
        response = self.client.get(
            reverse('removal_rates'),
            {'compound': 2336},
        )
        self.assertContains(response, '7 reported summaries')
        self.assertContains(response, 'Benzo(a)pyrene')
        self.assertContains(response, 'Benzopyrene')
        self.assertContains(response, 'Not reported')

    def test_technology_selection_displays_substances_and_deviations(
        self,
    ) -> None:
        process = Process.objects.get(name='PAC')
        response = self.client.get(
            reverse('removal_rates'),
            {
                'mode': 'technology',
                'process': process.pk,
            },
        )
        self.assertContains(response, 'caffeine')
        self.assertContains(response, '34.57')
        self.assertContains(response, 'SD (percentage points)')
        self.assertContains(response, 'Not reported')

    def test_references_are_honestly_labelled_and_include_publication(
        self,
    ) -> None:
        response = self.client.get(
            reverse('removal_rates'),
            {'compound': 2519},
        )
        self.assertContains(response, 'Database publication')
        self.assertContains(response, '10.1016/j.jenvman.2017.02.002')
        self.assertContains(response, 'Dataset-level removal-rate sources')
        self.assertContains(response, 'TAPES - De Watergroep')
        self.assertContains(response, 'Individual-study attribution')
        self.assertContains(response, 'data-reference-dialog')

    def test_invalid_identifiers_and_empty_search_are_handled(self) -> None:
        for value in ('invalid', '-1', '9999999999999999999999999'):
            with self.subTest(value=value):
                response = self.client.get(
                    reverse('removal_rates'),
                    {'compound': value},
                )
                self.assertContains(
                    response, 'selected substance is not available'
                )
        response = self.client.get(
            reverse('removal_rates'),
            {'q': 'not-a-real-substance'},
        )
        self.assertContains(response, 'No substances match')

    def test_search_does_not_render_unescaped_input(self) -> None:
        response = self.client.get(
            reverse('removal_rates'),
            {'q': '<script>alert(1)</script>'},
        )
        self.assertNotContains(response, '<script>alert(1)</script>')


class RemovalModelTests(DjangoTestCase):
    """Exercise the summary constraints against a disposable test database."""

    def setUp(self) -> None:
        self.compound = Compound.objects.create(cid=2336)
        self.process = Process.objects.create(name='UV')
        self.citation = Citation.objects.create(key='fischer2017decision')
        self.dataset = RemovalDataset.objects.create(
            key=DATASET_KEY,
            title='Test removal summaries',
            source_file='test.csv',
            source_sha256='a' * 64,
            publication=self.citation,
            aggregation_method='Source summaries',
        )

    def test_existing_key_only_citations_can_store_bibliography(self) -> None:
        self.assertEqual(self.citation.reference, '')
        self.assertEqual(self.citation.doi, '')
        self.assertEqual(self.citation.url, '')
        self.assertEqual(self.citation.notes, '')
        self.citation.reference = 'Fischer et al. (2017).'
        self.citation.doi = '10.1016/j.jenvman.2017.02.002'
        self.citation.url = 'https://doi.org/10.1016/j.jenvman.2017.02.002'
        self.citation.notes = 'Database publication.'
        self.citation.full_clean()
        self.citation.save()
        self.citation.refresh_from_db()
        self.assertEqual(self.citation.reference, 'Fischer et al. (2017).')
        self.assertEqual(self.citation.notes, 'Database publication.')

    def create_summary(
        self,
        row_number: int = 4,
        mean: float = 50,
        std: float | None = None,
        count: int | None = None,
    ) -> CompoundRemovalSummary:
        """Insert a summary with explicit source identity and statistics."""
        return CompoundRemovalSummary.objects.create(
            compound=self.compound,
            process=self.process,
            dataset=self.dataset,
            source_row_number=row_number,
            source_substance_label='Benzopyrene',
            source_treatment_label='UV',
            mean_percent=mean,
            std_percent=std,
            sample_count=count,
        )

    def test_distinct_source_rows_can_share_cid_and_process(self) -> None:
        first = self.create_summary()
        self.create_summary(row_number=5)
        self.assertEqual(first.compound_id, 2336)
        self.assertIsNone(first.std_percent)
        self.assertEqual(
            CompoundRemovalSummary.objects.filter(
                dataset=self.dataset
            ).count(),
            2,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_summary()

    def test_invalid_statistics_and_source_rows_are_rejected(self) -> None:
        for mean in (-1, 101):
            with (
                self.subTest(mean=mean),
                self.assertRaises(IntegrityError),
                transaction.atomic(),
            ):
                self.create_summary(mean=mean)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_summary(std=-1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_summary(count=0)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_summary(row_number=0)

    def test_referenced_records_are_protected_and_sources_are_multiple(
        self,
    ) -> None:
        self.create_summary()
        source = Citation.objects.create(key='snyder2007removal')
        self.dataset.sources.add(self.citation, source)
        self.assertEqual(self.dataset.sources.count(), 2)
        for instance in (
            self.compound,
            self.process,
            self.dataset,
            self.citation,
        ):
            with (
                self.subTest(instance=instance),
                self.assertRaises(ProtectedError),
            ):
                instance.delete()
