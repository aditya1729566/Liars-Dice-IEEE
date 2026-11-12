PYTHON ?= python3.12
RUN_ID ?= manual_$(shell date -u +%Y%m%dT%H%M%SZ)
PER_SEAT ?= 1000
N ?= 5
ITERATIONS ?= 100000
MCCFR_MILESTONES ?= 10000,100000
MCCFR_V2_MILESTONES ?= $(ITERATIONS)
SMALL_ITERATIONS ?= 100
SEED ?= 1729
SEED_OFFSET ?= 7000000
EVAL_AGENTS ?= cfr2 probability conservative high_call
.PHONY: setup setup-rebel build-engine dev kiosk test test-rebel verify train-small train-exhibit train-exhibit-v2 train-mccfr train-mccfr-v2 resume resume-v2 tournament evaluate evaluate-mccfr evaluate-mccfr-v2 evaluate-rebel export-results research-index build
setup:
	@$(PYTHON) --version
	@cmake --version | head -1
	@node --version
	npm install --prefix web --no-audit --no-fund
	cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
setup-rebel:
	$(PYTHON) scripts/setup_rebel.py
build-engine:
	cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
	cmake --build build -j2
dev: build-engine
	@$(PYTHON) server/app.py & api_pid=$$!; trap 'kill $$api_pid 2>/dev/null || true' EXIT INT TERM; LOCAL_API_PROXY=1 npm --prefix web run dev
kiosk: build-engine
	LOCAL_API_PROXY=1 npm --prefix web run build
	@$(PYTHON) server/app.py & api_pid=$$!; trap 'kill $$api_pid 2>/dev/null || true' EXIT INT TERM; LOCAL_API_PROXY=1 npm --prefix web run start
test: build-engine
	$(PYTHON) -m unittest discover -s engine/tests -v
	$(PYTHON) -m unittest discover -s trainer -p 'test_*.py' -v
	$(PYTHON) -m unittest discover -s server/tests -v
test-rebel:
	.cache/rebel-venv/bin/python -m unittest discover -s scripts -p 'test_rebel_bridge.py' -v
verify: test
	npm --prefix web run lint
	npm --prefix web run typecheck
	npm --prefix web run build
train-small:
	$(PYTHON) trainer/train_small.py --iterations $(SMALL_ITERATIONS) --run-id $(RUN_ID)
train-exhibit: build-engine
	$(PYTHON) trainer/train_exhibit.py --n 5 --iterations $(ITERATIONS) --seed $(SEED) --run-id $(RUN_ID)
train-exhibit-v2: build-engine
	$(PYTHON) trainer/train_exhibit_v2.py --n 5 --iterations $(ITERATIONS) --seed $(SEED) --run-id $(RUN_ID)
train-mccfr: build-engine
	./build/mccfr_trainer --iterations $(ITERATIONS) --seed $(SEED) --run-id $(RUN_ID) --milestones $(MCCFR_MILESTONES) --git-commit $$(git rev-parse HEAD)
train-mccfr-v2: build-engine
	./build/mccfr_v2_trainer --iterations $(ITERATIONS) --seed $(SEED) --run-id $(RUN_ID) --milestones $(MCCFR_V2_MILESTONES) --continuation docs/mccfr_v2_continuation.json --git-commit $$(git rev-parse HEAD)
resume:
	$(PYTHON) trainer/train_exhibit.py --n 5 --iterations $(ITERATIONS) --seed $(SEED) --run-id $(RUN_ID) --resume
resume-v2:
	$(PYTHON) trainer/train_exhibit_v2.py --n 5 --iterations $(ITERATIONS) --seed $(SEED) --run-id $(RUN_ID) --resume
tournament: build-engine
	$(PYTHON) scripts/tournament.py --run-id $(RUN_ID) --per-seat $(PER_SEAT) --n $(N)
evaluate: build-engine
	$(PYTHON) scripts/tournament.py --run-id $(RUN_ID) --per-seat $(PER_SEAT) --n $(N) --seed-offset $(SEED_OFFSET) --paired-seeds --agents $(EVAL_AGENTS)
evaluate-mccfr: build-engine
	$(PYTHON) scripts/tournament.py --run-id $(RUN_ID) --per-seat $(PER_SEAT) --n 5 --seed-offset $(SEED_OFFSET) --paired-seeds --agents mccfr_external_v1 cfr2 cfr probability aggressive conservative truthful adaptive --focus mccfr_external_v1
evaluate-mccfr-v2: build-engine
	$(PYTHON) scripts/tournament.py --run-id $(RUN_ID) --per-seat $(PER_SEAT) --n 5 --seed-offset $(SEED_OFFSET) --paired-seeds --stream-engine --agents mccfr_external_v2 mccfr_external_v1 cfr2 cfr random probability aggressive conservative truthful adaptive --focus mccfr_external_v2
	$(PYTHON) scripts/mccfr_v2_metrics.py $(RUN_ID)
evaluate-rebel: build-engine
	.cache/rebel-venv/bin/python scripts/tournament.py --run-id $(RUN_ID) --per-seat $(PER_SEAT) --n 5 --seed-offset $(SEED_OFFSET) --paired-seeds --stream-engine --agents rebel_transfer_v1 mccfr_external_v2 mccfr_external_v1 cfr2 cfr adaptive random probability aggressive conservative truthful high_call always_call switcher --focus rebel_transfer_v1
	$(PYTHON) scripts/mccfr_v2_metrics.py $(RUN_ID) --agent rebel_transfer_v1
export-results:
	$(PYTHON) scripts/export_results.py
research-index:
	$(PYTHON) scripts/build_research_index.py
build: build-engine
	npm --prefix web run build
