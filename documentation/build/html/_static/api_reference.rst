=============
API reference
=============

The REST API uses JSON. Token authentication is enabled
(``Authorization: Token <key>``). No default permission class is configured,
so an endpoint is open unless this page says otherwise.

Accounts
--------
.. list-table::
    :header-rows: 1
    :widths: 35 65

    * - Endpoint
      - Description
    * - ``POST /accounts/register/``
      - Create a user. Requires the token of a staff user. Body: ``username``,
        ``email``, ``password``. Returns 201.
    * - ``POST /accounts/login/``
      - Body: ``username`` (or an email address) and ``password``. Returns
        ``{"token": "..."}``, or 401 for invalid credentials.
    * - ``POST /accounts/logout/``
      - Deletes the token of the caller. Requires a token.
    * - ``GET /accounts/users/<id>/``
      - Returns ``username`` and ``email`` of a user. Requires a token. Users
        can read themselves, staff users can read all.

Design parameters
-----------------
``POST /api/process_parameters/``

Requires a token or a browser session, and the caller must own the plant.
Other callers get 401 or 404.

Stores the design parameters of a treatment plant and calculates plant
properties (nominal flow rate and construction costs).

Request body:

.. code-block:: json

    {
        "treatmentplant_id": 1,
        "configuration_id": 1,
        "parameters": {"<designparameter id>": 10000.0},
        "technology_properties": [
            {"technology": 1, "technologyproperty": 2, "value": "35"}
        ]
    }

Responses:

* 200 with ``properties`` and a ``redirect_url`` to the results page.
* 200 with ``required_technology_properties`` and a ``redirect_url`` to the
  technology properties form, when technology-level design parameters are
  missing and ``technology_properties`` is not given.
* 400 for an invalid body.
* 401 without a token or session.
* 404 when the plant does not exist or belongs to another user.

The full set of plant KPIs is calculated by the web interface, see
:doc:`kpi_evaluation`.
