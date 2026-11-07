# Execution state

Ruleset: `fixed5_score5_quantity_only_v1`. The user's fixed-five scoring specification superseded the earlier elimination rules.

Completed: local `main` bootstrap and `codex/bluff-exe` branch; C++ fixed-five engine, event replay, secure/seeded dice, quantity-only validation, random opener, score-to-five and explicit next round; three heuristic agents; loopback HTTP API with SQLite persistence, redaction, idempotency, invalid-attempt logging including malformed JSON, reconnect and deletion; Next.js 3D/2D UI; production kiosk; desktop/mobile screenshots; current 6,000-match baseline evaluation with raw records and exports; passing `make verify` after the final bid-selector reset.

Next executable tasks: design and train a fixed-five quantity-only CFR policy, evaluate against hard unseen opponents, and add adaptation only after that baseline is validated. The working branch `codex/bluff-exe` is pushed to origin; `main` is the bootstrap branch.

Known limits: no compatible CFR or adaptive policy, no hard-opponent champion, no prolonged kiosk stability result, no automated browser suite. Old runs and policy are preserved under legacy labels and excluded from the current API. Roughly 2.6 GiB free disk remained at last check. `make train-exhibit` exits rather than generating a false checkpoint.

Last successful commands: `make verify`; `make kiosk`; `python3.12 scripts/tournament.py --run-id fixed5_baseline_1000 --per-seat 1000 --n 5 --seed-offset 3000000`; `python3.12 scripts/export_results.py`. Evidence: `experiments/runs/fixed5_baseline_1000/`, `docs/fixed5-baseline-summary.json`, `docs/plots/fixed5-baseline.svg`, `docs/screenshots/`.
