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
SCALE_CONTAINER_MIB = $(shell python3 -I evaluation/scale/measure.py container-mib $(SCALE_MEMORY_MIB))
SCALE_SANDBOX = $(call sandbox,$(SCALE_CONTAINER_MIB)m)
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
PARITY_ORACLE = $(EVAL_OUT)/parity-oracle-$(shell $(parity_key))
PARITY_RUST = $(EVAL_OUT)/parity-rust-$(COMMIT)
PARITY_REQUIRED = tools/parity/required.txt
PARITY_ENGINE = tools/parity/engine.txt
PARITY_BINARIES = $(or $(CARGO_TARGET_DIR),$(CURDIR)/target)/release

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

define parity_d1
(cd $(1) && find . -name modules.tsv) | sort | while read -r modules; do \
	input=$$(dirname "$$modules"); \
	mkdir -p $(2)/$$input && \
	$(PARITY_BINARIES)/pycg_dump d1 $(1)/$$modules $(2)/$$input/D1.jsonl \
		|| { echo "parity: pycg_dump d1 $(1)/$$modules failed on $$input" >&2; exit 1; }; \
done
endef

define parity_compare
python3 -I tools/parity/compare.py $(1) $(2) $(or $(4),--required $(PARITY_REQUIRED)) > $(3); \
status=$$?; \
{ echo '```'; cat $(3); echo '```'; } >> $(SUMMARY); \
sed -n 's/^  \([^:]*\): different: \(.*\)$$/\1 \2/p' $(3) | while read -r input dumps; do \
	for dump in $$(echo "$$dumps" | tr ',' ' '); do \
		{ echo "$$input $$dump:"; echo '```'; \
		python3 -I tools/parity/diff.py $(1) $(2) "$$input" "$$dump"; echo '```'; } >> $(SUMMARY); \
	done; \
done; \
exit $$status
endef

define same_graphs
diff -rq -x runs.json -x result.json $(RESULT) $(RESULT)-seed1
@echo "the graphs of hash seeds 0 and 1 are byte-identical"
endef

.PHONY: setup test lint check format eval-inputs eval-inputs-build eval eval-record eval-diff eval-determinism \
	eval-measure-pr eval-measure-seed1 eval-measure-base eval-gate eval-report eval-compare \
	eval-same-graphs eval-labels eval-changes eval-scale parity-oracle parity-key parity

setup:
	uv sync --locked

test:
	$(RUN) python tools/test.py

lint:
	$(RUN) ruff check $(LINTED)
	$(RUN) ruff format --check $(LINTED)
	$(RUN) python tools/no_comments.py
	$(RUN) python tools/sdist_check.py

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
	@copy=$(EVAL_OUT)/inputs-$$(python3 -I tools/inputs_key.py) && \
	if [ -f $$copy/done ]; then echo "eval-inputs: the sources are copied in $$copy"; \
	else partial=$$copy.partial-$$$$ && mkdir -p $$partial/macro $$partial/scale && \
		docker run --rm --network none --user $$(id -u):$$(id -g) \
			-v $$partial/macro:/out -v $$partial/scale:/scale \
			pycg-eval-macro sh -c \
			'cp -RP /inputs/macro-benchmark/projects/. /out/ && cp -RP /inputs/scale/projects/. /scale/' && \
		touch $$partial/done && chmod -R a-w $$partial && \
		{ mv -T $$partial $$copy 2> /dev/null || { chmod -R u+w $$partial && rm -rf $$partial; }; } && \
		test -f $$copy/done && echo "eval-inputs: copied the sources to $$copy"; fi && \
	rm -rf $(PROJECTS) $(SCALE_PROJECTS) && mkdir $(PROJECTS) $(SCALE_PROJECTS) && \
	for source in $$copy/macro/* $$copy/scale/*; do \
		case $$source in $$copy/macro/*) into=$(PROJECTS);; *) into=$(SCALE_PROJECTS);; esac; \
		ln -s $$source $$into/ || exit 1; \
	done

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

parity-key:
	@$(parity_key)

parity:
	@test -d $(PARITY_ORACLE)/seed-0 || \
		(echo "parity: no oracle output at $(PARITY_ORACLE): run make parity-oracle" >&2 && false)
	cargo build --release --locked
	rm -rf $(PARITY_RUST)
	mkdir -p $(PARITY_RUST)/run-1 $(PARITY_RUST)/run-2
	@$(call parity_d1,$(PARITY_ORACLE)/seed-0,$(PARITY_RUST)/run-1)
	@$(call parity_d1,$(PARITY_ORACLE)/seed-0,$(PARITY_RUST)/run-2)
	@cd $(PARITY_ORACLE)/seed-0 && find . -name D2.jsonl | sort | while read -r dump; do \
		input=$$(dirname "$$dump"); \
		for run in run-1 run-2; do \
			mkdir -p $(PARITY_RUST)/$$run/$$input && \
			$(PARITY_BINARIES)/pycg_dump stubs "$$dump" \
				> $(PARITY_RUST)/$$run/$$input/D2.jsonl \
				|| { echo "parity: pycg_dump stubs $$dump failed on $$input" >&2; exit 1; }; \
		done; \
	done
	@cd $(PARITY_ORACLE)/seed-0 && find . -name D3.jsonl | sort | while read -r dump; do \
		input=$$(dirname "$$dump"); \
		for run in run-1 run-2; do \
			out=$(PARITY_RUST)/$$run/$$input && mkdir -p $$out && \
			if $(PARITY_BINARIES)/pycg_dump solver "$$dump" > $$out/D3.jsonl 2> $$out/replay.txt; \
			then rm $$out/replay.txt; else mv $$out/replay.txt $$out/error.txt; fi; \
		done; \
	done
	@cd $(PARITY_ORACLE)/seed-0 && find . -name D4.jsonl | sort | while read -r dump; do \
		input=$$(dirname "$$dump"); \
		out=$(PARITY_RUST)/engine/$$input && mkdir -p $$out && \
		if $(PARITY_BINARIES)/pycg_dump engine "$$dump" $$out 2> $$out/replay.txt; \
		then rm $$out/replay.txt; else mv $$out/replay.txt $$out/error.txt; fi; \
	done
	@$(call parity_compare,$(PARITY_ORACLE)/seed-0,$(PARITY_RUST)/run-1,$(PARITY_RUST)/oracle-run-1.txt)
	@$(call parity_compare,$(PARITY_ORACLE)/seed-0,$(PARITY_RUST)/run-2,$(PARITY_RUST)/oracle-run-2.txt)
	@$(call parity_compare,$(PARITY_ORACLE)/seed-0,$(PARITY_RUST)/engine,$(PARITY_RUST)/oracle-engine-all.txt,--dumps D3 D5)
	@$(call parity_compare,$(PARITY_ORACLE)/seed-0,$(PARITY_RUST)/engine,$(PARITY_RUST)/oracle-engine.txt,--dumps D3 D5 --inputs $(PARITY_ENGINE))
	@cd $(PARITY_ORACLE)/seed-0 && find . -name D6in.json | sort | while read -r inputs; do \
		input=$$(dirname "$$inputs"); \
		out=$(PARITY_RUST)/document/$$input && mkdir -p $$out && \
		(cd $(CURDIR) && $(PARITY_BINARIES)/pycg_dump document-build \
			$(PARITY_ORACLE)/seed-0/$$input $$out 2> $$out/build.txt) \
		|| mv $$out/build.txt $$out/error.txt; \
	done
	@$(call parity_compare,$(PARITY_ORACLE)/seed-0,$(PARITY_RUST)/document,$(PARITY_RUST)/oracle-document.txt,--dumps D6)
	@$(PARITY_BINARIES)/pycg_dump document $(PARITY_ORACLE)/seed-0 > $(PARITY_RUST)/writer.txt; \
	status=$$?; { echo '```'; cat $(PARITY_RUST)/writer.txt; echo '```'; } >> $(SUMMARY); \
	exit $$status
