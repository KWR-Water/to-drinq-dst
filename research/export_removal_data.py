"""Export provenance-aware removal CSVs without accessing the database.

Preserve the supplied summaries rather than pooling statistics across names.
Foreign keys are exported as portable lookup keys for a later ORM import.
"""

import csv
import hashlib
import math
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import astuple, dataclass
from pathlib import Path

DATASET_KEY: str = 'fischer2017-cec-removal-v1'
PUBLICATION_KEY: str = 'fischer2017decision'
SOURCE_KEYS: tuple[str, ...] = (
    'snyder2007removal',
    'tapes_de_watergroep',
    'tapes_tzw',
)
PROCESSES: dict[str, str] = {
    'O3': 'Ozonation',
    'O3 + H2O2': 'Ozonation with hydrogen peroxide',
    'PAC': 'Powdered activated carbon adsorption',
    'UV': 'UV treatment',
    'UV + H2O2': 'UV with hydrogen peroxide',
    'Nanofiltration': 'Nanofiltration',
    'Ultrafiltration': 'Ultrafiltration',
}
PROCESSED_DIRECTORY: Path = Path(__file__).parent / 'data' / 'processed'


@dataclass(frozen=True)
class CitationRow:
    """Keep a formatted reference and optional identifiers in one record."""

    key: str
    reference: str
    doi: str = ''
    url: str = ''
    notes: str = ''


CITATIONS: tuple[CitationRow, ...] = (
    CitationRow(
        key=PUBLICATION_KEY,
        reference=(
            'Fischer, A., ter Laak, T., Bronders, J., Desmet, N., '
            'Christoffels, E., van Wezel, A., and van der Hoek, J. P. '
            '(2017). Decision support for water quality management of '
            'contaminants of emerging concern. Journal of Environmental '
            'Management, 193, 360-372.'
        ),
        doi='10.1016/j.jenvman.2017.02.002',
        url='https://doi.org/10.1016/j.jenvman.2017.02.002',
        notes=(
            'Database publication; article metadata checked against Crossref.'
        ),
    ),
    CitationRow(
        key='snyder2007removal',
        reference=(
            'Snyder, S. A. (2007). Removal of EDCs and pharmaceuticals '
            'in drinking and reuse treatment processes. IWA Publishing.'
        ),
        notes=(
            'Bibliographic details supplied by the user; complete '
            'authorship and publishing details require verification. '
            'Original database label: Snyder et al. (2007).'
        ),
    ),
    CitationRow(
        key='tapes_de_watergroep',
        reference='TAPES - De Watergroep',
        notes='Original database label; full reference unavailable.',
    ),
    CitationRow(
        key='tapes_tzw',
        reference='TAPES - TZW',
        notes='Original database label; full reference unavailable.',
    ),
)


@dataclass(frozen=True)
class RemovalSummaryRow:
    """Represent a source summary using portable relationship keys.

    The row number is the physical, one-based row in the source CSV,
    including its three header rows. Counts remain unknown because they
    are not supplied in that CSV.
    """

    dataset_key: str
    compound_cid: int
    process_name: str
    source_row_number: int
    source_substance_label: str
    source_treatment_label: str
    mean_percent: float
    std_percent: float | None
    sample_count: int | None = None


SUMMARY_COLUMNS: tuple[str, ...] = tuple(
    RemovalSummaryRow.__dataclass_fields__
)


def normalize_identifier(value: str) -> str:
    """Normalize spelling without removing chemical identity distinctions."""
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def valid_cas(value: str) -> bool:
    """Check CAS syntax and its check digit, not chemical equivalence."""
    if re.fullmatch(r'[1-9][0-9]{1,6}-[0-9]{2}-[0-9]', value) is None:
        return False
    digits: str = value.replace('-', '')
    checksum: int = sum(
        position * int(digit)
        for position, digit in enumerate(reversed(digits[:-1]), start=1)
    )
    return checksum % 10 == int(digits[-1])


def read_csv_rows(path: Path) -> list[list[str]]:
    """Read semicolon-separated records, preserving quoted delimiters."""
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.reader(stream, delimiter=';'))


def build_compound_lookup(directory: Path) -> dict[str, set[int]]:
    """Index common names, synonyms and valid CAS numbers by candidate CID."""
    lookup: dict[str, set[int]] = {}
    compound_ids: set[int] = set()
    compounds: list[list[str]] = read_csv_rows(
        directory / 'table_compound.csv'
    )
    for _, cid_text, _, name in compounds[1:]:
        cid: int = int(cid_text)
        if cid <= 0 or cid in compound_ids:
            raise ValueError(f'Invalid or duplicate compound CID: {cid}')
        compound_ids.add(cid)
        lookup.setdefault(normalize_identifier(name), set()).add(cid)

    synonyms: list[list[str]] = read_csv_rows(
        directory / 'table_synonyms_cid.csv'
    )
    for _, cid_text, synonym in synonyms[1:]:
        cid = int(cid_text)
        if cid not in compound_ids:
            raise ValueError(f'Synonym references unknown CID: {cid}')
        if synonym.strip():
            lookup.setdefault(normalize_identifier(synonym), set()).add(cid)

    cas_rows: list[list[str]] = read_csv_rows(directory / 'table_cas_cid.csv')
    for _, cas, cid_text in cas_rows[1:]:
        cid = int(cid_text)
        if cid not in compound_ids:
            raise ValueError(f'CAS references unknown CID: {cid}')
        if valid_cas(cas.strip()):
            lookup.setdefault(cas.strip(), set()).add(cid)
    return lookup


def resolve_cid(label: str, lookup: dict[str, set[int]]) -> int:
    """Reject unresolved or ambiguous identifiers instead of guessing."""
    candidates: set[int] = lookup.get(normalize_identifier(label), set())
    if len(candidates) != 1:
        raise ValueError(
            f'Expected one CID for {label!r}; found {sorted(candidates)}'
        )
    return next(iter(candidates))


def load_summaries(directory: Path) -> list[RemovalSummaryRow]:
    """Resolve each exported summary to CID without merging source rows."""
    lookup: dict[str, set[int]] = build_compound_lookup(directory)
    records: list[list[str]] = read_csv_rows(
        directory / 'cecs_removal_eff_mean_std.csv'
    )
    expected_header: list[list[str]] = [
        ['', '', 'efficiency_avg', 'efficiency_avg'],
        ['', '', 'mean', 'std'],
        ['synonym_substance', 'treatment_spec', '', ''],
    ]
    if records[:3] != expected_header:
        raise ValueError('Unexpected removal CSV header')
    summaries: list[RemovalSummaryRow] = []
    for row_number, record in enumerate(records[3:], start=4):
        label, treatment, mean_text, std_text = record
        if treatment not in PROCESSES:
            raise ValueError(f'Unknown treatment: {treatment!r}')
        mean: float = float(mean_text)
        std: float | None = float(std_text) if std_text.strip() else None
        if not math.isfinite(mean) or not 0 <= mean <= 100:
            raise ValueError(f'Invalid mean on source row {row_number}')
        if std is not None and (not math.isfinite(std) or std < 0):
            raise ValueError(f'Invalid deviation on source row {row_number}')
        summaries.append(
            RemovalSummaryRow(
                dataset_key=DATASET_KEY,
                compound_cid=resolve_cid(label, lookup),
                process_name=treatment,
                source_row_number=row_number,
                source_substance_label=label,
                source_treatment_label=treatment,
                mean_percent=mean,
                std_percent=std,
            )
        )
    return summaries


def write_csv(
    path: Path,
    columns: Iterable[str],
    rows: Iterable[Iterable[str | int | float | None]],
) -> None:
    """Write portable UTF-8 CSVs with blank fields representing SQL NULL."""
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream, delimiter=';', lineterminator='\n')
        writer.writerow(columns)
        writer.writerows(rows)


def export_removal_data(directory: Path = PROCESSED_DIRECTORY) -> int:
    """Create import tables while leaving source files and SQLite untouched."""
    summaries: list[RemovalSummaryRow] = load_summaries(directory)
    source_path: Path = directory / 'cecs_removal_eff_mean_std.csv'
    checksum: str = hashlib.sha256(source_path.read_bytes()).hexdigest()
    destination: Path = directory / 'removal'
    destination.mkdir(parents=True, exist_ok=True)
    write_csv(
        destination / 'citation.csv',
        ('key', 'reference', 'doi', 'url', 'notes'),
        (astuple(citation) for citation in CITATIONS),
    )
    write_csv(
        destination / 'removal_dataset_source.csv',
        ('dataset_key', 'citation_key'),
        ((DATASET_KEY, key) for key in SOURCE_KEYS),
    )
    write_csv(
        destination / 'process.csv',
        ('name', 'description'),
        PROCESSES.items(),
    )
    write_csv(
        destination / 'removal_dataset.csv',
        (
            'key',
            'title',
            'source_file',
            'source_sha256',
            'publication_key',
            'source_attribution_verified',
            'aggregation_method',
            'provenance_notes',
        ),
        [
            (
                DATASET_KEY,
                'CEC removal summaries from Fischer et al. (2017)',
                source_path.name,
                checksum,
                PUBLICATION_KEY,
                'false',
                (
                    'Arithmetic mean and sample standard deviation '
                    '(ddof=1) of efficiency_avg grouped by source '
                    'substance label and treatment.'
                ),
                (
                    'Counts and experimental conditions are absent from this '
                    'summary export. Original CID mappings are preserved, not '
                    'chemically certified; review the diurone and '
                    'tcep mappings.'
                ),
            )
        ],
    )
    write_csv(
        destination / 'compound_removal_summary.csv',
        SUMMARY_COLUMNS,
        (astuple(summary) for summary in summaries),
    )
    return len(summaries)


if __name__ == '__main__':
    print(f'Exported {export_removal_data()} removal summaries.')
