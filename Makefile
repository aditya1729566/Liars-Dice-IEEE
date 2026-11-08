PYTHON ?= python3.12
RUN_ID ?= manual_$(shell date -u +%Y%m%dT%H%M%SZ)
PER_SEAT ?= 1000
N ?= 5
ITERATIONS ?= 100000
SMALL_ITERATIONS ?= 100
SEED ?= 1729
SEED_OFFSET ?= 7000000
EVAL_AGENTS ?= cfr2 probability conservative high_call
.PHONY: setup build-engine dev kiosk test verify train-small train-exhibit train-exhibit-v2 resume resume-v2 tournament evaluate export-results research-index build
setup:
	@$(PYTHON) --version
	@cmake --version | head -1
	@node --version
	npm install --prefix web --no-audit --no-fund
	cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
build-engine:
	cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
	cmake --build build -j2
dev: build-engine
	@$(PYTHON) server/app.py & api_pid=$$!; trap 'kill $$api_pid 2>/dev/null || true' EXIT INT TERM; npm --prefix web run dev
kiosk: build
	@$(PYTHON) server/app.py & api_pid=$$!; trap 'kill $$api_pid 2>/dev/null || true' EXIT INT TERM; npm --prefix web run start
test: build-engine
	$(PYTHON) -m unittest discover -s engine/tests -v
	$(PYTHON) -m unittest discover -s trainer -p 'test_*.py' -v
	$(PYTHON) -m unittest discover -s server/tests -v
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
resume:
	$(PYTHON) trainer/train_exhibit.py --n 5 --iterations $(ITERATIONS) --seed $(SEED) --run-id $(RUN_ID) --resume
resume-v2:
	$(PYTHON) trainer/train_exhibit_v2.py --n 5 --iterations $(ITERATIONS) --seed $(SEED) --run-id $(RUN_ID) --resume
tournament: build-engine
	$(PYTHON) scripts/tournament.py --run-id $(RUN_ID) --per-seat $(PER_SEAT) --n $(N)
evaluate: build-engine
	$(PYTHON) scripts/tournament.py --run-id $(RUN_ID) --per-seat $(PER_SEAT) --n $(N) --seed-offset $(SEED_OFFSET) --paired-seeds --agents $(EVAL_AGENTS)
export-results:
	$(PYTHON) scripts/export_results.py
research-index:
	$(PYTHON) scripts/build_research_index.py
build: build-engine
	npm --prefix web run build
