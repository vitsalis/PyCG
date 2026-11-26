RUN := uv run --locked
LINTED := pycg tests tools evaluation
INPUTS := evaluation/container/Dockerfile.inputs
INPUTS_REGISTRY := ghcr.io/vitsalis
PROJECTS := evaluation/macro-benchmark/projects
METRICS := evaluation/metrics.json
EVAL_OUT ?= $(or $(TMPDIR),/tmp)/pycg-evaluation
EVAL_JOBS ?= $(shell nproc)
BASE ?=
SUMMARY ?= /dev/stdout
LABELS ?= /dev/stdout
OUTPUTS ?= /dev/stdout
GIT_COMMON = $(abspath $(shell git rev-parse --git-common-dir))
COMMIT = $(shell git rev-parse --short=10 HEAD)
RESULT = $(EVAL_OUT)/pycg-$(COMMIT)
BASE_COMMIT = $(shell git rev-parse --short=10 $(BASE))
BASE_RESULT = $(EVAL_OUT)/base-$(BASE_COMMIT)-for-$(COMMIT)
BASE_TREE = $(EVAL_OUT)/tree-$(BASE_COMMIT)
BASE_METRICS = $(EVAL_OUT)/metrics-$(BASE_COMMIT).json
SANDBOX = docker run --rm --network none --read-only --tmpfs /tmp \
	--memory 6g --memory-swap 6g --cap-drop ALL \
	--security-opt no-new-privileges --user $$(id -u):$$(id -g) \
	-e HOME=/tmp -e PYTHONHASHSEED=0 \
	-v $(CURDIR):$(CURDIR):ro -v $(GIT_COMMON):$(GIT_COMMON):ro \
	-v $(EVAL_OUT):$(EVAL_OUT) pycg-eval-runner python3 -I
LOOP = $(SANDBOX) $(CURDIR)/evaluation/common/loop.py
GATE = $(SANDBOX) $(CURDIR)/evaluation/common/gate.py
LABELER = $(SANDBOX) $(CURDIR)/evaluation/common/labels.py
measure = $(SANDBOX) $(1)/evaluation/common/loop.py run --flavour new --checkout $(1) \
	--name $(2) --hash-seed $(3) --micro-jobs $(EVAL_JOBS) --out $(EVAL_OUT) \
	&& $(GATE) digest $(1) > $(EVAL_OUT)/$(2)/benchmark_sha256
measured = test -f $(RESULT)/result.json || ($(call measure,$(CURDIR),$(notdir $(RESULT)),0))
base_metrics = git rev-parse --verify --quiet $(BASE)^{commit} > /dev/null \
	&& (git show $(BASE):$(METRICS) > $(BASE_METRICS) 2> /dev/null \
	|| : > $(BASE_METRICS))
base_inputs = if [ "$$(python3 -I $(BASE_TREE)/tools/inputs_key.py)" = "$$(python3 -I tools/inputs_key.py)" ]; \
	then cp -RP $(PROJECTS) $(BASE_TREE)/$(PROJECTS); \
	else $(MAKE) --no-print-directory -C $(BASE_TREE) eval-inputs \
	&& $(MAKE) --no-print-directory eval-inputs; fi
need_base = $(if $(BASE),,$(error $@ needs BASE=<git ref of the base commit>))

define gate
$(base_metrics)
$(GATE) check $(RESULT) $(BASE_RESULT) $(BASE_METRICS)
endef

define report
$(GATE) report $(RESULT) $(CURDIR)/$(METRICS) >> $(SUMMARY)
endef

define measure_base
git worktree add --detach $(BASE_TREE) $(BASE)
($(base_inputs) && $(call measure,$(BASE_TREE),$(notdir $(BASE_RESULT)),0)) \
	|| (git worktree remove --force $(BASE_TREE) && false)
git worktree remove --force $(BASE_TREE)
endef

define compare
$(LOOP) compare $(BASE_RESULT) $(RESULT) > $(RESULT)-changes.txt
$(base_metrics)
$(GATE) summary $(RESULT) $(BASE_RESULT) $(BASE_METRICS) \
	--changes $(RESULT)-changes.txt >> $(SUMMARY)
endef

define same_graphs
diff -rq -x runs.json -x result.json $(RESULT) $(RESULT)-seed1
@echo "the graphs of hash seeds 0 and 1 are byte-identical"
endef

.PHONY: setup test lint check format eval-inputs eval-inputs-build eval eval-record eval-diff eval-determinism \
	eval-measure-pr eval-measure-seed1 eval-measure-base eval-gate eval-report eval-compare \
	eval-same-graphs eval-labels eval-changes

setup:
	uv sync --locked

test:
	$(RUN) pytest

lint:
	$(RUN) ruff check $(LINTED)
	$(RUN) ruff format --check $(LINTED)
	$(RUN) python tools/no_comments.py

check:
	$(RUN) python tools/check.py $(if $(FULL),--full) $(if $(BASE),--base $(BASE))

format:
	$(RUN) ruff check --select I --fix $(LINTED)
	$(RUN) ruff format $(LINTED)

eval-inputs-build:
	docker build --target macro -t pycg-eval-macro -f $(INPUTS) .
	docker build --target network -t pycg-eval-runner -f $(INPUTS) .

eval-inputs:
	@key=$$(python3 -I tools/inputs_key.py) && \
	if docker pull $(INPUTS_REGISTRY)/pycg-eval-macro:$$key \
		&& docker pull $(INPUTS_REGISTRY)/pycg-eval-runner:$$key; then \
		docker tag $(INPUTS_REGISTRY)/pycg-eval-macro:$$key pycg-eval-macro \
		&& docker tag $(INPUTS_REGISTRY)/pycg-eval-runner:$$key pycg-eval-runner \
		&& echo "eval-inputs: pulled the inputs images of key $$key from $(INPUTS_REGISTRY)"; \
	else \
		echo "eval-inputs: no inputs images of key $$key at $(INPUTS_REGISTRY): building them" \
		&& $(MAKE) --no-print-directory eval-inputs-build \
		&& echo "eval-inputs: built the inputs images of key $$key"; \
	fi
	rm -rf $(PROJECTS)
	mkdir $(PROJECTS)
	mkdir -p $(EVAL_OUT)
	docker run --rm --network none --user $$(id -u):$$(id -g) \
		-v $(CURDIR)/$(PROJECTS):/out pycg-eval-macro \
		cp -RP /inputs/macro-benchmark/projects/. /out/

eval: eval-inputs
	$(call measure,$(CURDIR),$(notdir $(RESULT)),0)
	$(report)

eval-record: eval-inputs
	$(measured)
	$(GATE) record $(RESULT) $(CURDIR)/$(METRICS) > $(EVAL_OUT)/metrics-$(COMMIT).json
	cp $(EVAL_OUT)/metrics-$(COMMIT).json $(METRICS)

eval-diff: eval-inputs
	$(need_base)
	$(measured)
	$(measure_base)
	$(compare)

eval-determinism: eval-inputs
	$(measured)
	$(call measure,$(CURDIR),$(notdir $(RESULT))-seed1,1)
	$(same_graphs)

eval-measure-pr: eval-inputs
	$(call measure,$(CURDIR),$(notdir $(RESULT)),0)

eval-measure-seed1: eval-inputs
	$(call measure,$(CURDIR),$(notdir $(RESULT))-seed1,1)

eval-measure-base: eval-inputs
	$(need_base)
	$(measure_base)

eval-gate: eval-inputs
	$(need_base)
	$(gate)

eval-report: eval-inputs
	$(report)

eval-compare: eval-inputs
	$(need_base)
	$(compare)

eval-same-graphs:
	$(same_graphs)

eval-labels: eval-inputs
	$(need_base)
	git diff --no-renames --name-only $(BASE) HEAD > $(EVAL_OUT)/changed-$(COMMIT).txt
	$(LABELER) $(RESULT)/result.json $(BASE_RESULT)/result.json \
		$(EVAL_OUT)/changed-$(COMMIT).txt $(EVAL_OUT)/labels-$(COMMIT).txt >> $(SUMMARY)
	cat $(EVAL_OUT)/labels-$(COMMIT).txt >> $(LABELS)

eval-changes:
	$(need_base)
	python3 -I tools/check.py --base $(BASE) --detect-eval $(OUTPUTS) >> $(SUMMARY)
