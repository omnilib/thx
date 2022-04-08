thx
===

A fast command runner for Python projects.

.. image:: https://img.shields.io/pypi/l/thx.svg
   :target: https://github.com/jreese/thx/blob/main/LICENSE
   :alt: MIT Licensed
.. image:: https://img.shields.io/pypi/v/thx.svg
   :target: https://pypi.org/project/thx
   :alt: PyPI Release
.. image:: https://img.shields.io/badge/change-log-blue
   :target: https://github.com/jreese/thx/blob/main/CHANGELOG.md
   :alt: Changelog
.. image:: https://readthedocs.org/projects/thx/badge/?version=stable
   :target: https://thx.readthedocs.io/
   :alt: Documentation Status
.. image:: https://github.com/jreese/thx/workflows/Build/badge.svg
   :target: https://github.com/jreese/thx/actions
   :alt: Build Status


`thx` is capable of running arbitrary jobs, configured via simple options in the
`PEP 518 <https://peps.python.org/pep-0518/>`_ standardized ``pyproject.toml``.
Jobs can be run on multiple Python versions at once, and independent steps can be
executed in parallel for faster results.

Watch `thx` format the codebase, build sphinx docs, run the test and linter suites on
five Python versions, and generate a final coverage report:

.. image:: https://asciinema.org/a/ZoT8qYbQ2g8wl1FrR9JSpRqRZ.svg
    :target: https://asciinema.org/a/ZoT8qYbQ2g8wl1FrR9JSpRqRZ
    :alt: Demo of thx

`thx` can also watch for modifications to your project, and automatically run jobs
every time changes are detected—it will even reload its configuration when your
``pyproject.toml`` changes:

.. image:: https://asciinema.org/a/uE79pfl07YzTiDmGnNzgY1GWG.svg
    :target: https://asciinema.org/a/uE79pfl07YzTiDmGnNzgY1GWG
    :alt: Demo of thx in watch mode


Usage
-----

Configuration uses standard `TOML <https://toml.io>`_ elements, and jobs can
reference shared values, which will be interpolated at runtime:

.. code-block:: toml

    [tool.thx.values]
    module = "thx"

    [tool.thx.jobs]
    lint = [
        "flake8 {module}",
        "ufmt check {module}",
    ]
    test = "python -m unittest -v {module}.tests"

The configuration above defines two jobs, "lint" and "test"; the "lint" job defines
two steps, and these can optionally be run in parallel. Both jobs present themselves
as separate commands in `thx`. Note the automatic replacement of ``{module}`` with
the configured value ``thx`` when running jobs:

.. code-block:: shell-session

    $ thx lint
    > flake8 thx
    > ufmt check thx

.. code-block:: shell-session

    $ thx test
    > python -m unittest thx.tests

They can also be run together in order, similar to `makefiles`:

.. code-block:: shell-session
    
    $ thx test lint
    > python -m unittest thx.tests
    > flake8 thx
    > ufmt check thx

By default, `thx` uses the active Python runtime for jobs, but can also run jobs on 
multiple runtimes in parallel:

.. code-block:: toml

    [tool.thx]
    python_versions = ["3.7", "3.8", "3.9"]

.. code-block:: shell-session

    $ thx test
    3.9> python -m unittest thx.tests
    3.8> python -m unittest thx.tests
    3.7> python -m unittest thx.tests

See the `user guide <https://thx.readthedocs.io>`_ for details on all available
configuration options.


Install
-------

.. note::

    `thx` is still in active development. Configuration options should be stable, but
    compatibility between minor releases is not guaranteed. For important production
    cases, please be sure to pin yourself to a single version, and test any new releases
    thoroughly.

`thx` is available on `PyPI <https://pypi.org/project/thx>`_:

.. code-block:: shell-session

    $ pip install thx

See the `user guide <https://thx.readthedocs.io>`_ for help getting started.


License
-------

`thx` is copyright `John Reese <https://jreese.sh>`_, and licensed under
the MIT license. I am providing code in this repository to you under an open
source license. This is my personal repository; the license you receive to my
code is from me and not from my employer. See the `LICENSE`_ file for details.

.. _LICENSE: https://github.com/jreese/thx/blob/main/LICENSE