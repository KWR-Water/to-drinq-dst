============
Architecture
============

Overview
--------
The DST is a server-rendered Django application with a small REST API. The
calculation logic is kept in plain Python modules, separate from the views.

.. mermaid::

    flowchart TD
        U[Browser] --> V[Django views and templates]
        C[API client] --> A[DRF API views]
        V --> D[decision_tree.py]
        V --> K[api_calculation.py]
        A --> K
        K --> T[utils/treatmentkpi.py]
        K --> F[utils/financial_costs.py]
        V --> O[pystimela_optim<br/>background thread]
        D --> M[(SQLite via Django ORM)]
        K --> M
        V --> M
        O --> W[research/pystimela_optim<br/>files]
        O --> M

Apps and modules
----------------
.. list-table::
    :header-rows: 1
    :widths: 30 70

    * - Module
      - Responsibility
    * - ``accounts``
      - Custom user model, user profile, admin, token login API.
    * - ``closuretree``
      - Generic closure table for hierarchical models. Used by the decision
        tree.
    * - ``drinq/models.py``
      - Data model, about 50 tables.
    * - ``drinq/views.py``
      - Class-based views for the design workflow, plus the orchestration of
        the calculation and optimisation pipelines.
    * - ``drinq/decision_tree.py``
      - Turns answers into technologies and treatment trains.
    * - ``drinq/api_calculation.py``
      - Plant and technology performance calculators, optimiser name mapping.
    * - ``drinq/utils/treatmentkpi.py``
      - One KPI class per treatment technology.
    * - ``drinq/utils/financial_costs.py``
      - Pure cost functions.
    * - ``drinq/api_views.py``
      - REST endpoint for design parameters.
    * - ``drinq/access.py``
      - Ownership rule for plants, shared by the views and the API.
    * - ``drinq/admin.py``
      - Admin site: editable catalogue, read-only plant data, no decision
        tree.
    * - ``research/``
      - Data ingestion, analysis and the optimiser workspace.
    * - ``tests/``
      - Unit and integration tests.

Data model
----------
.. list-table::
    :header-rows: 1
    :widths: 30 70

    * - Group
      - Main models
    * - Decision
      - ``DesignTree``, ``DecidingFactor``, ``DecidingFactorQuestion``,
        ``DecidingFactorChoice``, ``MultiStepConfiguration``,
        ``QuestionAnswer``
    * - Technology catalogue
      - ``Technology``, ``Stage``, ``StageTechnologies``,
        ``TechnologyRelatedtechnology``, ``TechnologyProperty``,
        ``TechnologyPropertyJunction``, ``TechnologyKPI``,
        ``TechnologyConstructionCostParameter``,
        ``TechnologyAdaptabilityScore``
    * - Plant instance
      - ``TreatmentPlant``, ``TreatmentPlantLayout``,
        ``TreatmentplantDesignParameter``,
        ``TreatmentPlantTechnologyPropertyValue``,
        ``TreatmentPlantTechnologyKPIValue``, ``TreatmentPlantPropertyValue``,
        ``TreatmentPlantWaterQualityParameterValue``
    * - Water quality and chemicals
      - ``WaterqualityParameter``, ``WaterqualityParameterTechnologyJunction``,
        ``ChemicalAgent``, ``ChemicalagentPrice``
    * - Optimiser
      - ``TechnologyPystimelaoptJunction``,
        ``TechnologyPropertyPystimelaoptJunction``,
        ``TechnologyWaterqualityParameterPystimelaoptJunction``,
        ``TreatmentPlantTechnologyOptimizationStatus``
    * - Chemistry
      - ``Compound``, ``CompoundCas``, ``CompoundSynonym``,
        ``RemovalEfficiency``, ``Process``, ``Citation``
    * - Users
      - ``CustomUser``, ``UserProfile``, ``Watercompany``

Architectural choices
---------------------
**Data-driven catalogue.** Technologies, properties, defaults, cost
coefficients and the decision tree are database content, not code. A domain
expert can change the catalogue without changing the views. The exception is
the KPI class of a technology, which is code.

**Closure table for the decision tree.** The tree is queried for children and
descendants on every question. A closure table makes these reads cheap and
keeps the tree editable as plain rows.

**Separation of calculation and web layer.** The cost functions and KPI
classes do not depend on Django requests. This keeps them testable with unit
tests.

**Recompute from stored inputs.** The calculation pipeline reads its inputs
from the database and writes results back. A user can change one value and
recalculate without a session state.

**Value provenance.** Technology property values carry a source (``user``,
``digested`` or ``optimized``). The tool can then reuse optimiser results and
discard them when inputs change.

**On-demand optimiser.** ``pystimela_optim`` is slow. It runs only when the
user asks for it, in a background thread by default. Its progress is kept in
the cache and polled by the page. The packages are imported when the server
starts, so they must be installed. The optimiser has its own conda environment
and wheels.

**Ownership-based access.** Plants belong to the user of their configuration.
All plant pages and the design parameter API check this with
``user_can_access_plant``. Staff users can access all plants. Other users get
a 404, so the existence of a plant is not disclosed.

**Stable property names.** KPI and property names are shared between code,
JSON files and database rows. They must be kept in sync, see
:doc:`administration`.

Technology stack
----------------
* Python 3.13 or newer, Django 5, Django REST framework with token and
  session authentication.
* SQLite database.
* Server-rendered templates with Bootstrap, jQuery and Popper.
* ``pandas`` and ``numpy`` for calculations, ``rdkit`` for structure images,
  ``pubchempy`` and ``cirpy`` for compound data.
* ``pystimela`` and ``pystimela_optim`` for process optimisation.
* conda environments, see :doc:`getting-started`.

Testing
-------
The ``tests/`` folder covers the decision tree and stage bucketing, KPI
classes, financial costs, KPI defaults in the database, the API, the views,
access control, the admin site, the optimiser scripts and the data ingestion.

Deployment notes
----------------
The project contains ``wsgi.py`` and ``asgi.py`` entry points. The default
settings are for development. For production:

* Set ``DEBUG`` to ``False``, move ``SECRET_KEY`` out of the source and set
  ``ALLOWED_HOSTS``.
* Run ``collectstatic`` and serve ``static/`` with the web server.
* Use one worker process, or a shared cache, because the optimiser status is
  kept in the cache of the process that runs the thread.
* Consider a database server instead of SQLite when several users work at the
  same time.
