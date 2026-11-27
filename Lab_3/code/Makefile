PYTHON ?= python3
BUILD_DIR ?= build

.PHONY: build test

build:
	PYTHONPYCACHEPREFIX="$(abspath $(BUILD_DIR))/pycache" $(PYTHON) -m compileall -q campus_events

test:
	$(PYTHON) -B -m unittest discover -s tests -v
