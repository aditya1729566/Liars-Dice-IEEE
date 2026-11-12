# BLUFF.EXE

A human-versus-AI dice bluffing game for an IEEE exhibition, playable in a browser or locally. Both players have five dice throughout the match. A raise must increase the **quantity**; the face may change. Challenge a claim to reveal both hands. The round winner earns one point, and the first to five wins. The C++20 engine owns all rolls, legal actions, scores, and results.

## Play online

[Open BLUFF.EXE](https://liarsdice5.vercel.app). The deployed game uses the same C++ rules engine and stores matches in private Vercel Blob storage. The Research tab gives a complete replay after a match ends. Repository changes to MCCFR v1 and v2 are not deployed until a production release. See [deployment notes](docs/vercel-deployment.md) for the runtime and storage design.

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

Seven opponents are selectable in the hosted game: random, probability, aggressive, the wider sampled-CFR Apprentice, the external-sampling MCCFR Monte Carlo, the separately versioned Monte Carlo II, and a public-outcome adaptive candidate. A separately selectable ReBeL Transfer is also available in the local game after `make setup-rebel`; its original checkpoint was trained under different rules and the hosted Node runtime does not contain its PyTorch dependency. Monte Carlo II uses a wider bid menu, more public bidding context, learned policy backoff, and a depth-limited first-to-five match target. It remains an imperfect-recall approximation; no full-match equilibrium is claimed. The Monte Carlo II is the local default after its 30,000-match held-out confirmation; the Apprentice remains selectable. The Observer still uses the original frozen CFR policy as its base. The earlier one-die CFR checkpoint used incompatible rules and is retired. See [MCCFR v2 results](docs/MCCFR_V2_RESULTS.md), [ReBeL transfer results](docs/REBEL_TRANSFER_RESULTS.md), [MCCFR v1 results](docs/MCCFR_RESULTS.md), and [the prior evidence report](docs/FINAL_REPORT.md) for measured comparisons and limitations.

Run `make test` for engine, trainer, and API tests; `make verify` for lint, type checks, and the production build; `make tournament RUN_ID=name PER_SEAT=1000 N=5` for the baseline league; `make evaluate RUN_ID=name PER_SEAT=1000` for a paired-seed candidate league; `make evaluate-mccfr-v2 RUN_ID=name PER_SEAT=1000` for the separately logged v2 league; `make research-index` to refresh the Research page's tracked evaluation summaries; and `make export-results` for CSV/JSONL/SVG exports. `make train-exhibit RUN_ID=name ITERATIONS=100000` trains the original fixed-five abstraction; `make train-exhibit-v2 RUN_ID=name ITERATIONS=100000` trains the wider action and two-bid-context candidate. `make train-mccfr RUN_ID=name ITERATIONS=1000000 SEED=20261112 MCCFR_MILESTONES=10000,100000,500000,1000000` trains MCCFR v1; `make train-mccfr-v2 RUN_ID=name ITERATIONS=1000000 SEED=20261112` trains v2 with the recorded continuation estimate. `make resume` and `make resume-v2` continue the original CFR checkpoints; use the `--resume` option of either MCCFR trainer for its checkpoint. All MCCFR training uses one CPU worker, checkpoints, a 1.5 GiB artifact cap, and a 2 GiB free-disk guard. `make train-small RUN_ID=name SMALL_ITERATIONS=2000` verifies CFR against an exact information-respecting best response in a quantity-only one-die **toy game**. Both MCCFR trainers have independently checked toy modes. Toy policies are never used in the fixed-five exhibition game. Training does not automatically replace the active policy.

For the local ReBeL Transfer, run `make setup-rebel`, `make test-rebel`, and `make dev`. Its source and checkpoint are fetched at a pinned commit into the ignored `.cache` directory and checked before use. `make evaluate-rebel RUN_ID=name PER_SEAT=100 SEED_OFFSET=9400000` evaluates it against every other engine opponent with both seats and paired seeds. The hosted Vercel game does not include this local PyTorch runtime.

## Documentation

[Rules](docs/RULES.md) · [Architecture](docs/ARCHITECTURE.md) · [API](docs/API.md) · [Research methods](docs/RESEARCH_METHODS.md) · [MCCFR v2 results](docs/MCCFR_V2_RESULTS.md) · [ReBeL transfer results](docs/REBEL_TRANSFER_RESULTS.md) · [MCCFR v1 results](docs/MCCFR_RESULTS.md) · [Design system](docs/DESIGN_SYSTEM.md) · [Live game screenshot](docs/screenshots/live-production-reveal.png) · [MCCFR v2 replay screenshot](docs/screenshots/mccfr-v2-replay-20261112.png) · [Final v2 match evidence](evidence/mccfr-v2-final-20261112.zip) · [Current state](docs/EXECUTION_STATE.md) · [Prior evidence](docs/FINAL_REPORT.md)
