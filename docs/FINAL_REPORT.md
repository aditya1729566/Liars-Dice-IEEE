# BLUFF.EXE evidence report

## Working game

The active ruleset is `fixed5_score5_quantity_only_v1`. Both players keep five dice, a raise must strictly increase quantity, every challenge awards exactly one point, and the first to five wins. The C++20 engine alone rolls dice, validates actions, and resolves outcomes. The loopback API persists private state, returns redacted views, records invalid attempts, and enforces versioned idempotent requests. The prior dice-elimination and lexicographic-bid runs and N=1 policy use different rules; they are excluded from all current-rule claims.

The supplied game-logic attachment ends midway through section 14. Sections 0–13, which fully define the playable rules and state transitions, were implemented; no claims are made about the missing tail.

A real browser completed a five-round match against the production C++ backend, including public bids, a reveal, explicit Next Round, and a 0–5 final score. A later browser check selected the current trained candidate, saw its public opening bid, and verified that the AI dice remained concealed. Desktop, mobile, trained-play, and five-agent-selector screenshots are in `docs/screenshots/`. No paid service was used.

## Agents and training

The five selectable agents are random, probability, aggressive, sampled CFR, and adaptive. The probability heuristic computes an exact binomial prior for the five unseen dice; it does not infer a strategic posterior. The sampled-CFR candidate was trained on the current fixed-five ruleset for 100,000 external-sampling iterations (seed 1729). The run completed in 14.33 seconds with 3,249 visited information sets and saved a checkpoint, manifest, and policy with SHA-256 `9054a212e2865189ee9358e344e3fba48298408edb96fbf8cc343e75d005b977`.

This policy uses an **imperfect-recall, one-round action abstraction**: an opening claim at quantity 1, then quantity +1 with the current or private modal face, or challenge. It falls back to the probability heuristic when an information set or legal action is unavailable. It is neither an exact solution nor a claim of full-match Nash play. The adaptive candidate uses only public past bids and revealed outcomes to adjust a bounded fraction of its decisions; it falls back to the frozen sampled policy. It has not been separately trained.

As a separate solver check, the quantity-only **one-die toy** enumerated all 36 deals and full histories. After 2,000 tabular CFR iterations, an independent information-set-respecting best response measured NashConv 0.0017316113 (sum of the two best-response utilities). The measured curve fell from 0.3463 at 10 iterations to 0.0017 at 2,000; see `docs/plots/quantity-n1-convergence.svg` and its run IDs in `docs/quantity-n1-curve.json`. This is an exact measurement for the toy, not an exploitability bound for the fixed-five game.

## Measured evaluations

All current evaluations used the same compiled engine and recorded each match, decision, observation, action, latency, and round reveal in SQLite. Each matchup was run in both seat orders with deterministic held-out seeds. Policy and engine SHA-256 values are frozen in the manifests. Wilson intervals are 95%; latency includes a fresh engine CLI process. No sampled agent made an illegal move in the completed runs or tests.

| Run | Scope | Matches | Decisions | Reveals | Errors |
| --- | --- | ---: | ---: | ---: | ---: |
| `fixed5_baseline_1000` | random, probability, aggressive; 1,000 per seat | 6,000 | 83,309 | 36,004 | 0 |
| `fixed5_five_agent_holdout_200` | five selectable agents; 200 per seat | 4,000 | 74,709 | 24,815 | 0 |
| `fixed5_hard_holdout_200` | probability, CFR, adaptive, conservative, high-call, always-call; 200 per seat | 6,000 | 136,422 | 40,077 | 0 |
| `fixed5_confirmatory_1000` | CFR, probability, conservative, high-call; paired seeds, 1,000 per seat | 12,000 | 292,730 | 82,429 | 0 |

The initial three-agent baseline favored probability: it beat aggressive 980/1,000 as Human and 977/1,000 as AI, while random beat probability 0/1,000 in either seat. Baseline mean decision latency was 2.147 ms and p95 was 2.395 ms.

The five-agent screen measured CFR beating probability **308/400 (77.0%, Wilson 72.6–80.9%)**. In the separate hard-opponent run, CFR beat probability **301/400 (75.3%, 70.8–79.2%)**, conservative **293/400 (73.3%, 68.7–77.4%)**, high-call **322/400 (80.5%, 76.3–84.1%)**, and always-call **391/400 (97.8%, 95.8–98.8%)**. These CFR pairings remain valid because the frozen CFR action code is unchanged. Adaptive rows in both historical runs are retained in the raw records but **not used for promotion**: the seat-swapped adaptive model counted its own revealed bids in the Human seat, and its original threshold adjustment had no effect at the discrete five-dice prior values. The adaptive implementation was corrected and requires a new evaluation.

The hard run recorded 24,076 trained-policy hits for CFR out of 24,085 CFR decisions; the remainder used fallback. CFR mean decision latency was 4.799 ms, p95 5.312 ms, maximum 23.853 ms. These are local batch measurements, not a prolonged kiosk-load benchmark. The screening and hard-opponent runs are descriptive; they have 200 matches per seat and are insufficient by themselves for the preregistered champion promotion.

The 1,000-per-seat paired-seed confirmation measured CFR beating probability **1,546/2,000 (77.3%, Wilson 75.4–79.1%)**, conservative **1,546/2,000 (77.3%, 75.4–79.1%)**, and high-call **1,651/2,000 (82.6%, 80.8–84.2%)**. Across the conservative and high-call league, CFR's win rate exceeded probability's by **7.15 percentage points**, with a 20,000-resample paired bootstrap 95% interval **[5.73, 8.55]** percentage points. Each seed block preserved both seats and both opponent results. CFR had 74,439 policy hits in 74,455 decisions; p95 CLI latency was 6.024 ms and maximum 38.290 ms. Its direct and opponent-specific results, zero illegal moves, and latency passed the registered promotion gates. `fixed5_cfr_100k` is the **measured champion for this local fixed-five opponent pool**, recorded in `policies/champions.json`; this does not establish global optimality.

The conservative and probability heuristics made identical choices in this mode because their different call thresholds fall between the same discrete five-unknown-dice prior values. Their direct matchup was 1,000/2,000 for the first-named agent, and their results against CFR matched. This reduces the effective diversity of the confirmatory pool; high-call and the earlier random/aggressive/always-call opponents provide the distinct robustness checks. No policy parameters were changed after the screen.

## Verification and limits

`make verify` passed after five-agent integration: C++ build, engine/trainer/HTTP unit tests, ESLint, TypeScript, and a patched Next.js production build. Additional engine and HTTP tests passed after the metadata updates. Engine tests cover quantity-only raises, forced call at quantity 10, random opener, fixed dice, scoring, redaction, replay, legal trained-agent moves, and invariance to hidden-human-dice changes. API tests cover invalid attempts including malformed JSON, stale versions, duplicate requests, explicit Next Round, deletion, five-agent metadata, and trained-agent creation. The browser exercised a complete match, the trained-agent live state, and the five-agent selector. Automated full-match browser scripting, prolonged kiosk load, and exact or restricted best-response/exploitability calculations for the fixed-five game remain unrun. The toy calculation does not validate five-dice equilibrium play.

Training, checkpoints, manifests, raw evaluation databases, summaries, and plots are preserved in deliverable archives. Large local duplicate exports were removed only after verifying the databases or archives. The evaluator enforced a 1.5 GiB artifact cap and 2 GiB free-disk guard; the trainer uses one CPU worker and the same guards.

## Staff explanation

Visitors see their five dice and claim how many of all ten dice show one face. They can raise the number or challenge the AI's claim. The AI sees only its own five dice and public moves, so it can be wrong or bluff. A challenge reveals both hands and gives one point to the round winner. First to five points wins. The Calculator uses exact odds for unseen dice; the Apprentice and Observer use an approximate trained policy, with the Observer adjusting from public past outcomes. The exhibition does not claim these policies solve the full game.
