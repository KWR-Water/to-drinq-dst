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

## Integration with pyStimela and optimisation per process

### Required optimizer wheels in this repository
The optimizer runtime requires both wheels:
- `pystimela_optim-<version>-py3-none-any.whl`
- `pystimela-0.0.2-py3-none-any.whl`

These wheels are installed automatically by `environment_optim.yml`
in a Python 3.13 environment. To use them in a base environment instead, run
`pip install ./whl/pystimela-0.0.2-py3-none-any.whl ./whl/pystimela_optim-0.1.2-py3-none-any.whl`.

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

## For users
### Create a conda environment before first use
See the first step in the developers section (the optimizer environment).

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
- `pystimela` and `pystimela_optim` are not on PyPI and are not listed as
dependencies. Install both wheels from `whl/` first (see above).
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
v. 1.2. See the `LICENSE` file for the full text.

The `closuretree` app is third-party code under the Apache License 2.0; see
the headers in its files.
