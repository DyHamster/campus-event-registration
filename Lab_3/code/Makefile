PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
BUILD_DIR ?= build
PORT ?= 8000

.PHONY: build test setup demo

build:
	PYTHONPYCACHEPREFIX="$(abspath $(BUILD_DIR))/pycache" $(PYTHON) -m compileall -q campus_events

test:
	$(PYTHON) -B -m unittest discover -s tests -v

setup:
	$(PYTHON) -m venv .venv
	.venv/bin/python -m pip install -r requirements.txt

demo:
	$(PYTHON) -B -m campus_events.web --database data/web-demo.sqlite3 --demo --port $(PORT)
