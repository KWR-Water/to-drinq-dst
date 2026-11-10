========
Overview
========

What the DST can do
-------------------
The DST supports early-stage design of a drinking water treatment plant.

* **Guided option generation.** A questionnaire about the source water and
  the treatment goals leads to a set of feasible treatment trains.
* **Design inputs.** The user enters plant-level parameters such as the
  population, water use and financial assumptions. Technology properties and
  water quality values start from database defaults and can be overridden.
* **KPI calculation.** For each treatment train the tool calculates footprint,
  energy use, CO2 emissions, construction and annual costs, the levelized cost
  of water, and an adaptability score.
* **Optimisation (optional).** Selected processes (coagulation-flocculation,
  rapid sand filtration, GAC, chlorination and ozonation) can be optimised
  with ``pystimela_optim``.
* **Comparison and export.** Two designs can be compared side by side. The
  results of a design can be exported to CSV.
* **REST API.** Plant-level properties can be calculated from design
  parameters through an API.

Main pages
----------
All design pages require login. A user sees only the designs of their own
configurations.

.. list-table::
    :header-rows: 1
    :widths: 35 65

    * - URL
      - Purpose
    * - ``/session_select/``, ``/configuration_manage/``
      - Start a new design or open, edit and delete stored configurations.
    * - ``/form-name/``, ``/form-designtree/``
      - Name the configuration and choose the water source.
    * - ``/multi_form/<id>/``
      - Answer the questions one by one.
    * - ``/form_complete/<session_key>/``
      - Review the proposed treatment options and name the ones to keep.
    * - ``/treatmentplant/<id>/parameters/``
      - Enter the design parameters of the plant.
    * - ``/treatmentplant/<id>/technology/``
      - Edit technology properties and water quality. Run the calculation or
        the optimisation.
    * - ``/treatmentplant/<id>/results/``
      - View plant and technology KPIs. Add ``export/csv/`` to download them.
    * - ``/treatmentplant/<id>/adaptability/``
      - See the adaptability scores per technology and criterion.
    * - ``/treatmentplant/compare/``
      - Compare two designs per property category, with a radar chart.
    * - ``/treatmentplant/technology-overview/``
      - Overview of technology parameters.
    * - ``/admin/``
      - Administration, for staff users. See :doc:`administration`.

Design workflow
---------------
.. mermaid::

    flowchart LR
        A[Log in] --> B[Name configuration<br/>and water source]
        B --> C[Answer questions]
        C --> D[Review treatment options]
        D --> E[Name an option<br/>creates a treatment plant]
        E --> F[Design parameters]
        F --> G[Technology properties<br/>and water quality]
        G --> H{Action}
        H -->|Calculate| I[Results and KPIs]
        H -->|Optimize| J[pystimela_optim run]
        J --> I
        I --> K[Compare or export]

The next chapters describe the :doc:`decision process <decision_process>` and
the :doc:`KPI evaluation <kpi_evaluation>` in detail.
