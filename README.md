# Setup of the package
Licensed under the EUPL v. 1.2; see [License](#license).

## Contributing to the DST

Contributions to the ToDrinQ Decision Support Tool (DST) are welcome:
bug reports, documentation, tests, treatment models, datasets, and code.
Read the [contribution guide](CONTRIBUTING.rst) before starting. The same
guide is included in the Sphinx documentation under **Contributing**.

**Maintenance availability:** The current main developers have limited
time for maintenance. Issue responses, pull request reviews, approvals,
and merges may take some time; no response or review timeframe is
guaranteed. Please plan accordingly and keep contributions focused.

- Discuss substantial changes in a GitHub issue before implementing them.
- Work on a short-lived branch; external contributors should use a fork.
- Open a pull request (PR) against `main` with relevant tests,
  documentation, and validation results.
- Main developers review PRs and merge approved changes into `main`.
  Authors do not approve or merge their own PRs. Changes to scientific
  results also need domain review.
- Do not submit credentials, private data, or sensitive database contents.

## For developers: configuration
The application imports `pystimela` and `pystimela_optim` when it starts, so
the optimizer environment is required. Follow the steps as below:
- Install the optimizer conda environment for Windows:
`conda env create -f environment_optim.yml`
- Install the optimizer conda environment for Mac:
`conda env create -f environment_optim_mac.yml`
and activate the (conda) python environment with:
`conda activate todrinq_dst_optim`
- Migrate the database with `python manage.py makemigrations` and complete the migration with `python manage.py migrate`
- Finally, run the Django server with
`python manage.py runserver`

The base environments `environment.yml` and `environment_mac.yml` do not
contain the optimizer wheels. If you use one of them, install both wheels from
the `whl/` folder first (see below), otherwise the server does not start.

Note: the optimizer route is planned to become optional in a future update,
with lazy imports of `pystimela` and `pystimela_optim`. Until then, the
optimizer packages are required to run the server and the tests.

## Integration with pystimela and optimisation per process

### About pystimela and pystimela_optim
The pystimela packages are optimization frameworks developed by researchers
from the National Technical University of Athens (NTUA) within the ToDrinQ
project. They are foreground IP, packaged separately, and publicly available
under the EUPL v. 1.2 license:

- [pystimela](https://bitbucket.org/team_makro/pystimela/)
- [pystimela_optim](https://bitbucket.org/team_makro/pystimelaoptim/)

The packages are not available on PyPI. See
[Intellectual Property](INTELLECTUAL_PROPERTY.rst) for details and the
background-IP inventory of third-party frontend libraries, including
Bootstrap, jQuery, Popper, Chart.js, and Select2.

### Required optimizer wheels in this repository
The optimizer runtime requires both wheels:
- `pystimela_optim-<version>-py3-none-any.whl`
- `pystimela-<version>-py3-none-any.whl`

These wheels are installed automatically by `environment_optim.yml`
in a Python 3.13 environment. To use them in a base environment instead, run
`pip install ./whl/pystimela-<version>-py3-none-any.whl ./whl/pystimela_optim-<version>-py3-none-any.whl`.
Check the latest version of these packages on the Bitbucket repositories.

Verify installation with:
`python -c "import pystimela; from pystimela_optim.scripts import run_all_optimizations; print('ok')"`

Run optimizer unit tests with:
`python -m unittest tests.test_pystimela_optim_scripts`

### Optimizer files in this repository
The local optimization workspace is stored in `research/pystimela_optim`:
- `research/pystimela_optim/inputs`: CSV inputs for process configuration.
- `research/pystimela_optim/configs`: generated JSON configuration files.
- `research/pystimela_optim/outputs`: enabled-process files and run results.

Run only the optimizer unit tests with:
`python -m unittest tests.test_pystimela_optim_scripts`

## TODO / Fix
The following is on the To-do list.
- **Closure-tree tests:** Test closure behavior through the registered
  `DecidingFactor` model, without defining test-only Django models. The
  focused test is `tests.test_closuredecidingfactor.TestDecisionTreeClosureIntegration`.
  We might drop the legacy `closuretree/tests.py` suite, whose ad-hoc
  models fail Django test discovery.
- **Decision-tree fixture:** Model the path as source choice -> question ->
  answer choices -> optional follow-up question. A question should not be reused 
  across multiple `DecidingFactor` rows and should not rely on removed model fields.
- **Domain review:** We have to validate missing TSS/E. coli and 
  membrane-property defaults against approved catalogue sources. Also review the 
  AIEX, CIEX, pressurised sand, strainer, and UV KPI test values against 
  their formulas, units, and assumptions before changing or removing 
  those assertions.

## For users
### Create a conda environment before first use
See the first step in the developers section (the optimizer environment).

## Removal Data Attribution
The CEC removal database extract was provided by Annemarie van Wezel and
is associated with Fischer et al. (2017),
[Decision support for water quality management of contaminants of emerging concern](https://doi.org/10.1016/j.jenvman.2017.02.002).
Its contributing removal records cite Snyder et al. (2007) and two TAPES
sources. Providing the extract does not establish ownership of all
underlying measurements or permission to redistribute them. See the
[removal dataset documentation](research/data/processed/removal/README.md)
for references, acknowledgement wording, permission qualifications, and
the CSV import layout. Ownership acknowledgements remain in documentation.

Import the prepared tables with `uv run --no-project --python <environment-python>
python manage.py import_removal_data` after applying migrations. Add
`--dry-run` to validate and roll back all writes. Signed-in users can open
**Menu > Substance removal rates** to browse by CAS/synonym or technology,
including standard deviations and literature references.

# Future development
The ideas from the current maintainers for future development are included in
the [technical notes](documentation/source/future-development.rst). Progress
may take time because
available maintenance and development time is limited.

# Building the package
The package metadata is defined in `pyproject.toml`; `setup.py` is a thin
shim for tools that still call it. Python 3.13 or newer is required.

1. In the activated optimizer environment, install the build tool:
`pip install build`
2. Build the source distribution and the wheel from the repository root:
`python -m build`
The results are written to `dist/`.
3. Install the result, for example in a clean environment:
`pip install dist/todrinq_dst-0.1.0-py3-none-any.whl`

Notes:
- `pystimela` and `pystimela_optim` were developed by NTUA within ToDrinQ,
  and are publicly available under EUPL v. 1.2 from the
  [pystimela](https://bitbucket.org/team_makro/pystimela/) and
  [pystimela_optim](https://bitbucket.org/team_makro/pystimelaoptim/)
  repositories. They are not on PyPI or listed as package dependencies.
  Install the pre-built wheels from `whl/` first (see above).
- See [Intellectual Property](INTELLECTUAL_PROPERTY.rst) for licensing details.
- The Django `templates/` and `templatetags/` folders are outside the Python
packages. They are only part of the source distribution (see `MANIFEST.in`),
so run the server from a source checkout rather than from the wheel.
- Optional extras: `pip install ".[dev]"` (debug toolbar) and
`pip install sphinx` (Sphinx requirements).
- The version is set in `pyproject.toml`; the documentation reads it
from there.

# Documentation
The documentation is written with Sphinx. The sources are in
`documentation/source`; the generated files are written to
`documentation/build` (ignored by git).

## Generate the documentation
1. Install the documentation requirements in your python environment:
`pip install -r documentation/requirements.txt`
2. Go to the documentation folder and build the HTML pages:
```
cd documentation
make html
```
On Windows (PowerShell) use `.\make.bat html` instead of `make html`.
3. Open `documentation/build/html/index.html` in a browser.

The diagrams are drawn by the browser with Mermaid, which is loaded from the
internet. Without a connection the diagrams show as plain text.

## Clean the documentation
Remove all generated files with:
```
cd documentation
make clean
```
On Windows (PowerShell) use `.\make.bat clean`. Run `make clean` followed by
`make html` for a full rebuild, for example after changing
`documentation/source/conf.py` or the table of contents in `index.rst`.

# Project folder structure
The folders have the following purpose:
- tests: contains unit tests.
- documentation: contains documentation which can be created (and updated) by 
running make.bat; the result is in `documentation/build/html`
- drinq: django application
- research: contains files:
  * which do data analysis
  * which do model analyses
  * which test new functionalities

# License
Copyright (c) KWR Water Research Institute

Licensed under the EUPL

This project is licensed under the European Union Public Licence (EUPL)
v. 1.2 (or later). See the `LICENSE` file for the full text.

The `closuretree` app is third-party code under the Apache License 2.0; see
the headers in its files.
