# BLUFF.EXE

A local human-versus-AI dice bluffing game for an IEEE exhibition. Both players have five dice throughout the match. A raise must increase the **quantity**; the face may change. Challenge a claim to reveal both hands. The round winner earns one point, and the first to five wins. The C++20 engine owns all rolls, legal actions, scores, and results.

## Run locally

Requires CMake with C++20 support, Python 3.12, Node 24, npm, and about 2 GiB free disk. macOS uses Xcode Command Line Tools; Linux needs a C++20 compiler and CMake. No account, cloud service, paid API, camera, or microphone is required.

```sh
make setup
make dev
```

Open `http://127.0.0.1:3000`. The API listens at `http://127.0.0.1:8787`. For a production kiosk, use `make kiosk`; it builds both components before starting them.

## Play

Each round rolls five dice per player. Only your dice are visible until a challenge. A bid such as `3 × 4` claims that at least three of the ten dice show 4. The opener may make any bid; later bids must claim more dice and may choose any face. At quantity 10, the responder must challenge. The challenged round winner scores one point. Select Next Round for fresh dice; the prior round loser opens. Play Again creates a new match.

The interface provides keyboard controls, reduced-motion support, public claim history, and a 2D fallback for missing WebGL.

## Agents and evidence

Five opponents are selectable: random, probability, aggressive, a trained sampled-CFR champion, and a public-outcome adaptive candidate. The trained policy uses an imperfect-recall one-round abstraction for these fixed-five rules. It is the strongest measured option in the local confirmatory league, not a full-game equilibrium. The earlier one-die CFR checkpoint used incompatible rules and is retired. The adaptive candidate remains experimental; see [the evidence report](docs/FINAL_REPORT.md).

Run `make test` for engine, trainer, and API tests; `make verify` for lint, type checks, and the production build; `make tournament RUN_ID=name PER_SEAT=1000 N=5` for the baseline league; `make evaluate RUN_ID=name PER_SEAT=1000` for a paired-seed candidate league; and `make export-results` for CSV/JSONL/SVG exports. `make train-exhibit RUN_ID=name ITERATIONS=100000` trains a new fixed-five candidate with one CPU worker, checkpoints, a 1.5 GiB artifact cap, and a 2 GiB free-disk guard. `make resume RUN_ID=name ITERATIONS=100000` resumes a checkpoint. `make train-small RUN_ID=name SMALL_ITERATIONS=2000` verifies CFR against an exact information-respecting best response in a quantity-only one-die **toy game**. The toy policy is never used in the fixed-five exhibition game. Training does not automatically replace the active policy.

## Documentation

[Rules](docs/RULES.md) · [Architecture](docs/ARCHITECTURE.md) · [API](docs/API.md) · [Research methods](docs/RESEARCH_METHODS.md) · [Design system](docs/DESIGN_SYSTEM.md) · [Current state](docs/EXECUTION_STATE.md) · [Evidence](docs/FINAL_REPORT.md)
