=======================
Contributing to the DST
=======================

Contributions to the ToDrinQ Decision Support Tool (DST) are welcome.
You can report bugs, improve documentation, add tests, contribute treatment
models or appropriately licensed datasets, and propose code changes.

Maintenance availability
------------------------
The current main developers have limited time for maintenance. Responses
to issues, pull request reviews, approvals, and merges may take some time.
There is no guaranteed response or review timeframe. Please plan
accordingly: opening a pull request does not guarantee its acceptance or
inclusion in a particular release.

Keep contributions focused and provide enough context for asynchronous
review. If you have a deadline, mention it when discussing the work,
but do not assume that the maintainers can meet it.

Roles and responsibilities
--------------------------
* **Contributors** discuss proposed work, implement focused changes, add
  relevant tests and documentation, and respond to review feedback.
* **Main developers (maintainers)** triage issues, review and approve pull
  requests (PRs), and merge accepted changes into ``main``.
* **Domain reviewers** assess changes to treatment models, scientific
  assumptions, datasets, KPI calculations, or treatment recommendations.
  Their assessment complements, rather than replaces, maintainer review.

Repository access does not remove the review requirement. An author must
not approve or merge their own PR. A maintainer's own contribution needs
review and merging by another maintainer.

Discuss the work first
----------------------
Search the repository's `issues`_ and `pull requests`_ before starting to
avoid duplicating work.

Open an issue before substantial changes, such as a new feature, a new
treatment model, a dependency change, an API change, or a database schema
change. Describe the problem, proposed approach, and expected effect on
users and scientific results. Wait for maintainer agreement on the scope
before investing in substantial implementation.

Small bug fixes and documentation corrections may go directly to a PR.
For bug reports, include reproduction steps, expected and actual
behaviour, and relevant environment details. Remove secrets and private
data from logs, screenshots, and example inputs.

Development workflow
--------------------
Use short-lived branches based on the latest ``main``. There is no
permanent ``develop`` branch in this workflow.

1. External contributors fork the repository and clone their fork.
   Collaborators with write access may clone the repository directly.
2. Create a focused branch, for example ``fix/kpi-calculation``,
   ``feature/treatment-model``, or ``docs/contributing``.
3. Follow the environment and startup instructions in the `README`_.
   The server and tests currently require both optimizer wheels, even if
   your change does not concern optimization.
4. Implement one coherent change. Follow existing project conventions
   and add or update relevant tests and documentation.
5. Run the relevant validation, inspect the diff, and push the branch.
   Avoid committing local database changes or generated results unless
   they are explicitly part of the agreed contribution.
6. Open a PR targeting the upstream repository's ``main`` branch.
   Use a draft PR if you want early feedback before the work is ready.
7. Address review feedback and update the validation results after
   changes. A maintainer other than the author merges the accepted PR.

Testing and documentation
-------------------------
Run commands from the repository root in the configured optimizer
environment. For example, run the Django checks and the test modules
relevant to your change::

    python manage.py check
    python manage.py test tests.test_access_control tests.test_admin

Replace the example test modules with those covering your change.
Optimizer-specific unit tests can be run with::

    python -m unittest tests.test_pystimela_optim_scripts

Run the full Django suite when the scope warrants it::

    python manage.py test

The Getting Started documentation records known failures in the full
suite, mainly in technology KPI tests. Do not treat every failure as
pre-existing: compare with the unchanged base revision in a separate
checkout using the same environment and test inputs. Record the commands,
results, and any confirmed baseline failures in the PR. New failures
introduced by the contribution must be resolved before merging.

For documentation changes, install the documentation requirements as
described in the README and build the HTML documentation::

    cd documentation
    make html

On Windows PowerShell, use ``.\make.bat html`` instead of ``make html``.
Inspect the generated pages, including navigation and links, and report
any build warnings. Do not commit generated documentation output.

Run any applicable project-configured formatting, linting, and type
checks, and report their results. Do not claim checks passed if they were
not run; explain any validation that could not be completed.

Scientific models and data
--------------------------
Changes affecting scientific outputs require an additional domain
review. Provide:

* Sources and redistribution rights for models and datasets.
* Equations, units, assumptions, applicability limits, and provenance.
* Reproducible, non-sensitive example inputs and expected outputs.
* Tests or comparisons demonstrating the expected effect on KPIs,
  optimization results, or treatment recommendations.
* An explanation of changes to existing outputs and any implications
  for interpreting results.

Use synthetic or appropriately licensed example data, not confidential
utility, customer, or personal data.

Pull request checklist
----------------------
Before requesting review, check that the PR includes:

* A clear description of the problem and solution, with a linked issue
  where applicable.
* A focused diff without unrelated refactoring or generated files.
* Relevant tests and updated documentation.
* Validation commands and results, including confirmed baseline failures
  and any checks not run.
* Screenshots for visible interface changes, where useful.
* Details of database migrations, dependencies, API changes, or changes
  in scientific outputs, where applicable.
* No credentials, private data, or unexplained local database changes.

Review and merging
------------------
The contribution policy is:

* At least one main developer other than the author must approve the PR.
* Changes affecting scientific results or recommendations also require
  a domain review, with the assessment recorded on the PR.
* Review conversations must be resolved before merging.
* Substantive changes after approval require renewed approval.
* Relevant validation must pass without new regressions. Once automated
  checks are configured as required, they must pass before merging.
* A maintainer other than the author uses a squash merge into ``main``
  so that each PR becomes one coherent commit.
* Delete the contribution branch after merging. External contributors
  can delete the branch in their own fork.

The same review process applies to urgent fixes. Do not bypass it as a
routine shortcut. Keep discussion constructive, explain technical
decisions, and allow time for maintainers and contributors to respond.

Public repository safeguards
----------------------------
Never commit credentials, tokens, local environment files such as
``.env``, private utility or customer data, sensitive database contents,
or logs containing such information.

Contributions are accepted under the project's EUPL-1.2 licence. Submit
only material you have the right to contribute under those terms.
Preserve copyright and third-party licence notices, including those for
the Apache-2.0-licensed ``closuretree`` app. See the project `licence`_.

Do not disclose exploitable vulnerabilities in public issues or PRs.
Use GitHub's private vulnerability reporting option in the repository's
Security tab if it is enabled. If it is unavailable, obtain a private
contact for a maintainer through their published institutional contact
details before sharing sensitive information.

Repository-owner setup before public release
--------------------------------------------
The following are maintainer setup tasks, not features enabled by this
guide. Repository owners should:

* Designate the main developers responsible for reviews and merges, and
  identify domain reviewers for scientific changes.
* Protect ``main`` with a GitHub ruleset requiring PRs and an independent
  maintainer approval. Restrict updates to the maintainers responsible
  for merging; block direct pushes, force pushes, and branch deletion.
* Require resolved review conversations and dismiss stale approvals
  after new changes. Avoid routine use of administrative bypasses.
* Enable squash merging and automatic deletion of merged branches.
* Establish a reliable test baseline and GitHub Actions checks before
  making those checks required. Until then, review the validation
  evidence recorded in each PR.
* Enable private vulnerability reporting or publish an agreed private
  reporting contact before making the repository public.
* Review the files and Git history for secrets and private data, and
  confirm redistribution rights for bundled optimizer wheels and
  datasets before publication.

Documenting this workflow does not configure branch protection, install
CI workflows, assign reviewers, or certify the repository for publication.

.. _issues: https://github.com/KWR-Water/to-drinq-dst/issues
.. _pull requests: https://github.com/KWR-Water/to-drinq-dst/pulls
.. _README: https://github.com/KWR-Water/to-drinq-dst/blob/main/README.md
.. _licence: https://github.com/KWR-Water/to-drinq-dst/blob/main/LICENSE
