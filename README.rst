thx
===

A simple, composable command runner for Python projects.

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


Goals
-----

    "like makefiles, but in pyproject.toml"

    -- author

`thx` is capable of running one or more jobs, configured via simple options in the
PEP 517 standardized `pyproject.toml`. Jobs can be run on multiple Python versions at
once, and individual steps can be executed in parallel for faster results.

.. raw:: html

    <script id="asciicast-3zNkVeBxbQrwIDK5EbydnjDyV" src="https://asciinema.org/a/3zNkVeBxbQrwIDK5EbydnjDyV.js" async></script>

.. literalinclude:: ../pyproject.toml
    :language: toml
    :start-after: [tool.thx]

.. code-block:: toml

    [tool.thx]
    default = ["lint", "test"]
    module = "thx"

    [tool.thx.jobs]
    lint = [
        "flake8 {module}",
        "ufmt check {module}",
    ]
    test = "python -m unittest -v {module}.tests"

With the given configuration, the following commands are possible. Note the automatic
replacement of ``{module}`` with ``thx``:

.. code-block:: shell-session

    $ thx lint
    > flake8 thx
    > ufmt check thx

.. code-block:: shell-session

    $ thx test
    > python -m unittest thx.tests

Without a command, ``thx`` will run the configured list of default jobs:

.. code-block:: shell-session

    $ thx
    > flake8 thx
    > ufmt check thx
    > python -m unittest thx.tests


Terminology
-----------

* `command` refers to an individual program executed by `thx` as a subprocess,
  including any rendered template values. An example command could include running unit
  tests via ``python -m unittest thx``.

* `step` refers to a pending command, before any template values are rendered, and
  includes the configuration, environment, and any other values that may affect the
  final program and arguments that will be executed.

* `job` refers to a named job, consisting of one or more steps, and a list of any other
  jobs that must be completed before this job can begin (`"requires"`). These are the
  primary unit defined in the project's ``pyproject.toml``.


Install
-------

`thx` is not yet ready for production use. Check the Github repo for development status.


License
-------

`thx` is copyright `John Reese <https://jreese.sh>`_, and licensed under
the MIT license. I am providing code in this repository to you under an open
source license. This is my personal repository; the license you receive to my
code is from me and not from my employer. See the `LICENSE`_ file for details.

.. _LICENSE: https://github.com/jreese/thx/blob/main/LICENSE