SRCS:=thx

.venv:
	python -m venv .venv
	source .venv/bin/activate && make setup dev
	echo 'run `source .venv/bin/activate` to use virtualenv'

venv: .venv

dev:
	python -m pip install -e .

setup:
	python -m pip install -U pip
	python -m pip install -Ur requirements-dev.txt
	python -m pip install -Ur requirements.txt

release: lint test clean
	flit publish

format:
	python -m ufmt format $(SRCS)

lint:
	python -m flake8 $(SRCS)
	python -m ufmt check $(SRCS)

test:
	python -m coverage run -m $(SRCS).tests
	python -m coverage combine
	python -m coverage report
	python -m mypy --install-types --non-interactive -p $(SRCS)

html: .venv README.rst docs/*.rst docs/conf.py
	source .venv/bin/activate && sphinx-build -b html docs html

clean:
	rm -rf build dist html *.egg-info .mypy_cache

distclean: clean
	rm -rf .venv
