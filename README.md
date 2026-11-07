# BLUFF.EXE

A local human-versus-AI dice bluffing game for an IEEE exhibition. Both players have five dice throughout the match. A raise must increase the **quantity**; the face may change. Challenge a claim to reveal both hands. The round winner earns one point, and the first to five wins. The C++20 engine owns all rolls, legal actions, scores, and results.

## Run locally

Requires CMake with C++20 support, Python 3.12, Node 24, npm, and about 2 GiB free disk. macOS uses Xcode Command Line Tools; Linux needs a C++20 compiler and CMake. No account, cloud service, paid API, camera, or microphone is required.

```sh
make setup
make dev
```

Open `http://127.0.0.1:3000`. The API listens at `http://127.0.0.1:8787`. For a production build, use `make build` then `make kiosk`.

## Play

Each round rolls five dice per player. Only your dice are visible until a challenge. A bid such as `3 × 4` claims that at least three of the ten dice show 4. The opener may make any bid; later bids must claim more dice and may choose any face. At quantity 10, the responder must challenge. The challenged round winner scores one point. Select Next Round for fresh dice; the prior round loser opens. Play Again creates a new match.

The interface provides keyboard controls, reduced-motion support, public claim history, and a 2D fallback for missing WebGL.

## Agents and evidence

The playable opponents are random, probability, and aggressive C++ heuristics. The earlier one-die CFR checkpoint used incompatible rules and is retired. No trained policy or champion is claimed for the current ruleset. The current baseline tournament records every match and decision under `experiments/runs/`; see [the evidence report](docs/FINAL_REPORT.md) for completed results and limitations.

Run `make test` for engine/API tests, `make verify` for lint, type checks, and the production build, `make tournament RUN_ID=name PER_SEAT=1000 N=5` for a current-ruleset baseline, and `make export-results` for CSV/JSONL/SVG exports. `make train-exhibit` currently exits with an explicit unsupported status; it does not create a fictitious model.

## Documentation

[Rules](docs/RULES.md) · [Architecture](docs/ARCHITECTURE.md) · [API](docs/API.md) · [Research methods](docs/RESEARCH_METHODS.md) · [Design system](docs/DESIGN_SYSTEM.md) · [Current state](docs/EXECUTION_STATE.md) · [Evidence](docs/FINAL_REPORT.md)
