==============
KPI evaluation
==============

The tool evaluates a treatment plant on two levels. First, each technology in
the train gets its own KPIs. Second, the technology KPIs are combined with the
design parameters into plant KPIs.

Calculation pipeline
--------------------
The pipeline is ``_run_calculation_pipeline`` in ``drinq/views.py``. It starts
when the user presses *Calculate* on the technology properties page. It reads
all inputs from the database, so it always uses the values that were just
saved.

.. mermaid::

    flowchart TD
        A[Design parameters] --> N[Nominal flow]
        B[Technology properties<br/>defaults and user values] --> T[Technology KPIs]
        C[Water quality in and target] --> T
        D[Chemical prices] --> T
        N --> T
        T --> S[Sum over technologies]
        S --> P[Plant KPIs]
        N --> P
        A --> P
        T --> CC[Construction costs]
        CC --> P
        P --> R[Stored plant properties]
        T --> R2[Stored technology KPI values]

Input values
------------
Inputs come from three sources.

1. **Database defaults.** ``TechnologyPropertyJunction.default_value``,
   ``DesignParameter.defaultvalue`` and the default chemical prices.
2. **User input.** Values entered per plant on the parameter and technology
   pages.
3. **Calculated values.** Properties flagged ``is_digested`` are calculated by
   the KPI classes. Values returned by the optimiser are marked as optimised.

Every stored technology property value carries a source: ``user``,
``digested`` or ``optimized``.

Design parameters
-----------------
The plant-level parameters are stored in ``DesignParameter``. The calculation
uses the following names.

.. list-table::
    :header-rows: 1
    :widths: 45 55

    * - Parameter
      - Use
    * - population persons
      - Drinking water demand
    * - average consumption (lppd)
      - Demand per person per day
    * - large-scale consumption (m3/day)
      - Extra demand, for example industry
    * - leakage factor
      - Extra production for network losses
    * - peak daily demand factor
      - Design flow relative to average flow
    * - interest rate, depreciation period
      - Capital costs (percent and years)
    * - operation and maintenance rate
      - O&M costs as a percentage of construction costs
    * - personnel costs
      - Annual personnel costs
    * - energy price
      - Price per kWh

Nominal flow
------------
The plant is designed for the nominal flow :math:`Q` in m3/h:

.. math::

    Q = \left(Q_{pop} + \frac{Q_{large}}{24}\right)
        (1 + f_{leak}) \, f_{peak}

Here :math:`Q_{pop}` is the demand of the population in m3/h, :math:`Q_{large}`
the large-scale demand in m3/day, :math:`f_{leak}` the leakage factor and
:math:`f_{peak}` the peak factor.

Technology KPIs
---------------
Each technology is matched on its stage and name to a KPI class in
``drinq/utils/treatmentkpi.py``. The classes share the base class
``TreatmentKPI`` and calculate the same set of KPIs.

.. list-table::
    :header-rows: 1
    :widths: 40 15 45

    * - KPI
      - Unit
      - Remark
    * - footprint area
      - m2
      -
    * - daily energy consumption
      - kWh/day
      -
    * - power
      - kW
      -
    * - head loss
      - bar
      - Hydraulic loss over the unit.
    * - daily mass of chemicals
      - kg/day
      - Per chemical. Used for costs and emissions.
    * - chemical solution concentration
      - mg/L
      -
    * - CO2 equivalent emissions
      - kg CO2-eq/m3
      - From electricity and chemicals. The code marks the summation as
        work in progress.
    * - daily chemical costs
      - EUR/day
      - Mass per chemical times the chemical price.

The available classes cover these groups. Technologies without a class
get no technology KPIs.

* Screening: strainer, micro strainer.
* Coagulation and flocculation: dynamic mixing, inline mixing, cascade mixer,
  flocculation.
* Floc removal: sludge blanket, chain-scraped sedimentation, flotation,
  lamella clarifier (sloped and horizontal).
* Filtration: rapid sand (single, dual, pressurised, moving bed), membranes.
* Advanced treatment: GAC, PAC, UV/H2O2, ozone contactor, ion exchange,
  pellet softening.
* Disinfection and storage: chlorine, chloramine, UV, clean water storage.

Plant KPIs
----------
The technology KPIs for footprint, energy, power, head loss, CO2 and chemical
costs are summed over the technologies. The plant KPIs are then derived.

.. list-table::
    :header-rows: 1
    :widths: 40 60

    * - Plant KPI
      - Definition
    * - nominal flow rate
      - See above.
    * - footprint area
      - Sum of technology footprints.
    * - specific energy consumption
      - Daily energy divided by daily flow, in kWh/m3.
    * - CO2 equivalent emissions
      - Sum of technology emissions, in kg/m3.
    * - construction costs
      - See below.
    * - operation and maintenance costs (annual)
      - Construction costs times the O&M rate.
    * - investment costs (annual)
      - Total annual costs, see below.
    * - levelized cost of water
      - Total annual costs per m3 produced.
    * - levelized chemical costs
      - Annual chemical costs per m3 produced.
    * - adaptability score
      - See below.

Costs
-----
**Construction costs.** For each technology the cost is a polynomial in one
technology property :math:`x_t` (for example a volume or an area) or one plant
property :math:`x_p` (for example the nominal flow):

.. math::

    C_{tech} = a x_t^2 + b x_t + c x_p^2 + d x_p + e

The coefficients are stored per technology in
``TechnologyConstructionCostParameter``. Unused coefficients are zero. The sum
over all technologies is multiplied by surcharge factors for construction
(20%), tail costs (5%) and general facilities (5%). The calculation is
``construction_costs_total`` in ``drinq/utils/financial_costs.py``.

**Annual costs.** With construction costs :math:`C`, lifespan :math:`L`,
interest rate :math:`i` and O&M rate :math:`p`:

.. math::

    T = \frac{C}{L} + C\,i + C\,p + E + P + K

where :math:`E` is the energy costs (daily energy times 365 times the energy
price), :math:`P` the personnel costs and :math:`K` the chemical costs (daily
chemical costs times 365). The depreciation is linear and the interest is
charged on the full construction costs.

**Levelized cost of water.**

.. math::

    LCOW = \frac{T}{24 \cdot 365 \cdot Q}

Adaptability
------------
Adaptability describes how well a technology copes with change, for example in
raw water quality. Each technology has a score per ``AdaptabilityCriterion``
in ``TechnologyAdaptabilityScore``. The technology score is the mean over its
criteria. The plant score is the mean over the technologies and is stored as
the plant property *adaptability score* (0 to 1). The details are shown at
``/treatmentplant/<id>/adaptability/``.

Optimisation
------------
For selected processes the user can run an optimisation instead of a plain
calculation. The processes are coagulation-flocculation, single and dual
filtration, GAC, chlorination and ozonation.

.. mermaid::

    flowchart LR
        A[Plant inputs] --> B[Payload and CSV inputs<br/>research/pystimela_optim/inputs]
        B --> C[Config JSON per process]
        C --> D[pystimela_optim run]
        D --> E[results JSON<br/>in outputs]
        E --> F[Store properties,<br/>water quality and KPIs]
        F --> G[Recalculate plant KPIs]

* The mapping between DRINQ properties and optimiser parameters is stored in
  ``TechnologyPystimelaoptJunction``, ``TechnologyPropertyPystimelaoptJunction``
  and ``TechnologyWaterqualityParameterPystimelaoptJunction``. Only properties
  flagged ``sent_to_optimizer`` are sent.
* By default the run starts in a background thread (setting
  ``OPTIMIZER_ASYNC``). The page polls
  ``/treatmentplant/<id>/technology/optimizer-status/``.
* ``TreatmentPlantTechnologyOptimizationStatus`` records per plant and
  technology whether the result is current. It stores a hash of the inputs.
  When the user changes an input, the hash no longer matches and the stale
  result is dropped.
* *Reset optimization* clears the flags and recalculates with the user and
  default values.

Comparing designs
-----------------
``/treatmentplant/compare/`` places the plant properties of two designs side
by side per category. The radar chart scales each property to the larger of
the two values and shows the mean per category.
