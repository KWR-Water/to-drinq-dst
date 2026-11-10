===
FAQ
===
Frequently Asked Questions

Why does a technology have no KPIs?
    The KPIs are calculated by a class that is matched on the stage and the
    name of the technology. A new technology needs a branch in
    ``TechnologyPerformanceCalculator.calculate_kpi``.

Why did my optimised values disappear?
    The tool stores a hash of the inputs with each optimiser result. After an
    input changes, the result is stale and the tool recalculates with the
    user and default values. Run the optimisation again.

How can I restore the default values?
    Press *Reset optimization* on the technology properties page to drop
    optimised values. Values that you entered stay as they are.

Why do I get an error after selecting the water source?
    The design tree of that water source needs a node for the water source
    choice with a question node below it. Check the ``DecidingFactor`` rows.

Why do I get a 404 on a treatment plant page?
    You can only open plants that belong to your own configurations. Staff
    users can open all plants. Check that you are logged in with the right
    account.

Does the tool rank the treatment options?
    No. The decision tree reduces the options. Use the KPIs and the
    comparison page to choose.

Where are the logs?
    ``general.log`` in the project root and ``pystimela.log`` for the
    optimiser.

Django does not start and mentions ``pkg_resources``.
    Install ``setuptools<81`` in the environment.
