# Setup of the package
## For developers: configuration
Follow the steps as below:
- Install the conda environment:
`conda env create -f environment.yml`
and activate the (conda) python environment with:
`conda activate todrinq_dst`
- Migrate the database with `python manage.py makemigrations` and complete the migration with `python manage.py migrate`
- Finally, run the Django server with
`python manage.py runserver`


### 

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
