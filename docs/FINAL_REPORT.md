# BLUFF.EXE evidence report

## Rules and working build

The active ruleset is `fixed5_score5_quantity_only_v1`. Both players keep five dice. Only bid quantity may increase. Every challenged round awards one point; first to five wins. The prior dice-elimination and lexicographic-bid build, its screenshots, its evaluations, and its N=1 CFR checkpoint are retained under legacy paths and **do not validate this game**.

`make kiosk` was run locally on 7 November 2026. A real browser completed a five-round match against the C++ backend, showing a 0–5 final score, five dice per side throughout, public bids, true dice reveal, explicit Next Round, and disabled play controls at match end. The desktop and mobile screenshots in `docs/screenshots/` are from that running production build. No paid service was used.

## Current-rule evaluation

Run `fixed5_baseline_1000` completed on 7 November 2026 with engine SHA-256 `b4f0bb1e365b32650f0992d1d8cc0a987fa66dbf764c2850e266be9c15bad79f`, seeds beginning at 3,000,000, both seat orders, and 1,000 matches per seat for each baseline pairing. It ran on macOS arm64 from 17:29:10 to 17:33:47 UTC. All 6,000 match results, 36,004 round reveals, and 83,309 agent decisions were logged in SQLite. The logger recorded zero run errors. Decision latency including CLI process startup was mean 2.147 ms, p95 2.395 ms, maximum 114.544 ms. This is a local batch measurement, not a kiosk p95 under visitor load.

| First-named agent vs second | First-named wins as Human | First-named wins as AI |
| --- | ---: | ---: |
| Random vs Probability | 0/1000, 95% Wilson [0.0%, 0.38%] | 0/1000, [0.0%, 0.38%] |
| Random vs Aggressive | 582/1000, [55.12%, 61.22%] | 574/1000, [54.31%, 60.43%] |
| Probability vs Aggressive | 980/1000, [96.93%, 98.70%] | 977/1000, [96.57%, 98.46%] |

The probability heuristic leads this **three-agent baseline pool**. This league does not establish a champion against stronger unseen opponents or prove game-theoretic optimality. The complete summary and plot are in `docs/fixed5-baseline-summary.json` and `docs/plots/fixed5-baseline.svg`; raw SQLite, CSV, and JSONL records are in the local `experiments/runs/fixed5_baseline_1000/` directory and the deliverable evidence archive.

## Tests and limitations

`make verify` passed: C++ build, six engine tests, two HTTP tests, ESLint, TypeScript, and the patched Next.js production build. Tests cover quantity-only raises, forced challenge at quantity 10, random initial opener, fixed dice, scoring, public claims, redaction, replay, invalid attempts, duplicate requests, explicit next round, and deletion. The browser check covered start, maximum bid, forced AI challenge, reveal, Next Round, and match completion. Long-duration kiosk load and automated browser tests are still unrun.

No current-ruleset CFR or adaptive policy has been trained. The old N=1 exact policy had a different action vocabulary and payoff and is not loaded. `make train-exhibit` exits with an explicit unsupported status. There is no current CFR iteration count, exploitability result, or champion promotion. Fixed-five quantity-only CFR training, hard-opponent holdout evaluation, and adaptation robustness are the next research tasks. The frontend currently offers three genuine heuristic opponents and labels their methods accurately.

## Staff explanation

Visitors see five private dice and claim how many of the ten dice show one face. They can raise the number or challenge the AI's claim. The AI estimates odds from its own dice but cannot see the visitor's dice, so it can be wrong or bluff. A challenge reveals both hands and gives the round winner one point. First to five points wins. Game-theoretic and adaptive modes are withheld until they are trained and tested for these exact rules.
