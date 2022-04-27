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


Continuous Integration
----------------------

The current recommended way to use `thx` in CI jobs is by installing it from PyPI in
the live environment:

.. code-block:: shell-session

    $ pip install thx

`thx` should then be run with the ``--live`` flag to disable the version matrix, and
only run jobs against the active runtime, rather than having a single CI job that
tests all supported versions at once:

.. code-block:: shell-session

    $ thx --live <job-name> ...


Github Actions
^^^^^^^^^^^^^^

This build workflow will run separate jobs for each supported OS and Python version,
and will install and run `thx` using the active Python version.

.. code-block:: yaml
    :caption: .github/workflows/build.yml

    name: Build
    on:
      push:
        branches:
          - main
        tags:
          - v*
      pull_request:

    jobs:
      build:
        runs-on: ${{ matrix.os }}
        strategy:
          fail-fast: false
          matrix:
            python-version: ["3.7", "3.8", "3.9", "3.10"]
            os: [macOS-latest, ubuntu-latest, windows-latest]

        steps:
          - name: Checkout
            uses: actions/checkout@v3

          - name: Set Up Python ${{ matrix.python-version }}
            uses: actions/setup-python@v3
            with:
              python-version: ${{ matrix.python-version }}
              cache: 'pip'

          - name: Install thx
            run: pip install -U thx

          - name: Test
            run: thx --live test

          - name: Lint
            run: thx --live lint
