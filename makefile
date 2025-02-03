PKG:=thx
EXTRAS:=dev,docs

UV:=$(shell uv --version)
ifdef UV
	VENV:=uv venv
	PIP:=uv pip
else
	VENV:=python -m venv
	PIP:=python -m pip
endif

install:
	$(PIP) install -Ue .[$(EXTRAS)]

.venv:
	$(VENV) .venv

venv: .venv
	source .venv/bin/activate && make install
	echo 'run `source .venv/bin/activate` to activate virtualenv'

format:
	python -m ufmt format $(PKG)

lint:
	python -m flake8 $(PKG)
	python -m ufmt check $(PKG)

test:
	python -m coverage run -m $(PKG).tests
	python -m coverage combine
	python -m coverage report
	python -m mypy --install-types --non-interactive -p $(PKG)

html: .venv README.rst docs/*.rst docs/conf.py
	source .venv/bin/activate && sphinx-build -b html docs html

clean:
	rm -rf build dist html *.egg-info .mypy_cache

distclean: clean
	rm -rf .venv
