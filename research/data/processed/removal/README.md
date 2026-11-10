# CEC Removal Summary Dataset

## Suggested Attribution

> Removal data were extracted from the database associated with Fischer
> et al. (2017), *Decision support for water quality management of
> contaminants of emerging concern*, and provided by Annemarie van Wezel.
> The contributing records in the supplied export cite Snyder et al.
> (2007), TAPES - De Watergroep, and TAPES - TZW. The local derivative
> contains arithmetic means and sample standard deviations grouped by
> source substance name and treatment specification.

Cite the database publication as:

Fischer, A., ter Laak, T., Bronders, J., Desmet, N., Christoffels, E.,
van Wezel, A., and van der Hoek, J. P. (2017). Decision support for water
quality management of contaminants of emerging concern. *Journal of
Environmental Management*, **193**, 360-372.
https://doi.org/10.1016/j.jenvman.2017.02.002

Annemarie van Wezel is acknowledged as the provider of the database
extract, not as the sole author or established rights holder of its
underlying measurements. Provider and ownership acknowledgements belong
in documentation, not in the citation or dataset tables. There is no transfer date, database version, and dataset-specific licence.

Do not invent a transfer date or assume that the repository's software licence permits redistribution of these data. Confirm permission and citation wording with the provider before publishing a standalone dataset. Add a dataset DOI if the derivative is subsequently deposited in a repository.

The following citation sources refer to the imported database file, removal rates as reported by Snyder and the water utility De Watergroep and TZW (see the CSV files in the raw\abates folder for full, original details):
```bibtex
@article{fischer2017decision,
  author = {Fischer, Astrid and ter Laak, Thomas and Bronders, Jan
            and Desmet, Nele and Christoffels, Ekkehard
            and van Wezel, Annemarie and van der Hoek, Jan Peter},
  title = {Decision support for water quality management of
           contaminants of emerging concern},
  journal = {Journal of Environmental Management},
  volume = {193},
  year = {2017},
  pages = {360--372},
  issn = {0301-4797},
  doi = {10.1016/j.jenvman.2017.02.002}
}

@techreport{snyder2007removal,
  author = {Snyder, Shane A.},
  title = {Removal of {EDCs} and pharmaceuticals in drinking and
           reuse treatment processes},
  year = {2007},
  institution = {IWA Publishing},
  note = {Bibliographic details supplied by the data user;
          complete authorship and publishing details require verification}
}
```

`tapes_de_watergroep` and `tapes_tzw` are local citation keys for the raw
labels `TAPES - De Watergroep` and `TAPES - TZW`. Do not substitute invented titles, authors, or dates.

## Provenance And Limits

The input is `../cecs_removal_eff_mean_std.csv`. The export retains its
201 summary records, covering 46 CIDs and 199 distinct CID-treatment
combinations. Nine standard deviations are missing. Counts, individual
study links, and experimental conditions are not present in this input.

An audit of `research/data/raw/abates/DSS treatment techniques - master.csv`,
using the water-type filter and Greek-character replacements in
`research/ingest_abates_data.py`, reproduced all 201 means and standard
deviations to an absolute tolerance of 1e-10. The contributing raw records
had these source labels:

| Raw citation label | Contributing records |
| --- | ---: |
| Snyder et al. (2007) | 1291 |
| TAPES - De Watergroep | 25 |
| TAPES - TZW | 11 |

These are counts of raw input records, not independent studies or
replicates. In particular, Snyder is not the sole source. Dataset source
citations describe the collection as a whole; they do not imply that
every summary contains observations from every source.

`source_attribution_verified=false` records that the full bibliographies
and per-summary source attribution remain incomplete. The raw label
check does not verify the primary reports. `sample_count` remains NULL
because this export preserves the supplied summary file, rather than
enriching it from a potentially different raw dataset version.

`Benzo(a)pyrene` and `Benzopyrene` both resolve to CID 2336 and have
separate UV and UV + H2O2 summaries. Both are retained. Do not average
these means or overwrite one row with the other. Canonical combined
statistics should be recomputed from deduplicated raw observations after
resolving CID and checking experimental context.

CID mappings come from the supplied compound, synonym, and CAS tables;
they have not been chemically certified. Review the `diurone`/CID 25210
and `tcep`/CID 119411 associations before using these results in scientific
decisions. No mapping or source CSV was silently corrected.

## Import Tables

All files are UTF-8, semicolon-delimited CSVs with one header row and no
pandas index. Quoted cells may contain semicolons. Use a CSV parser, not
string splitting. Empty numeric fields represent SQL NULL, not zero.

| File | Rows | Destination |
| --- | ---: | --- |
| `citation.csv` | 4 | `Citation` model, using `key` |
| `process.csv` | 7 | Existing `Process` model, using `name` |
| `removal_dataset.csv` | 1 | New `RemovalDataset` model |
| `removal_dataset_source.csv` | 3 | Existing dataset-source many-to-many relationship |
| `compound_removal_summary.csv` | 201 | New `CompoundRemovalSummary` model |

`citation.csv` contains `key;reference;doi;url;notes`. The formatted
`reference` keeps authors, year, title, and publishing details together,
without separate author or publisher tables. DOI and URL may be blank;
`notes` records incomplete or unverified bibliographic details, not
ownership claims. The existing numeric citation primary key is unchanged.

`RemovalDataset.publication` identifies the database publication. Its
existing `sources` relationship identifies removal-rate sources via
Django's automatic junction table. No additional citation-role model is
introduced. The link CSV contains `dataset_key;citation_key`, replacing
the previous JSON list of source keys. These are dataset-level links,
not an assertion of per-summary source attribution.

The CSVs use portable relationship keys, not database-specific numeric
IDs. Use the Django management command, not direct SQLite `.import`:

```text
uv run --no-project --python <environment-python> python manage.py migrate
uv run --no-project --python <environment-python> python manage.py import_removal_data --dry-run
uv run --no-project --python <environment-python> python manage.py import_removal_data
```

Back up existing databases before migrating or importing. The import command validates the source checksum and compares exported
summaries with the source snapshot before writing. It imports the 46
compounds, checksum-valid CAS mappings, deduplicated synonyms, citations,
processes, dataset links, and all 201 summaries in one transaction.
`--dry-run` performs the same work but rolls everything back. `--directory`
can select another export directory whose parent contains the source CSVs.
The command requires the snapshot layout produced by this exporter.

Existing nonempty citation metadata, molecular structures, and dataset
summaries must agree with the snapshot; conflicts abort the transaction
instead of silently replacing records. Existing process descriptions and
compound common names are preserved. Repeated imports do not duplicate
aliases or summaries. CAS checksum validity does not certify chemical
identity. The original, flagged diurone and tcep mappings remain unchanged.

Process names preserve the seven source treatment labels. In the browser,
these are the technology selections; they are not automatically equated
with plant-specific technologies or optimizer models. Blank standard
deviations and sample counts remain NULL, and attribution stays unverified
until the bibliographic and individual-study review is complete.

## Browser

After signing in, open **Menu > Substance removal rates**, or
`/removal-rates/`. The substance view accepts CAS numbers, synonym names,
common names, or CIDs and lets the user choose a matching compound. The
technology view lists substances for the selected source treatment.
Result links switch between the two views.

After two characters, the search suggests up to 15 matching substances,
showing their common names, CIDs, and available CAS numbers. Common-name
prefixes appear first. Click a suggestion, or use the arrow keys and
Enter, to open its rates. Escape dismisses the suggestions. Searches are
debounced and superseded requests are cancelled. The Search button and
substance selector remain available without JavaScript or if suggestions
cannot be loaded. Only compounds with removal summaries are suggested.

Common names and CAS numbers support substring matching; synonyms match
only from the beginning of the alias, case-insensitively. This prevents
short searches such as `met` from matching incidental `methanol` or
`methylethyl` fragments inside long chemical or product descriptions.
The same rules apply to live suggestions and submitted searches.

After selecting a substance, up to 5 distinct synonyms are shown in grey
below its CID and CAS identifiers. Blank entries and the displayed common
name are excluded. Recognizable UUIDs, hexadecimal hashes, InChIKeys,
registry/catalogue codes, and structural identifiers are excluded from
this display before applying the limit. Numbered chemical names are
retained, and names are deduplicated case-insensitively. Synonyms are
sorted alphabetically, with `List truncated (5 shown)` only when more
than 5 eligible names exist. The original alias data and identifier
search remain unchanged. This display filter does not independently
validate the chemical equivalence of imported aliases.

Every row shows its original reported substance label, mean removal
percentage, standard deviation in percentage points when reported, and a
References button. Zero deviations are distinct from missing deviations.
Reference dialogs distinguish the database publication from dataset-level
removal-rate sources; they do not claim individual-study attribution.
The two identity mappings needing review are visibly flagged. Literature
summaries across different conditions are not treatment design guarantees.

`source_row_number` is the physical one-based source CSV row, including
the three header rows: the first observation is row 4, the last row 204.
CID and process are deliberately not unique together. The schema enforces
unique `(dataset, source_row_number)`, mean in [0, 100], nonnegative or
NULL standard deviation, and positive or NULL sample count. Compound,
process, dataset, and publication references use protected deletion.

## Regeneration

From the repository root, using the existing Python environment:

```text
uv run --no-project --python <environment-python> python -m research.export_removal_data
```

This rewrites only the five generated CSVs in this directory. It does not
modify the input tables, apply migrations, or access SQLite. The source
file's SHA-256 is recorded in the dataset CSV; imports should separately
retain the compound-mapping tables and their revision for reproducibility.
The local dataset key identifies this derivative, not an asserted version
of the original database.

The exporter matches normalized common names, synonyms, or checksum-valid
CAS numbers to candidate CIDs. Duplicate aliases for the same CID are
collapsed; unknown or multi-CID labels fail instead of guessing. Invalid
CAS values, including literal `None`, are excluded from the lookup.
Punctuation is retained so salts and stereoisomers are not conflated.