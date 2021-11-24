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

    "makefiles, but with pyproject.toml"

    -- author

`thx` should be capable of running one or more commands, configured via simple and
obvious options in the PEP 517 standardized `pyproject.toml`.  Commands are simple
strings, or lists of strings, each representing a program to be run, with basic
interpolation of values.

.. code-block:: toml

    [tool.thx]
    default = ["lint", "test"]
    module = "thx"

    [tool.thx.commands]
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

Without a command, ``thx`` will run the configured list of default commands:

.. code-block:: shell-session

    $ thx
    > flake8 thx
    > ufmt check thx
    > python -m unittest thx.tests


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