RUN := uv run --locked
LINTED := pycg tests tools micro-benchmark/validate.py evaluation
INPUTS := evaluation/container/Dockerfile.inputs
PROJECTS := evaluation/macro-benchmark/projects
EVAL_OUT ?= $(or $(TMPDIR),/tmp)/pycg-evaluation
GIT_COMMON = $(abspath $(shell git rev-parse --git-common-dir))

.PHONY: setup test lint format eval

setup:
	uv sync --locked

test:
	$(RUN) pytest

lint:
	$(RUN) ruff check $(LINTED)
	$(RUN) ruff format --check $(LINTED)

format:
	$(RUN) ruff check --select I --fix $(LINTED)
	$(RUN) ruff format $(LINTED)

eval:
	docker build --target macro -t pycg-eval-macro -f $(INPUTS) .
	docker build --target network -t pycg-eval-runner -f $(INPUTS) .
	rm -rf $(PROJECTS)
	mkdir $(PROJECTS)
	mkdir -p $(EVAL_OUT)
	docker run --rm --network none --user $$(id -u):$$(id -g) \
		-v $(CURDIR)/$(PROJECTS):/out pycg-eval-macro \
		cp -RP /inputs/macro-benchmark/projects/. /out/
	docker run --rm --network none --read-only --tmpfs /tmp \
		--memory 6g --memory-swap 6g --cap-drop ALL \
		--security-opt no-new-privileges --user $$(id -u):$$(id -g) \
		-e HOME=/tmp -e PYTHONHASHSEED=0 \
		-v $(CURDIR):$(CURDIR):ro -v $(GIT_COMMON):$(GIT_COMMON):ro \
		-v $(EVAL_OUT):/out pycg-eval-runner \
		sh -c "git config --global --add safe.directory '*' \
		&& python3 -I $(CURDIR)/evaluation/common/loop.py run --flavour new \
		--checkout $(CURDIR) --name pycg-$$(git rev-parse --short=10 HEAD) --out /out"
