==============
Administration
==============

This chapter is for power users and administrators. It explains how to manage
users and how to maintain the data behind the tool.

Access levels
-------------
The tool uses the standard Django roles. No custom roles exist.

.. list-table::
    :header-rows: 1
    :widths: 25 75

    * - Role
      - Rights
    * - Regular user
      - Can use the design workflow. Has no access to ``/admin/``.
    * - Staff (``is_staff``)
      - Can open ``/admin/``. Sees only the models for which the user (or a
        group) has permissions.
    * - Superuser
      - Has all permissions.

All logged-in users have the same functional rights in the design workflow.
Use groups with model permissions to limit what staff users can change in the
admin site.

Manage users
------------
Create the first administrator::

    python manage.py createsuperuser

Add a user in the admin site:

1. Open ``/admin/`` and choose *Users*, then *Add user*.
2. Enter a username and a password. The password must pass the validators
   (similarity to user data, minimum length, common passwords, all numeric).
3. Save, then fill in the email address, names and permissions on the next
   page.
4. Set the *Water company* in the *User Profile* block at the bottom of the
   page. The profile is created automatically when the user is created.
   Add water companies under *Watercompanys* in the admin site.

Other tasks:

.. list-table::
    :header-rows: 1
    :widths: 30 70

    * - Task
      - How
    * - Make a user staff or superuser
      - Tick *Staff status* or *Superuser status* on the user page.
    * - Give limited admin rights
      - Create a group with the needed model permissions and add the user.
    * - Block access temporarily
      - Clear *Active*. The data of the user is kept.
    * - Reset a password
      - Use the password link on the user page. Users can also change their
        own password at ``/change-password/``.
    * - Revoke an API token
      - Delete the token under *Auth Token* in the admin site.
    * - Delete a user
      - Delete on the user page. This also deletes the profile and the saved
        configurations of the user, including their treatment plants.

Login and registration
----------------------
* The web interface uses session login at ``/login/``, which redirects to the
  Django REST framework login page. Logout is at ``/logout/``.
* The API issues a token at ``POST /accounts/login/`` and removes it at
  ``POST /accounts/logout/``. A user can log in with the username or the email
  address.
* ``POST /accounts/register/`` creates a user. It requires the token of a
  staff user. Regular users cannot register themselves, so create accounts in
  the admin site or through this endpoint.

Security notes
--------------
The following rules apply.

* The pages for parameters, technology properties, results, adaptability and
  the overviews require login. A user sees only the plants of their own
  configurations. Staff users see all plants. Other users get a 404.
* ``GET /accounts/users/<id>/`` requires a token. Users can read only their
  own record. Staff users can read all records.
* ``POST /api/process_parameters/`` requires a token or a browser session and
  ownership of the plant.
* The questionnaire results, the session selection and the creation of a
  treatment plant require login. A plant can only be created in a
  configuration of the user.

Review the following points before a production deployment.

* ``DEBUG`` is on, ``SECRET_KEY`` is in the settings file and
  ``ALLOWED_HOSTS`` lists local hosts only. See :doc:`architecture`.

Manage content
--------------
The admin site covers the catalogue data. The decision tree is deliberately
not registered, because a wrong edit can break the questionnaire for every
user.

.. list-table::
    :header-rows: 1
    :widths: 30 70

    * - Access
      - Models
    * - Editable
      - Compounds, CAS numbers, synonyms, removal efficiencies, processes,
        goals, technologies, stages and their links, technology properties and
        defaults, construction cost parameters, technology KPIs, design
        parameters and categories, plant properties, water quality parameters
        and their technology links, chemical agents, prices and technology
        links, adaptability criteria and scores, water companies, citations.
    * - Read-only
      - The optimiser name mappings (``*Pystimelaopt*``) and the data of
        users: configurations, treatment plants, layouts, design parameter,
        property, KPI and water quality values, chemical prices per plant and
        optimisation status. Use these pages for support. Deleting a row is
        still possible with the delete permission.
    * - Not in the admin site
      - Design trees, questions, choices, deciding factors, the links from
        choices to technologies, the previous and next step links between
        technologies, categorical variables and stored answers. Edit these in
        the database, with care.

The names of technologies, stages, technology properties, KPIs, design
parameters, plant properties and water quality parameters cannot be changed
after creation. The names are used in code and JSON files.

Add a technology
^^^^^^^^^^^^^^^^
1. Create the ``Technology`` and assign it to a ``Stage``. The name cannot be
   changed afterwards in the admin site, so choose it with care.
2. Add its properties with default values (``TechnologyPropertyJunction``) and
   its water quality parameters.
3. Link the technology to a choice in the decision tree
   (``TechnologyDecidingFactorJunction``) and add
   ``TechnologyRelatedtechnology`` rows when it has a previous or next step.
   These tables are not in the admin site.
4. Add construction cost coefficients, chemical agents and adaptability
   scores.
5. For KPIs, add a branch in ``TechnologyPerformanceCalculator.calculate_kpi``
   in ``drinq/api_calculation.py``. The branch matches on the stage name and on
   words in the technology name. Without it, the technology has no KPIs.

Keep the property names in sync
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The files ``drinq/utils/treatmentpropertyname.json`` and
``drinq/utils/treatmentplantpropertyname.json`` must match the database
tables. Regenerate the first with ``python generate_treatmentpropertyname_json.py``
from the project root.

Change defaults
^^^^^^^^^^^^^^^
Defaults live in ``DesignParameter.defaultvalue`` and ``ChemicalagentPrice``.
Users can override them per plant. The overrides are stored in
``TreatmentplantDesignParameter`` and
``TreatmentPlantChemicalagentPriceJunction``.

Import compound data
^^^^^^^^^^^^^^^^^^^^
Run the scripts in ``research/`` from the project root.

* ``ingest_abates_data.py`` reads the ABATES removal studies.
* ``collect_substance_identifiers.py`` collects identifiers from PubChem.
  Requests are spaced by ``TIME_BETWEEN_PUBCHEM_REQUESTS``.
* ``import_compounds.py`` writes the compound, CAS and synonym tables to the
  database.

Operations
----------
* **Backup.** Copy ``drinq/to_drinq_dst.sqlite`` while the server is stopped.
* **Migrations.** Run ``python manage.py migrate`` after each update.
* **Logs.** ``general.log`` holds the application log. The optimiser writes
  ``pystimela.log``.
* **Optimiser files.** Inputs, configurations and results are written under
  ``research/pystimela_optim``. Run the optimiser with this folder as the
  working directory, because the scripts use relative paths.
