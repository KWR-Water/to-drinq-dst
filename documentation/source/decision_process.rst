================
Decision process
================

The decision process turns the answers of a user into a list of treatment
trains. It does not rank the trains. Ranking is left to the user, who compares
the KPIs of the trains that remain.

Building blocks
---------------
.. list-table::
    :header-rows: 1
    :widths: 30 70

    * - Model
      - Role
    * - ``DesignTree``
      - One decision tree per water source.
    * - ``DecidingFactorQuestion``
      - A question, linked to a ``CategoricalVariable`` that defines the
        possible answers.
    * - ``DecidingFactorChoice``
      - One possible answer to a question.
    * - ``DecidingFactor``
      - A node in the tree. A node holds either a question or a choice. Its
        parent and children define the order of the questions.
    * - ``TechnologyDecidingFactorJunction``
      - Links a choice to the technologies it selects (``effective_technology``).
    * - ``TechnologyRelatedtechnology``
      - Marks technologies that are the previous, current or next step of
        another technology.
    * - ``StageTechnologies``, ``Stage``
      - Assign technologies to treatment stages, for example screening,
        coagulation or disinfection.
    * - ``MultiStepConfiguration``, ``QuestionAnswer``
      - The stored session of a user and the answers given.

``DecidingFactor`` extends ``ClosureModel`` from the ``closuretree`` app. The
app keeps a closure table, so ancestors and descendants of a node are found
with one query (``get_children()``, ``get_descendants()``).

Steps
-----
.. mermaid::

    flowchart TD
        A[Water source selected] --> B[First question of the design tree]
        B --> C[User picks a choice]
        C --> D[QuestionAnswer saved]
        D --> E{More children?}
        E -->|yes| B
        E -->|no| F[Collect technologies per answer]
        F --> G[Build stage buckets]
        G --> H[Cartesian product of buckets]
        H --> I[Treatment options]
        I --> J[User filters and names options]

1. **Water source.** The chosen source selects the ``DesignTree``. The view
   ``FormWaterSourceView`` finds the node of the water source choice and
   takes its first child as the first question.
2. **Questions.** ``MultiStepQuestionView`` shows one question at a time and
   stores the answer. It follows the child node that belongs to the chosen
   answer. Nodes without a question are skipped. A choice stored on such a
   node is recorded as an answer automatically. The walk ends when a node has
   no more children, or after ``DECISION_TREE_MAX_STEPS`` (50) steps.
3. **Technologies per answer.** ``get_technology_of_choice()`` returns the
   technology ids of a choice, or ``None``. Several ids mean interchangeable
   alternatives.
4. **Stage buckets.** For each answer, in order of the answers,
   ``_build_choice_buckets()`` creates up to three buckets: an optional
   previous-step bucket, the alternatives of the choice, and an optional
   next-step bucket. ``_append_stage_buckets()`` appends them to the running
   sequence and skips a bucket that repeats the one before it.
5. **Treatment trains.** ``get_treatment_trains()`` takes the product of all
   buckets (``itertools.product``). Each combination is one treatment option
   with ordered steps. The placeholder technologies "no technology" and
   "dummy technology" are left out.
6. **Review.** ``QuestionsCompleteView`` shows one dropdown per stage. The
   stage name comes from ``StageTechnologies``. Picking a technology in a
   dropdown filters the options. Options that are already named are marked.
7. **Naming.** Naming an option creates a ``TreatmentPlant`` with its
   ``TreatmentPlantLayout``, one row per step. From here on the KPI
   evaluation applies.

Design rules
------------
* One bucket holds all alternatives of one choice. Alternatives are never
  split over several buckets, otherwise the number of dropdowns explodes.
* Buckets are appended in order. They are never merged by index across
  choices, because each choice starts counting at zero.
* The stage membership in the database is not used to place bucket
  boundaries, because a technology can belong to more than one stage.

These rules are covered by ``tests/test_treatmentoptions_stage_bucketing.py``
and ``tests/test_decision_tree.py``.
