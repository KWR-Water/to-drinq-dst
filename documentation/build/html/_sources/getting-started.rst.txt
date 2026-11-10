===============
Getting Started
===============

Install
-------
The project has two conda environments. Run all commands from the project
root.

* ``environment.yml`` (Python 3.12) is the base environment. Use
  ``environment_mac.yml`` on macOS.
* ``environment_optim.yml`` (Python 3.13) adds the ``pystimela`` and
  ``pystimela_optim`` wheels from the ``whl/`` folder. Use
  ``environment_optim_mac.yml`` on macOS.

The packages are also publicly available under EUPL v. 1.2 from
`pystimela <https://bitbucket.org/team_makro/pystimela/>`_ and
`pystimela_optim <https://bitbucket.org/team_makro/pystimelaoptim/>`_.

.. note::
    ``drinq/views.py`` imports ``pystimela`` and ``pystimela_optim`` when the
    server starts. Run the server and the tests in the optimiser environment,
    or install both wheels in the base environment. A future update may make
    the optimiser optional with lazy imports.

Create and activate the optimiser environment (Windows)::

    conda env create -f environment_optim.yml
    conda activate todrinq_dst_optim

.. note::
    ``django-betterforms`` imports ``pkg_resources``. Use
    ``setuptools<81``, otherwise Django does not start.

Prepare the database and start the server::

    python manage.py migrate
    python manage.py createsuperuser
    python manage.py runserver

The application is then available at http://127.0.0.1:8000/. The database is
the SQLite file ``drinq/to_drinq_dst.sqlite``. Log in to use the tool. See
:doc:`administration` for adding users.

Check the optimiser installation
--------------------------------
::

    python -c "import pystimela; from pystimela_optim.scripts import run_all_optimizations; print('ok')"

The optimisation itself runs only when a user presses *Optimize*.

Run the tests
-------------
::

    python manage.py test
    python manage.py test tests.test_access_control tests.test_admin

.. note::
    The full suite currently reports failures and errors that also occur on a
    clean checkout, mainly in the technology KPI tests. Run a single module to
    check a change.

Build this documentation
------------------------
::

    pip install -r documentation/requirements.txt
    cd documentation
    make html

The result is written to ``documentation/build/html``. Remove the generated
files with ``make clean`` (``make.bat clean`` on Windows).
