PYTHON ?= python3.12
RUN_ID ?= manual_$(shell date -u +%Y%m%dT%H%M%SZ)
PER_SEAT ?= 1000
N ?= 5
.PHONY: setup build-engine dev kiosk test verify train-small train-exhibit resume tournament evaluate export-results build
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
kiosk: build-engine
	@$(PYTHON) server/app.py & api_pid=$$!; trap 'kill $$api_pid 2>/dev/null || true' EXIT INT TERM; npm --prefix web run start
test: build-engine
	$(PYTHON) -m unittest discover -s engine/tests -v
	$(PYTHON) -m unittest discover -s server/tests -v
verify: test
	npm --prefix web run lint
	npm --prefix web run typecheck
	npm --prefix web run build
train-small:
	@echo 'Legacy N=1 CFR trainer is incompatible with fixed-five rules.' >&2; exit 2
train-exhibit:
	@echo 'Fixed-five CFR training is not yet implemented; no policy was created.' >&2; exit 2
resume:
	@echo 'No current-ruleset CFR checkpoint can be resumed.' >&2; exit 2
tournament: build-engine
	$(PYTHON) scripts/tournament.py --run-id $(RUN_ID) --per-seat $(PER_SEAT) --n $(N)
evaluate: build-engine
	$(PYTHON) scripts/tournament.py --run-id $(RUN_ID) --per-seat $(PER_SEAT) --n $(N) --agents probability aggressive conservative high_call always_call
export-results:
	$(PYTHON) scripts/export_results.py
build: build-engine
	npm --prefix web run build
