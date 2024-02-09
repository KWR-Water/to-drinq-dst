# Setup of the package
## For developers: configuration
Make a list of all the packages required to run your code in requirements.txt. 
If this repository depends on any package that should be installed by conda 
instead of pip, add that package in requirements_conda.yml; also specify your
python version in that file.

## For users
### Create a conda environment before first use
After that, create a conda environment by navigating your command prompt to 
the folder containing `requirements_conda.yml`, that is, the same folder as 
this file. Then type the command 
`conda env create -n todrinq_dst --file requirements_conda.yml`.

# Project folder structure
The folders have the following purpose:
- tests: contains unit tests.
- documentation: contains documentation which can be created (and updated) by 
running make.bat; the result is in `documentation/build/html`
- dst_site: django application
- src: contains code and files and should function independent of django.
- research: contains files that run the code in src to:
  * do data analysis
  * model analysis
  * test new functionalities
