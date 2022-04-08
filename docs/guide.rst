User Guide
==========

Quick Start
-----------

`coming soon`


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