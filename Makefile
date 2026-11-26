RUN := uv run --locked
LINTED := pycg tests tools evaluation
INPUTS := evaluation/container/Dockerfile.inputs
INPUTS_REGISTRY := ghcr.io/vitsalis
PROJECTS := evaluation/macro-benchmark/projects
SCALE_PROJECTS := evaluation/scale/projects
SCALE_MEMORY_MIB ?= 4096
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
sandbox = docker run --rm --network none --read-only --tmpfs /tmp \
	--memory $(1) --memory-swap $(1) --cap-drop ALL \
	--security-opt no-new-privileges --user $$(id -u):$$(id -g) \
	-e HOME=/tmp -e PYTHONHASHSEED=0 \
	-v $(CURDIR):$(CURDIR):ro -v $(GIT_COMMON):$(GIT_COMMON):ro \
	-v $(EVAL_OUT):$(EVAL_OUT) pycg-eval-runner python3 -I
SANDBOX = $(call sandbox,6g)
SCALE_SANDBOX = $(call sandbox,$(SCALE_MEMORY_MIB)m)
SCALE_MEASURE = $(CURDIR)/evaluation/scale/measure.py
SCALE_RESULT = $(EVAL_OUT)/scale-$(COMMIT)
SCALE_BASE_RESULT = $(EVAL_OUT)/scale-base-$(BASE_COMMIT)-for-$(COMMIT)
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
need_name = $(if $(NAME),,$(error $@ needs NAME=<package of evaluation/scale/projects.toml>))
measure_scale = $(SCALE_SANDBOX) $(SCALE_MEASURE) run --checkout $(1) --name $(notdir $(2)) \
	--package $(NAME) --out $(EVAL_OUT) --memory-mib $(SCALE_MEMORY_MIB)
scale_record = $(1)/scale/$(NAME).record.json
PARITY_SETS ?= micro macro
PARITY_DUMP = $(CURDIR)/tools/parity/dump.py
PARITY_KEYED = pycg tools/parity evaluation/micro-benchmark/snippets evaluation/common/run.py
parity_key = python3 -I tools/parity/dump.py key --checkout $(CURDIR)

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

define measure_scale_base
git worktree add --detach $(BASE_TREE) $(BASE)
$(call measure_scale,$(BASE_TREE),$(SCALE_BASE_RESULT)) \
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
	eval-same-graphs eval-labels eval-changes eval-scale parity-oracle

setup:
	uv sync --locked

test:
	$(RUN) python tools/test.py

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
	rm -rf $(PROJECTS) $(SCALE_PROJECTS)
	mkdir $(PROJECTS) $(SCALE_PROJECTS)
	mkdir -p $(EVAL_OUT)
	docker run --rm --network none --user $$(id -u):$$(id -g) \
		-v $(CURDIR)/$(PROJECTS):/out -v $(CURDIR)/$(SCALE_PROJECTS):/scale \
		pycg-eval-macro sh -c \
		'cp -RP /inputs/macro-benchmark/projects/. /out/ && cp -RP /inputs/scale/projects/. /scale/'

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

eval-scale: eval-inputs
	$(need_name)
	$(if $(BASE),$(measure_scale_base))
	$(call measure_scale,$(CURDIR),$(SCALE_RESULT))
	$(if $(BASE),$(SCALE_SANDBOX) $(SCALE_MEASURE) compare \
		$(call scale_record,$(SCALE_BASE_RESULT)) $(call scale_record,$(SCALE_RESULT)))

eval-changes:
	$(need_base)
	python3 -I tools/check.py --base $(BASE) --detect-eval $(OUTPUTS) >> $(SUMMARY)

parity-oracle: eval-inputs
	@test -z "$$(git status --porcelain -- $(PARITY_KEYED))" \
		|| (echo "parity-oracle: commit $(PARITY_KEYED) first" && false)
	@out=$(EVAL_OUT)/parity-oracle-$$($(parity_key)) && mkdir -p $$out && \
	for set in $(PARITY_SETS); do \
		if [ -f $$out/done-$$set ]; then echo "parity-oracle: $$set is cached in $$out"; \
		else $(SANDBOX) $(PARITY_DUMP) oracle --checkout $(CURDIR) --out $$out \
			--set $$set --jobs $(EVAL_JOBS) && touch $$out/done-$$set || exit 1; fi; \
	done && echo "parity-oracle: $$out"
