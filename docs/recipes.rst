Recipes
=======

Here are some common patterns in development workflows, and how to best achieve them
with `thx`.

Version Matrix
--------------

`thx` has direct support for running jobs on multiple Python versions in parallel.
Projects only need to list the set of supported Python versions, and `thx` will make
a best effort to find and run jobs on as many of these versions as possible:

.. code-block:: toml
    :caption: pyproject.toml

    [tool.thx]
    python_versions = ["3.8", "3.9", "3.10", "3.11"]


Formatters
----------

Formatters should generally only be run once, to prevent race conditions between jobs
on multiple Python versions running in parallel. Setting ``once = true`` will make sure
your formatter only gets run on the latest enabled Python version:

.. code-block:: toml
    :caption: pyproject.toml

    [tool.thx.format]
    run = ["black {module}"]
    once = true


Linters
-------

When running linters, results are often independent from each other, and it is often
unnecessary to wait for other steps to finish first before the next one starts.
Recommended practice is to combine all linters into a single parallel job, to make
best use of multi-core systems:

.. code-block:: toml
    :caption: pyproject.toml

    [tool.thx.job.lint]
    run = [
        "black --check {module}",
        "flake8 {module}",
        "mypy -p {module}",
    ]
    parallel = true


Test Coverage
-------------

Recording and collecting test coverage data must be handled carefully when running
tests in parallel across multiple Python versions. Recommended practice is to enable
parallel support in your coverage configuration, and add a separate job—that only runs
once—to combine and report coverage results after your test job has completed:

.. code-block:: toml
    :caption: pyproject.toml

    [tool.coverage.run]
    parallel = true

    [tool.thx.jobs.test]
    run = "python -m coverage run -m {module_tests}"

    [tool.thx.jobs.coverage]
    once = true
    requires = ["test"]
    run = [
        "python -m coverage combine",
        "python -m coverage report",
    ]

It is also common to desire seeing the coverage report, even when results are above
minimum thresholds. In these cases, the coverage job can always show its output:

.. code-block:: toml
    :caption: pyproject.toml

    [tool.thx.jobs.coverage]
    ...
    show_output = true