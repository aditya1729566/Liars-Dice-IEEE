# External-sampling MCCFR: implementation and measured results

## Scope

`mccfr_external_v1` is an independently trained, selectable opponent for the authoritative five-dice ruleset `fixed5_score5_quantity_only_v1`. It does not replace either existing CFR artifact. The existing Apprentice remains the default and the recorded champion in `policies/champions.json`.

The trainer optimizes the winner of **one round** with payoff +1/−1. The exhibition match awards a point each round and ends when a player reaches five. The policy therefore is not trained for full-match win probability. Its bid menu and information key are abstractions; no full-game equilibrium or exploitability guarantee is claimed.

## Algorithm and sampling

The C++20 trainer follows the external-sampling procedure in [Lanctot et al., *Monte Carlo Sampling for Regret Minimization in Extensive Games*](https://proceedings.neurips.cc/paper/2009/hash/00411460f7c92d2124a67ea0f4cb5f85-Abstract.html) and the [OpenSpiel external-sampling reference](https://github.com/google-deepmind/open_spiel/blob/master/open_spiel/algorithms/external_sampling_mccfr.cc):

1. Each iteration runs one traversal for each player. Each traversal samples two independent five-die hands and a fair starter.
2. At opponent nodes it samples one action from that opponent's current regret-matched strategy. At traverser nodes it explores every action in the abstract legal menu.
3. For traverser action values \(u(a)\), it adds \(u(a)-\sum_b\sigma(b)u(b)\) to cumulative regret. There is no extra opponent-reach multiplier: opponent actions and chance are sampled from their actual probabilities, so their reach cancels the external-sampling importance denominator. Cumulative regrets retain negative values; only the strategy calculation clamps regrets to positive parts.
4. At opponent nodes, the current distribution is added to the average-strategy sum. The probability of reaching those nodes includes the sampled player's prior actions, supplying implicit own-reach weighting. This is the simple average variant used by OpenSpiel. It is different from adding own reach at traverser nodes of an opponent-sampled traversal.

The older Python `train_exhibit_v2.py` already has external-sampling *traversal structure*, despite its “sampled CFR” label. It records average weights at traverser nodes using traverser reach. The new C++ trainer is isolated, has a different private-hand information key, deterministic RNG serialization, and opponent-node averaging. This difference is an implementation distinction, not evidence by itself that the new agent is stronger.

## Game abstraction and inference

Chance samples ten fair dice exactly as the engine does. A challenge counts the actual matching dice, with no wild face. Opening bids can be quantity one on any face or quantity two on the player's modal face. Later choices are a call or a raise by one or two with the current face or private modal face, always within quantity ten. The engine still permits all legal bids; this restriction applies to self-play training and model inference only.

The information key contains the acting player's six-face hand histogram, public starter and player, and the last two public bids. It never contains the opponent's unrevealed hand. The last-two-bid window is imperfect recall. At a human history absent from the trained table, the engine uses the existing probability heuristic and records that source explicitly. This fallback can be exploited; policy-hit rates are measured in the evaluation evidence.

The exported JSON policy is packed as sorted, fixed-size records in `policies/mccfr_external_v1.bin`. The engine binary-searches records by information key, then samples a legal action by its trained average weight. Both local and Vercel APIs verify its SHA-256 against `policies/index.json` before offering the agent. The direct engine handles missing or corrupt files with a legal heuristic fallback.

## Verification

The independent one-die toy game has all legal opening bids, quantity-two raises, complete public history, and an exact information-respecting best-response evaluator. With seed 42, measured exploitability was 0.083339 after 1,000 iterations and 0.008306 after 10,000. This verifies convergence on that toy; it is **not** an exploitability measure for the five-dice model. The toy test also checks policy normalization. The trainer self-test covers regret matching, action sampling, fair-die sampling, legal abstract moves, hidden-hand independence, and challenge utilities. A resume test compares policy and checkpoint bytes against an uninterrupted run.

Engine and API tests cover full matches, action legality, replay validity, policy checksums, redacted active views, hidden-hand independence, model availability, and corrupt-file fallback. Decompressing the tracked checkpoint into a fresh temporary directory and exporting it recreated the selected JSON policy byte for byte. A local browser playthrough against The Monte Carlo completed 0–5 in five rounds, then displayed a 25-step replay with recorded MCCFR policy weight and both post-match hands. The same match and Research view loaded in the production kiosk build. A 390-pixel mobile viewport had no horizontal overflow. Screenshots: [desktop replay](screenshots/mccfr-replay-20261112.jpg) and [mobile replay](screenshots/mccfr-replay-mobile-20261112.jpg).

## Training checkpoints

The training seed was 20261112 and one CPU worker was used. Each iteration contains two traversals. The staged run produced:

| Iterations | Traversals | Sampled terminal histories | Information sets | Measured segment wall time |
| ---: | ---: | ---: | ---: | ---: |
| 10,000 | 20,000 | 1,387,245 | 219,189 | 1.627 s |
| 100,000 | 200,000 | 8,534,483 | 317,413 | 5.054 s from 10k |
| 500,000 | 1,000,000 | 37,421,808 | 351,327 | 17.671 s from 100k |
| 1,000,000 | 2,000,000 | 72,751,079 | 361,343 | 21.038 s from 500k |

The four segment times sum to about 45.39 s, excluding process startup between resumes. A separate one-process rerun with the same seed and milestones completed in 60.979 s while the final tournament also used the machine. Its measured peak RSS was 676,544,512 bytes (645 MiB). A further one-process run from committed source `f740fce78a5e17830651f04f09805516fd2ffdbe` completed in 55.624 s with 581,255,168 bytes peak RSS, while the larger confirmation tournament was running. Its [manifest](../evidence/mccfr-committed-run-20261112.json) records the command, commit, seed, iterations, terminal histories, memory, and elapsed time. All three final checkpoints and JSON policies were byte-identical: checkpoint SHA-256 `6c36ab4e1b844e2da8db20b4dac60e8924591d9cf1916bf5078f8df99b3c6686`, JSON policy SHA-256 `4abee0311f2c418b5810668794ba900576c6ecf19b3fed2d3c4fced2c8a4396e`. The compressed, tracked checkpoint is `policies/mccfr_external_v1.checkpoint.json.gz` (SHA-256 `88cc97410e21f5c791bc4fdde85e9f3142ba154ca6073bf7367d46f9a0936c9e`). The 1m average policy has 277,980 nonempty information sets. Its packed artifact is 18,902,656 bytes, SHA-256 `6d184abbb39cd577d5cdd7668888fe419b485383e87ce88364743ecf6bb0522c`. The original CFR and Apprentice SHA-256 values remain `9054a212e2865189ee9358e344e3fba48298408edb96fbf8cc343e75d005b977` and `d99c9c002989c65fed62348b8ea623974436b7ebc75f9a0821c6e5edee99d9a8`.

## Checkpoint screening and selection

Development seeds 8,200,000–8,200,049 were paired and seat balanced. These screens used 50 matches per seat against each of Apprentice and Calculator:

| Checkpoint | vs Apprentice | vs Calculator |
| --- | ---: | ---: |
| 10k | 12/100 | 37/100 |
| 100k (retrospective rerun) | 32/100 | 64/100 |
| 500k | 54/100 | 67/100 |
| 1m | 52/100 | 70/100 |

The 1m checkpoint was selected before validation and final evaluation; its 122 total wins across those two opponents narrowly exceeded 500k's 121, and the individual differences are too small to establish a ranking. The original 100k policy became unavailable through local cloud offloading before its scheduled screen. A byte-identical final-checkpoint rerun recreated a 100k policy for a retrospective screen; that result did not influence checkpoint selection.

Validation used independent paired seeds 8,300,000–8,300,049, 50 matches per seat per opponent (700 matches total). The 1m policy won 56/100 vs Apprentice, 66/100 vs original CFR, 77/100 vs Calculator, 99/100 vs Bluffer, 77/100 vs conservative, 71/100 vs truthful, and 67/100 vs adaptive. The final evaluation uses new seeds 8,400,000 onward; its results and per-move metrics are recorded separately below.

## Final held-out benchmark

The frozen 1m policy was evaluated on new paired seeds 8,400,000–8,400,199, 200 matches per seat against each opponent: 2,800 completed matches and 73,191 recorded decisions. Counts below are Monte Carlo wins over 400 matches per opponent. Intervals use the sample variance of each seed's two-seat mean and a 1.96 normal multiplier; they are descriptive approximations that keep the paired seats together.

| Opponent | Wins / matches | Win % (95% paired-seed interval) | Avg rounds | MCCFR bluff % | MCCFR challenge % | Challenge accuracy % | MCCFR p95 decision ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Apprentice (`cfr2`) | 208 / 400 | 52.0 (47.3–56.7) | 7.63 | 29.9 | 25.6 | 63.4 | 4.37 |
| Original CFR | 256 / 400 | 64.0 (59.4–68.6) | 7.43 | 27.0 | 20.2 | 61.0 | 3.54 |
| Calculator | 290 / 400 | 72.5 (68.1–76.9) | 7.39 | 23.9 | 11.4 | 34.9 | 3.29 |
| Bluffer | 399 / 400 | 99.8 (99.3–100) | 6.16 | 16.0 | 76.6 | 81.3 | 3.08 |
| Conservative | 290 / 400 | 72.5 (68.1–76.9) | 7.39 | 23.9 | 11.4 | 34.9 | 3.64 |
| Truthful | 253 / 400 | 63.2 (58.0–68.5) | 7.71 | 25.8 | 13.4 | 3.0 | 3.41 |
| Observer (`adaptive`) | 271 / 400 | 67.8 (63.5–72.0) | 7.44 | 26.6 | 19.5 | 61.1 | 4.22 |

“Bluff” means a bid that the eventual revealed hands show to be false, including intermediate bids. Challenge frequency is calls divided by that agent's decisions, and challenge accuracy is won calls divided by calls. Latency times a fresh C++ engine process and policy lookup, excluding HTTP and storage. Match length in actions, exact counts, per-seat results, opponent metrics, policy-hit counts, engine checksum, and seed provenance are in the SQLite and JSON evidence. Calculator and conservative use thresholds that lead to identical move choices at these discrete priors. The 52% direct interval against Apprentice includes 50%; the evidence does not establish that Monte Carlo is stronger than the current champion. The Apprentice remains the default.

Raw [training checkpoints and policies](../evidence/mccfr-training-20261112.zip) (SHA-256 `28b8dc7c2cdc180e9644fa72f4f3b8548c4c447a6449ebd9ec9c3c0067cbb22d`) and [development, validation, and final evaluations](../evidence/mccfr-evaluation-20261112.zip) (SHA-256 `469d7538c542eb564ccee12d3e1e93cd92d55ebac56911958dec4ab1561bff45`) are tracked. The archives were integrity checked; the evaluation archive contains the per-match SQLite records.

## Larger independent confirmation

The same frozen 1m policy then played 1,000 matches per seat against each of seven opponents using new paired seeds 8,500,000–8,500,999. All 14,000 planned matches completed from 2026-11-12 11:15:04 to 12:00:05 UTC with zero logged errors and 365,670 recorded decisions. The table uses approximate 95% intervals that cluster each seed's two seats, as described above. These synthetic opponents and seeds differ from both screening and the initial final holdout.

| Opponent | Wins / matches | Win % (95% paired-seed interval) | Avg rounds | MCCFR bluff % | MCCFR challenge % | Challenge accuracy % | MCCFR p95 decision ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Apprentice (`cfr2`) | 1,069 / 2,000 | 53.45 (51.49–55.41) | 7.64 | 28.8 | 25.5 | 62.4 | 4.34 |
| Original CFR | 1,307 / 2,000 | 65.35 (63.34–67.36) | 7.43 | 27.1 | 20.3 | 60.0 | 3.94 |
| Calculator | 1,465 / 2,000 | 73.25 (71.36–75.14) | 7.38 | 24.1 | 11.5 | 35.6 | 3.76 |
| Bluffer | 1,988 / 2,000 | 99.40 (99.06–99.74) | 6.14 | 14.3 | 76.5 | 81.5 | 3.61 |
| Conservative | 1,465 / 2,000 | 73.25 (71.36–75.14) | 7.38 | 24.1 | 11.5 | 35.6 | 4.27 |
| Truthful | 1,249 / 2,000 | 62.45 (60.14–64.76) | 7.71 | 25.9 | 13.7 | 3.1 | 3.51 |
| Observer (`adaptive`) | 1,337 / 2,000 | 66.85 (64.90–68.80) | 7.44 | 26.8 | 19.4 | 58.7 | 4.33 |

The direct Apprentice interval is above 50% under this seed-paired approximation, supporting a measured advantage against that frozen policy in this evaluation. It does not prove a five-dice equilibrium strategy or predict results against people. Apprentice remains the application default as required. The Calculator and conservative rows again coincide in wins because their thresholds produce the same choices at these priors. Raw per-match actions, reveals, timings, policy hits, and fixed engine and model checksums are in [confirmation evidence](../evidence/mccfr-confirm-20261112.zip) (SHA-256 `582ba801ca7fad661aa6223a65db8efd3e2ad5fe5cdd2bb8e9b40ff94e068350`); the run manifest and per-opponent metrics are inside the integrity-checked archive. The production-kiosk [Research screenshot](screenshots/mccfr-confirm-research-20261112.jpg) shows the published paired interval beside a completed human replay. This confirmation did not change checkpoint selection.

## Reproduction and limitations

Run `make build-engine`, then `./build/mccfr_trainer --self-test`. The toy check is `python3.12 -m unittest trainer.test_mccfr -v`. For a new one-million-iteration run, use `make train-mccfr RUN_ID=<new-id> ITERATIONS=1000000 SEED=20261112 MCCFR_MILESTONES=10000,100000,500000,1000000`. Resume from a run's checkpoint with `./build/mccfr_trainer --run-id <id> --iterations <higher-budget> --seed 20261112 --resume --milestones <comma-list>`. To recover the selected tracked checkpoint in a fresh checkout, decompress `policies/mccfr_external_v1.checkpoint.json.gz` into `experiments/runs/<new-id>/checkpoint.json`, then run `./build/mccfr_trainer --run-id <new-id> --seed 20261112 --export-only` to recreate its JSON policy without another traversal. Pack an explicitly selected JSON policy with `python3.12 scripts/pack_mccfr_policy.py experiments/runs/<id>/policy_<iterations>.json policies/mccfr_external_v1.bin`; update the checksum in `policies/index.json` if deliberately changing the deployed candidate. Evaluate with `make evaluate-mccfr RUN_ID=<new-id> PER_SEAT=200 SEED_OFFSET=<unused-seed-base>`.

The benchmark is limited to the listed opponents, seeded synthetic matches, and the one-round abstraction. It does not measure equilibrium distance in the five-dice game or performance against humans. The model is selectable but not the default; no new deployment is asserted here.
