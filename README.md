# Setup of the package
## For developers: configuration
Follow the steps as below:
- Install the conda environment for Windows:
`conda env create -f environment.yml`
- Install the conda environment for Mac:
`conda env create -f environment_mac.yml`
and activate the (conda) python environment with:
`conda activate todrinq_dst`
- Migrate the database with `python manage.py makemigrations` and complete the migration with `python manage.py migrate`
- Finally, run the Django server with
`python manage.py runserver`

## Optional: integration with pyStimela and optimisation per process
Use the dedicated optimizer environment file:
`conda env create -f environment_optim.yml`
`conda activate todrinq_dst_optim`

### Required optimizer wheels in this repository
The optimizer runtime requires both wheels:
- `pystimela_optim-<version>-py3-none-any.whl`
- `pystimela-0.0.2-py3-none-any.whl`

These wheels are installed automatically by `environment_optim.yml`
in a Python 3.13 environment.

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
See the first step in the developers section.

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
