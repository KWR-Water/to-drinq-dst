===========================
Intellectual Property (IPR)
===========================

This document describes the intellectual property components incorporated in the
ToDrinQ Decision Support Tool (DST).

Foreground and background refer to the scope of the whole ToDrinQ project,
not whether a component is developed in this repository or installed separately.
Project-created results are foreground IP; pre-existing third-party components
are background IP. These descriptions do not assign or transfer ownership:
rights holders and access rights are determined by the applicable project
agreements and contribution provenance.

Background Intellectual Property
=================================

Background IP includes pre-existing code, models, and other material incorporated
into the project. Third-party components retain their own licences and copyright
notices; the DST's EUPL licence does not replace those notices.

Third-Party Components
----------------------

* **closuretree:** Django application for hierarchical data management
  
  - License: Apache License 2.0
  - Attribution: See headers in ``closuretree/`` directory

* **Select2:** jQuery-based select box replacement
  
  - License: MIT License
  - Source: https://select2.org/ (https://github.com/select2/select2)
  - Attribution: Included as vendor code in ``static/admin/``

* **Open-Source Dependencies:** See ``pyproject.toml`` for the complete list
  
  - Django, NumPy, pandas, SciPy, RDKit, and others
  - Review the applicable versions, licences, and redistribution obligations
    when adding or updating dependencies.

Frontend dependencies
---------------------

Third-party JavaScript and CSS are background IP, whether bundled locally or
loaded from a content delivery network (CDN). The application uses:

.. list-table::
   :header-rows: 1
   :widths: 20 45 15 20

   * - Component
     - Version and use
     - Licence
     - Upstream
   * - Bootstrap
     - 5.3.3 JavaScript and CSS in ``drinq/static/``; 5.1.3 CSS loaded
       from jsDelivr in ``templates/drinq/compound/detail.html``
     - MIT
     - https://getbootstrap.com/
   * - jQuery
     - 3.5.1 in ``drinq/static/js/``; 3.6.0 loaded from code.jquery.com
       in ``templates/drinq/form_complete.html``
     - MIT
     - https://jquery.com/
   * - Popper
     - @popperjs/core 2.11.8 in ``drinq/static/js/popper.min.js``
     - MIT
     - https://popper.js.org/
   * - Chart.js
     - Loaded from jsDelivr by the treatment-plant comparison and results
       templates; the URL does not pin a version
     - MIT
     - https://www.chartjs.org/
   * - Select2
     - Vendor assets in ``static/admin/``
     - MIT
     - https://select2.org/ and https://github.com/select2/select2

Collected assets in ``static/`` also include Django admin, Django REST Framework,
debug toolbar, and django-extensions scripts, including additional vendor
libraries such as XRegExp. Preserve their package-specific and vendor notices;
do not assume that every file has the enclosing framework's licence.
This inventory is not a complete licence audit of collected static files.

``templates/base.html`` also loads the PT Sans font through Google Fonts.
Fonts and other external assets require their own provenance and licence review,
separately from JavaScript and CSS libraries.

For redistribution, retain the applicable copyright and licence texts, not just
links to upstream websites. For CDN assets, record the version actually used and
its licence; an unversioned URL does not identify a fixed release. Original
project-specific JavaScript and CSS may be foreground IP, but using or modifying
a vendor library does not make the entire library original project work.


Foreground Intellectual Property
=================================

Foreground IP comprises intellectual property created within the ToDrinQ
project, including the NTUA packages and original DST contributions.

pystimela and pystimela_optim
-----------------------------

* **Description:** Water treatment modelling and process optimization packages
* **Versions included:** pystimela 0.0.2, pystimela_optim 0.1.2
* **Developed by:** Researchers at the National Technical University of Athens
  (NTUA), within the scope of ToDrinQ
* **Classification:** Foreground IP of the ToDrinQ project, even though packaged
  separately from the DST
* **Distribution licence:** EUPL v. 1.2
* **Public repositories:**
  `pystimela <https://bitbucket.org/team_makro/pystimela/>`_ and
  `pystimela_optim <https://bitbucket.org/team_makro/pystimelaoptim/>`_
* **Distribution:** Publicly available from Bitbucket; pre-built wheels are
  also included in ``whl/``. The packages are not available on PyPI.

Original DST contributions
---------------------------

Original project contributions include:

* Treatment technology models and scientific assumptions
* Drinking water quality simulation and decision-support algorithms
* Cost optimization and resource management frameworks
* Web application interfaces and REST API implementations
* Database schema and treatment plant configuration datasets
* Test suites, validation frameworks, and documentation
* All original Python, HTML, CSS, and JavaScript code

The provenance of the scientific models and datasets currently in this
repository has been checked. Repeat the provenance and rights review for future
additions or material changes. The repository carries a KWR Water Research
Institute copyright notice and is licensed under EUPL v. 1.2 (see ``LICENSE``).
The notice does not by itself establish ownership of every individual
contribution; rights holders are determined by applicable agreements, notices,
and contribution provenance.

IPR Summary
===========

The following table summarizes the intellectual property landscape of this project:

+------------------------------+---------------------+--------------------------+--------------------------+
| Component                    | Version/Source      | License                  | Type                     |
+==============================+=====================+==========================+==========================+
| pystimela                    | 0.0.2 (NTUA)        | EUPL v. 1.2              | Foreground IP            |
+------------------------------+---------------------+--------------------------+--------------------------+
| pystimela_optim              | 0.1.2 (NTUA)        | EUPL v. 1.2              | Foreground IP            |
+------------------------------+---------------------+--------------------------+--------------------------+
| closuretree                  | (included)          | Apache License 2.0       | Background IP            |
+------------------------------+---------------------+--------------------------+--------------------------+
| Select2                      | (vendor)            | MIT License              | Background IP            |
+------------------------------+---------------------+--------------------------+--------------------------+
| Bootstrap (JS and CSS)       | Local / CDN         | MIT License              | Background IP            |
+------------------------------+---------------------+--------------------------+--------------------------+
| jQuery                       | Local / CDN         | MIT License              | Background IP            |
+------------------------------+---------------------+--------------------------+--------------------------+
| Popper                       | 2.11.8              | MIT License              | Background IP            |
+------------------------------+---------------------+--------------------------+--------------------------+
| Chart.js                     | CDN (not pinned)    | MIT License              | Background IP            |
+------------------------------+---------------------+--------------------------+--------------------------+
| Django ecosystem             | PyPI                | Various (OSI approved)   | Background IP            |
+------------------------------+---------------------+--------------------------+--------------------------+
| ToDrinQ DST code             | Original            | EUPL v. 1.2              | Foreground IP            |
+------------------------------+---------------------+--------------------------+--------------------------+
| Scientific models & datasets | Checked; review new additions | Check component terms  | Depends on provenance    |
+------------------------------+---------------------+--------------------------+--------------------------+
| Documentation & tests        | Original            | EUPL v. 1.2              | Foreground IP            |
+------------------------------+---------------------+--------------------------+--------------------------+


Attribution and Acknowledgments
===============================

**Optimization Framework**
  The pystimela and pystimela_optim packages were developed by researchers at
  the National Technical University of Athens (NTUA). They are publicly
  available under the EUPL v. 1.2 license from
  `pystimela <https://bitbucket.org/team_makro/pystimela/>`_ and
  `pystimela_optim <https://bitbucket.org/team_makro/pystimelaoptim/>`_.

**Third-Party Libraries**
  This project builds on excellent open-source libraries, including:
  
  - **Select2** (MIT License) - jQuery-based select box enhancement
    Available at https://select2.org/ (https://github.com/select2/select2)
  - **Django ecosystem** - Web framework and related packages
  - **Scientific packages** - NumPy, pandas, SciPy, RDKit, and others
  
  See ``pyproject.toml`` for a complete list and their respective licenses.

**Included Components**
  - **closuretree** (Apache License 2.0) - Django hierarchical data management


Guidelines for Contributors
============================

When contributing to this project, please note:

* **Foreground IP:** Identify new project-created contributions and their
  contributors. Copyright in a contribution remains with its contributor or,
  where applicable, the contributor's employer or another rights holder.
  Submission and acceptance do not transfer copyright to the project, KWR, or
  another project partner. Accepted DST contributions are made available under
  EUPL v. 1.2; contributors must be authorized to grant that licence. This
  does not reclassify pre-existing material as foreground IP.

* **Background IP:** If you incorporate any third-party code, models, or data:
  
  - Verify that the source license is compatible with EUPL v. 1.2
  - Include proper attribution, copyright, and licensing information
  - Document the provenance in your pull request
  - Do not include proprietary, confidential, or restricted-license materials

* **Scientific Data and Models:** Provide clear documentation of:
  
  - Sources and equations
  - Units, assumptions, and applicability limits
  - Reproducible test cases and expected outputs
  - Any data licensing or attribution requirements

See ``CONTRIBUTING.rst`` for the full contribution policy.
