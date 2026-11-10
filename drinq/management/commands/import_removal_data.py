"""Import validated removal snapshots and their chemical identifiers."""

import csv
import hashlib
from argparse import ArgumentParser
from dataclasses import astuple
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

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
    SUMMARY_COLUMNS,
    load_summaries,
    normalize_identifier,
    read_csv_rows,
    valid_cas,
)


def read_records(path: Path) -> list[dict[str, str]]:
    """Read structured import records without losing quoted delimiters."""
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream, delimiter=';'))


def required(record: dict[str, str], field: str) -> str:
    """Reject absent required fields before importing an incomplete record."""
    value: str = record.get(field, '')
    if not value:
        raise CommandError(f'Missing required field: {field}')
    return value


class Command(BaseCommand):
    """Import a removal snapshot atomically without replacing existing data."""

    help = 'Import removal CSVs, compounds, CAS numbers, and synonyms.'

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Accept a portable CSV directory and a rollback-only preview."""
        parser.add_argument(
            '--directory',
            default=str(settings.BASE_DIR / 'research/data/processed/removal'),
        )
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args: object, **options: object) -> None:
        """Validate and import all linked tables in one transaction."""
        directory = Path(str(options.get('directory')))
        try:
            with transaction.atomic():
                count = self.import_snapshot(directory)
                if options.get('dry_run'):
                    transaction.set_rollback(True)
        except (OSError, ValueError, IntegrityError) as error:
            raise CommandError(str(error)) from error
        action = (
            'Validated (rolled back)' if options.get('dry_run') else 'Imported'
        )
        self.stdout.write(self.style.SUCCESS(f'{action}: {count} summaries.'))

    def import_snapshot(self, directory: Path) -> int:
        """Preserve source identities and reject changed snapshot records."""
        processed = directory.parent
        dataset_records = read_records(directory / 'removal_dataset.csv')
        if len(dataset_records) != 1:
            raise CommandError('Expected exactly one removal dataset.')
        metadata = dataset_records[0]
        source_name = required(metadata, 'source_file')
        if Path(source_name).name != source_name:
            raise CommandError('Source file must be a filename.')
        checksum = hashlib.sha256(
            (processed / source_name).read_bytes()
        ).hexdigest()
        if checksum != required(metadata, 'source_sha256'):
            raise CommandError('Removal source checksum does not match.')
        summaries = load_summaries(processed)
        exported = read_csv_rows(directory / 'compound_removal_summary.csv')
        expected = [list(SUMMARY_COLUMNS)] + [
            ['' if value is None else str(value) for value in astuple(row)]
            for row in summaries
        ]
        if exported != expected:
            raise CommandError('Summary CSV does not match the source data.')
        citations: dict[str, Citation] = {}
        for record in read_records(directory / 'citation.csv'):
            key = required(record, 'key')
            if key in citations:
                raise CommandError(f'Duplicate citation: {key}')
            values = {
                'reference': required(record, 'reference'),
                'doi': record.get('doi', ''),
                'url': record.get('url', ''),
                'notes': record.get('notes', ''),
            }
            citation, created = Citation.objects.get_or_create(
                key=key,
                defaults=values,
            )
            if not created:
                current = (
                    citation.reference,
                    citation.doi,
                    citation.url,
                    citation.notes,
                )
                incoming = tuple(values.values())
                if any(current) and current != incoming:
                    raise CommandError(f'Conflicting citation: {key}')
                citation.reference, citation.doi = incoming[:2]
                citation.url, citation.notes = incoming[2:]
                citation.save()
            citations[key] = citation
        compounds: dict[int, Compound] = {}
        for _, cid_text, smiles, name in read_csv_rows(
            processed / 'table_compound.csv'
        )[1:]:
            cid = int(cid_text)
            compound, created = Compound.objects.get_or_create(
                cid=cid,
                defaults={'common_name': name, 'isomeric_smiles': smiles},
            )
            if (
                not created
                and compound.isomeric_smiles
                and compound.isomeric_smiles != smiles
            ):
                raise CommandError(f'Conflicting structure for CID {cid}')
            compounds[cid] = compound
        for _, cas, cid_text in read_csv_rows(processed / 'table_cas_cid.csv')[
            1:
        ]:
            if valid_cas(cas.strip()):
                CompoundCas.objects.get_or_create(
                    cid=compounds.get(int(cid_text)),
                    cas=cas.strip(),
                )
        known_synonyms = {
            (cid, normalize_identifier(name))
            for cid, name in CompoundSynonym.objects.filter(
                cid_id__in=compounds,
            ).values_list('cid_id', 'synonym')
            if name
        }
        for _, cid_text, synonym in read_csv_rows(
            processed / 'table_synonyms_cid.csv'
        )[1:]:
            pair = (int(cid_text), normalize_identifier(synonym))
            if synonym.strip() and pair not in known_synonyms:
                CompoundSynonym.objects.create(
                    cid=compounds.get(pair[0]),
                    synonym=synonym,
                )
                known_synonyms.add(pair)
        processes: dict[str, Process] = {}
        for record in read_records(directory / 'process.csv'):
            name = required(record, 'name')
            process, _ = Process.objects.get_or_create(
                name=name,
                defaults={'description': record.get('description', '')},
            )
            processes[name] = process
        key = required(metadata, 'key')
        publication = citations.get(required(metadata, 'publication_key'))
        if publication is None:
            raise CommandError('Unknown database publication.')
        verified = required(metadata, 'source_attribution_verified').lower()
        if verified not in ('true', 'false'):
            raise CommandError('Invalid source attribution boolean.')
        dataset_values = {
            'title': required(metadata, 'title'),
            'source_file': source_name,
            'source_sha256': checksum,
            'publication': publication,
            'source_attribution_verified': verified == 'true',
            'aggregation_method': required(metadata, 'aggregation_method'),
            'provenance_notes': metadata.get('provenance_notes', ''),
        }
        dataset, created = RemovalDataset.objects.get_or_create(
            key=key,
            defaults=dataset_values,
        )
        if not created and (
            dataset.source_sha256 != checksum
            or dataset.publication != publication
            or dataset.title != dataset_values.get('title')
            or dataset.source_file != source_name
            or dataset.aggregation_method
            != dataset_values.get('aggregation_method')
            or dataset.provenance_notes
            != dataset_values.get('provenance_notes')
            or dataset.source_attribution_verified != (verified == 'true')
        ):
            raise CommandError('Dataset key already has different metadata.')
        source_keys: set[str] = set()
        for record in read_records(directory / 'removal_dataset_source.csv'):
            citation_key = required(record, 'citation_key')
            if (
                required(record, 'dataset_key') != key
                or citation_key not in citations
            ):
                raise CommandError('Unknown dataset source relationship.')
            source_keys.add(citation_key)
        if set(dataset.sources.values_list('key', flat=True)) - source_keys:
            raise CommandError('Dataset already has conflicting sources.')
        dataset.sources.add(*(citations.get(name) for name in source_keys))
        existing_rows = set(
            CompoundRemovalSummary.objects.filter(dataset=dataset).values_list(
                'source_row_number', flat=True
            )
        )
        if existing_rows - {row.source_row_number for row in summaries}:
            raise CommandError('Dataset already has unexpected summary rows.')
        for row in summaries:
            process = processes.get(row.process_name)
            if row.dataset_key != key or process is None:
                raise CommandError('Unknown summary dataset or process.')
            summary, created = CompoundRemovalSummary.objects.get_or_create(
                dataset=dataset,
                source_row_number=row.source_row_number,
                defaults={
                    'compound': compounds.get(row.compound_cid),
                    'process': process,
                    'source_substance_label': row.source_substance_label,
                    'source_treatment_label': row.source_treatment_label,
                    'mean_percent': row.mean_percent,
                    'std_percent': row.std_percent,
                    'sample_count': row.sample_count,
                },
            )
            if not created and (
                summary.compound.pk != row.compound_cid
                or summary.process != process
                or summary.source_substance_label != row.source_substance_label
                or summary.source_treatment_label != row.source_treatment_label
                or summary.mean_percent != row.mean_percent
                or summary.std_percent != row.std_percent
                or summary.sample_count != row.sample_count
            ):
                raise CommandError(
                    f'Conflicting summary at row {row.source_row_number}'
                )
        return len(summaries)
