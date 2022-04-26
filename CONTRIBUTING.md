# Contributing to thx

## Preparation

You'll need to have Python 3.7 or newer available for testing.
I recommend using [pyenv][] for this:

    $ pyenv install 3.7.13
    $ pyenv local 3.7.13

Ideally, you should also have newer versions as well:

    $ pyenv local 3.10.4 3.9.9 3.8.12 3.7.13


## Testing

Create a fresh development environment, and bootstrap thx: 

    $ cd <path/to/thx>
    $ python -m venv venv
    $ source venv/bin/activate
    (venv) $ pip install -U pip -r requirements-dev.txt
    (venv) $ pip install -e .

Run the test suite from your bootstrapped version of thx:

    (venv) $ thx


## Submitting

Before submitting a pull request, please ensure
that you have done the following:

* Documented changes or features in README.md
* Added appropriate license headers to new files
* Written or modified tests for new functionality
* Run `thx` to run the formatter, and passed the test suite and all linters.

[pyenv]: https://github.com/pyenv/pyenv
