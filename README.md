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

The interface uses crisp 2D dice without WebGL, keyboard controls, public claim history, and a responsive layout. After each completed human match, the Research tab offers a slide-by-slide replay of every round start, bid, challenge, reveal, next-round transition, and final result. Each slide shows both hands as post-match evidence, the public claim, score, exact count, the AI's fair-dice truth prior, and recorded policy choices when available. The AI's explanation of a human move is a labeled hypothesis based only on its own dice and public actions; the game cannot know the human's intent. Active matches never expose the private replay or AI hand.

## Agents and evidence

Five opponents are selectable: random, probability, aggressive, the wider sampled-CFR Apprentice, and a public-outcome adaptive candidate. Both trained policies use imperfect-recall one-round abstractions for these fixed-five rules; the Observer still uses the original frozen CFR policy as its base. The earlier one-die CFR checkpoint used incompatible rules and is retired. The adaptive candidate remains experimental; see [the evidence report](docs/FINAL_REPORT.md) for measured comparisons and limitations.

Run `make test` for engine, trainer, and API tests; `make verify` for lint, type checks, and the production build; `make tournament RUN_ID=name PER_SEAT=1000 N=5` for the baseline league; `make evaluate RUN_ID=name PER_SEAT=1000` for a paired-seed candidate league; `make research-index` to refresh the Research page's tracked evaluation summaries; and `make export-results` for CSV/JSONL/SVG exports. `make train-exhibit RUN_ID=name ITERATIONS=100000` trains the original fixed-five abstraction; `make train-exhibit-v2 RUN_ID=name ITERATIONS=100000` trains the wider action and two-bid-context candidate. `make resume` and `make resume-v2` continue their respective checkpoints. Both trainers use one CPU worker, checkpoints, a 1.5 GiB artifact cap, and a 2 GiB free-disk guard. `make train-small RUN_ID=name SMALL_ITERATIONS=2000` verifies CFR against an exact information-respecting best response in a quantity-only one-die **toy game**. The toy policy is never used in the fixed-five exhibition game. Training does not automatically replace the active policy.

## Documentation

[Rules](docs/RULES.md) · [Architecture](docs/ARCHITECTURE.md) · [API](docs/API.md) · [Research methods](docs/RESEARCH_METHODS.md) · [Design system](docs/DESIGN_SYSTEM.md) · [Game screenshot](docs/screenshots/bluff-v2-setup.png) · [Replay screenshot](docs/screenshots/bluff-replay-human.png) · [Raw v2 evaluations](evidence/fixed5-cfr-v2-confirm.zip) · [Current state](docs/EXECUTION_STATE.md) · [Evidence](docs/FINAL_REPORT.md)
