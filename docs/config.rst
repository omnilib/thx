Configuration
=============

`thx` is configured exclusively in your project's ``pyproject.toml``, with a limited
set of command-line options.

Command Line
------------

Most `thx` commands follow this basic pattern:

.. code-block:: shell-session

    $ thx [FLAGS] [<JOB> ...]

`thx` will run any jobs requested (or the :attr:`default` jobs if none given), in the
order requested, including any other jobs :attr:`required <requires>` by the
requested jobs.

Commands
^^^^^^^^

`thx` also includes two basic commands for convenience:

.. attribute:: list

    Lists all configured jobs, their dependencies, and the steps that will be executed
    if those jobs are run.

.. attribute:: clean

    Deletes existing `thx`-managed virtual environments.


Options
^^^^^^^

The following flags and options are supported when running jobs:

.. attribute:: --clean

    Equivalent to running the :attr:`clean` command.

.. attribute:: --debug

    Enable debug logging output.

.. attribute:: --live

    Disable the configured :attr:`python_versions` matrix, and run requested jobs
    against the live Python runtime that `thx` is using.

.. attribute:: --python VERSION | --py VERSION

    Disable the configured :attr:`python_versions` matrix, and run requested jobs
    against the specified Python version (if available).

.. attribute:: --watch | -w

    Enable :ref:`Watch Mode`. `thx` will watch for modifications to files in configured
    :attr:`watch_paths`, and automatically restart jobs after each detected change.


Project
-------

The following project-level options are supported in the ``[tool.thx]`` table:

.. attribute:: default
    :type: list[str]

    When running `thx` without explicit job names, this option defines the default set
    of jobs that will be run. If not set and no jobs are requested, `thx` will output a
    list of known jobs, equivalent to running ``thx list``.

.. attribute:: python_versions
    :type: list[str]

    This specifies the version matrix that `thx` will use when running jobs. If not
    specified, `thx` will default to using the live runtime, equivalent to running
    with ``thx --live``.

.. attribute:: requirements
    :type: list[str]

    This specifies the list of dependency requirements files (relative to project root)
    that `thx` will use when initializing virtual environments.
    If not specified, `thx` will detect any files in the project root matching the glob
    ``requirements*.txt``. Files must be usable by ``pip install -r``.

.. attribute:: watch_paths
    :type: list[str]

    This specifies the list of paths (relative to project root) that will be watched
    for modifications when running `thx` in watch mode. If not specified, `thx` will
    default to watching the entire project root. Any paths matching the project root's
    ``.gitignore`` will not trigger watch behavior, even if specified in
    :attr:`watch_paths`.


Jobs
----

Jobs are defined in the ``[tool.thx.jobs]`` table.

Simple jobs with a single step may be defined as a mapping of job name to the command:

.. code-block:: toml

    [tool.thx.jobs]
    test = "python -m unittest"

To configure any other options for the job, it must be defined as a table. Tables must
be named like ``[tool.thx.jobs.name]``, where `name` is the name of the job:

.. code-block:: toml

    [tool.thx.jobs.test]
    run = "python -m unittest -v"
    show_output = true

Inline tables are also acceptable for jobs with a single step, though dedicated tables
are generally preferred for readability:

.. code-block:: toml

    [tool.thx.jobs]
    format = {run="black project", once=true}

The following options are supported for each job:

.. attribute:: once
    :type: bool
    :value: False

    By default, `thx` will run jobs on all available versions in the configured
    :attr:`python_versions` matrix.

    When set to True, `thx` will only run this job once, using the newest available
    version in the matrix.

.. attribute:: parallel
    :type: bool
    :value: False

    By default, `thx` will run all configured steps in sequence, with each step waiting
    for the previous step to complete successfully. If an individual step fails, later
    steps will not be run.

    When set to True, `thx` will instead run all steps for this job in parallel,
    without waiting for previous steps to complete.

.. attribute:: requires
    :type: list[str]

    Any job names specified will be run before this `job`, even if they were not
    requested, or were requested after this job when invoked.

.. attribute:: run
    :type: str | list[str]

    The command or list of commands to run for this job. Commands may include standard
    Python "format string" templates, which will be substituted at runtime. See the
    `Values`_ section for details and examples.


Values
------

Projects can define an arbitrary set of static values in the ``[tool.thx.values]``
table, which then get interpolated into all command strings at runtime.

For example, with the following configuration:

.. code-block:: toml
    :caption: pyproject.toml

    [tool.thx.jobs]
    test = "python -m unittest {module}.tests"

    [tool.thx.values]
    module = "pizza"

When running this job, the executed command will look something like this:

.. code-block:: shell-session

    python -m unittest pizza.tests
