# MCCFR external v2: audit, experiments, and results

## Baseline and constraints

On 12 November 2026, `codex/mccfr-v2` started from commit `1fbcaa9` with a clean working tree. Baseline `make verify` passed: 12 engine, 7 trainer, and 5 server tests, lint, typecheck, and a production Next.js build. No repository `AGENTS.md` was present. The machine had 16 GiB RAM, 10 logical CPUs, and approximately 5.1 GiB free disk. The experiment guard remains 1.5 GiB per run and 2 GiB free disk. Prior policies, checkpoints, evaluations, and evidence are preserved.

The authoritative ruleset is `fixed5_score5_quantity_only_v1`: each player rolls five fair six-sided dice each round, claims strictly increase in quantity to ten, challenges award a point, the loser starts the next round, and the first player to five points wins. The engine permits every larger quantity and face. The v1 MCCFR trainer instead permits six quantity-one openings plus one modal quantity-two opening, and later a challenge or one- or two-step raises on the current or modal face. Its key stores the private hand histogram, starter, player, and last two public bids. It optimizes a one-round +1/−1 payoff. The five-dice key has imperfect recall and no five-dice exploitability bound.

In the recorded 14,000-match v1 confirmation, v1 policy hits were 99.97% of its decisions against Apprentice, 99.98% against original CFR and adaptive, 99.83% against probability/conservative, 91.28% against truthful, and only 24.70% against aggressive. The remainder used the probability heuristic. These are the baseline coverage figures for v2. The v1 direct result against Apprentice was 1,069/2,000 (53.45%, approximate 95% paired-seed interval 51.49%–55.41%).

The existing policy SHA-256 values at baseline are: original CFR `9054a212e2865189ee9358e344e3fba48298408edb96fbf8cc343e75d005b977`, Apprentice `d99c9c002989c65fed62348b8ea623974436b7ebc75f9a0821c6e5edee99d9a8`, v1 MCCFR binary `6d184abbb39cd577d5cdd7668888fe419b485383e87ce88364743ecf6bb0522c`, and v1 compressed checkpoint `88cc97410e21f5c791bc4fdde85e9f3142ba154ca6073bf7367d46f9a0936c9e`.

## Design to test

The v2 trainer will remain separate from v1. It will sample fair dice and opponent actions, enumerate the traverser's abstract actions, update signed counterfactual regrets, and average strategies at opponent nodes as in [Lanctot et al.](https://proceedings.neurips.cc/paper/2009/hash/00411460f7c92d2124a67ea0f4cb5f85-Abstract.html) and [OpenSpiel's external-sampling implementation](https://github.com/google-deepmind/open_spiel/blob/master/open_spiel/algorithms/external_sampling_mccfr.cc). Its larger legal menu will cover more faces and quantity jumps, including high opening claims that currently force fallback against aggressive play. A fine information key will use more public bidding history and the acting player's private hand, never the other player's unrevealed dice. A learned coarser policy will handle unseen fine keys; its use will be counted separately from exact policy hits and heuristic fallback.

To target the first-to-five match, v2 will evaluate a challenge by the expected eventual match result after updating the scores and next starter, using a separately measured, frozen continuation model. This is a depth-limited approximation to full-match play: it optimizes the current round's decisions for a match-value target but does not solve the entire multi-round extensive game. We will compare it to a one-round-utility control and keep only measured improvements. The algorithm will be verified on a tractable one-die game and checked for legal actions, privacy, reproducibility, checkpoint recovery, and finite arithmetic before large training.

Development and final seeds will be separate, with paired seats and identical rules for v2 versus v1, Apprentice, original CFR, and the heuristic league. We will publish actual match counts, intervals that keep paired seeds together, policy coverage at each backoff level, latency, training time, memory, and resource limits. No strength or convergence claim will be made from iteration count alone.

## Design and feasibility measurements

A first attempt at full within-round history, exact score pairs, six faces at three successive raise quantities, and 24 opening actions hit the 1.8-million fine-set cap after only 100 iterations. Its failed run is `mccfr_v2_pilot_1000_20261112`; it reached 1,634,814 sets and 1,304,395,776 bytes peak RSS at that checkpoint. A last-three-bid and match-point-bucket pilot still created 649,746 sets at 1,000 iterations (`mccfr_v2_pilot_b_20261112`). These runs remain intact and were not selected.

The trainable design uses six faces at opening quantities 1, 2, and 10; thereafter it may challenge or raise by one or two using the current face, the private modal face, or the second most frequent private face. Its fine key has the private histogram, starter, player, the last two exact public bids, a flag for at least one earlier bid, and a flag for whether any earlier bid used the currently claimed face. This retains a small, relevant signal from older public history while remaining imperfect recall. It omits exact scores from the key to avoid severe sparsity, but training samples score pairs and uses the expected eventual match result as the challenge payoff. The coarse key drops the prior-bid and older-history features and its strategy is the sampled-visit-weighted marginal of fine MCCFR strategies. Exact and backoff policy sources are separately logged.

The continuation estimate came from 2,000 seeded v1-versus-v1 first rounds (`mccfr_v2_continuation_20261112`): the starter won 1,083 (54.15%, Wilson interval 51.96%–56.32%). Its match-value table follows the actual next-starter rule and the first-to-five score target. Since a fixed continuation that depends only on scores and the round winner assigns two fixed payoffs at each score, it does not by itself establish a strategically different full-match equilibrium. Score-independent policy keys further limit match-specific adaptation. This remains a **depth-limited full-match objective**, not full-game external-sampling MCCFR.

The independent one-die toy check measured exact best-response exploitability of 0.06877 after 1,000 iterations and 0.00679 after 10,000. A checkpoint-resume run and an uninterrupted run produced byte-identical toy policies; export-only recovery reproduced the policy. C++ self-tests cover signed regret matching, opponent sampling, fair dice, action legality, privacy, history features, and match terminal utility. These toy results do not estimate five-dice exploitability.

## Development screens

All rows below used paired development seeds 8,700,000–8,700,049, 50 matches per seat per opponent. The 10k, 100k, 500k, and 1m screens used fresh engine processes; the 2m screen used a verified equivalent persistent engine process. These sample sizes support checkpoint selection, not a superiority claim.

| Training iterations | Fine information sets | v2 wins vs v1 / 100 | v2 wins vs Apprentice / 100 |
| ---: | ---: | ---: | ---: |
| 10,000 | 603,124 | 7 | 5 |
| 100,000 | 849,182 | 31 | 40 |
| 500,000 | 915,747 | 47 | 45 |
| 1,000,000 | 932,262 | 53 | 57 |
| 2,000,000 | 943,046 | 52 | 58 |
| 5,000,000 | 951,916 | 57 | 62 |

An alternate 500,000-iteration run that enumerated both starters at each sampled chance outcome reached 932,330 fine sets, 57,958 backoff sets, and 756,760,576 bytes peak RSS. Its development screen was weaker: 44/100 against v1 and 48/100 against Apprentice on the same 8,700,000–8,700,049 seeds. This did not establish that starter enumeration is generally harmful; the run had one tenth as many iterations as the 5m candidate.

The 5m run made 10,000,000 traversals and sampled 1,000,173,874 terminal histories. Its 1m→5m segment took 650.59 seconds and peaked at 773,177,344 bytes RSS. The full float policy had 880,899 exact and backoff records and occupied 120,683,179 bytes (SHA-256 `6206b3cbb5adf6951af5043643093b443367531f9703cbf655e4c37a4c298244`), exceeding GitHub's normal 100 MB single-file limit. We converted its fixed-width float weights to 16-bit probabilities totaling 65,535 per record; the packed policy is 78,400,027 bytes with SHA-256 `4326b283fe865df94ced77bf5a2053ebe5520caf6c0d5df9ea7bf68c59c88bfb`. On independent development seeds 8,700,200–8,700,249, full-precision and packed policies produced byte-identical match outcomes, actions, and reveals across 200 paired, seat-balanced matches. This checks the tested trajectories, not every possible decision.

The 5m checkpoint is inaccessible because macOS cloud storage marked the gzip file `dataless`; reads failed with `Operation timed out`, and the attempted 10m resume stopped before any new iteration. The 5m float policy remained readable. A new local-disk run from the same seed, continuation, and compiled trainer reached 5m with a byte-identical float policy (SHA-256 `6206b3cbb5adf6951af5043643093b443367531f9703cbf655e4c37a4c298244`) and a readable gzip checkpoint (SHA-256 `8f62b02b737ade533c6100200850dc0d8af94f1d31f8c1c826e091e041fb2270`). It continued to 10m. This recovery avoids changing or deleting the existing pilot evidence.

Before reading the 10m result, the selection rule is: evaluate packed 5m and packed 10m on the same independent seeds 8,800,000–8,800,999 in both seats against v1 MCCFR, Apprentice, and original CFR. Select the higher equally weighted mean match win rate across those three opponents; if they are within one percentage point, retain 5m as the smaller checkpoint. Development screens are used for feasibility, not the final superiority claim. The final selected policy will then play fresh held-out seeds beginning at 9,000,000, with at least 5,000 per seat against each of those three major comparisons. A separate opponent league will use fresh seeds beginning at 9,100,000. These ranges were fixed before the 10m policy was available.

The first 5m validation attempt `mccfr_v2_validation_5m_20261112` was interrupted after 2,339 matches because the persistent engine reparsed the existing CFR JSON policy on every decision. Its partial SQLite log and failed manifest remain intact. Caching those immutable policy tables within the persistent engine passed fresh-versus-stream parity tests. Repeating the same seeds reproduced all 2,339 completed match outcomes, 69,213 actions, and 17,810 round reveals exactly. The completed cached run `mccfr_v2_validation_5m_cached_20261112` contains 6,000 matches, 172,459 decisions, zero errors, and a 36,077,568-byte SQLite log. It took 186.53 seconds while 10m training also ran, with 222,412,800 bytes peak Python RSS and 17,629,184 bytes peak engine RSS.

| 5m validation opponent | Wins / 2,000 | Win rate | Approximate 95% paired-seed interval | Exact / backoff decisions |
| --- | ---: | ---: | ---: | ---: |
| MCCFR v1 | 1,215 | 60.75% | 57.69%–63.73% | 29,583 / 0 |
| Apprentice | 1,253 | 62.65% | 59.61%–65.59% | 29,176 / 0 |
| Original CFR | 1,270 | 63.50% | 60.47%–66.43% | 25,765 / 3 |

The interval combines a normal seed-block estimate with a Wilson floor at the number of paired seeds, preventing degenerate intervals at all-win or all-loss edges. It is an approximate uncertainty summary, not an exploitability result. V2's persistent-process decision p95 across these pairings was 1.39–1.56 ms and excludes process startup.

The 2m policy also played 50 matches per seat against four additional development opponents on paired seeds 8,700,100–8,700,149. It won 72/100 versus probability, 99/100 versus aggressive, 64/100 versus truthful, and 76/100 versus adaptive. Exact-plus-learned-backoff coverage was 100% in all four pairings. Its aggressive pairing used 516 exact and 224 backoff decisions; the prior v1 policy had only 24.70% trained-policy coverage against aggressive in its larger confirmation. These are different seed sets and should not be interpreted as a direct win-rate improvement over v1.

The packed 5m policy used the same league development seeds and won 60/100 versus original CFR, 100/100 versus random, 68/100 versus probability, 100/100 versus aggressive, 68/100 versus conservative, 70/100 versus truthful, and 64/100 versus adaptive. Its exact-plus-backoff coverage was 100% in every pairing. Exact coverage against aggressive was 512/737 decisions (69.47%), against random 242/705 (34.33%), and against truthful 931/1,023 (91.01%). The rest used learned backoff. The measured policy decision latency in a persistent engine process during this screen ranged by pairing from 0.81 to 1.44 ms at p95; this includes JSON transport but excludes process startup and ran concurrently with training, so final latency measurements will be reported separately.

## Final selection and held-out results

The clean 10m run completed 10,000,000 training iterations and 1,957,731,975 sampled terminal histories, 956,380 fine information sets, and 57,960 coarse sets in 1,534.63 seconds, peaking at 775,241,728 bytes RSS. Its float policy SHA-256 is `57441e195f2c8fa4f1deb369308244c0110de0d111438c57f10bc49b31276946`; its Q16 policy SHA-256 is `dc8fad4e0ee4a078252663dbe7f603f562cd9148574cec661366ed7b9aadb7ba`; and its gzip checkpoint passed integrity verification with SHA-256 `da1baf274e7f727acee7ef5089a91590264a91c5348ca161c289861acf305fd0`. The complete 10m run remains in the ignored experiment directory, with the selected 5m checkpoint and Q16 policy copied to `policies/`.

| Candidate | Wins vs v1 / 2,000 | Wins vs Apprentice / 2,000 | Wins vs original CFR / 2,000 | Equal-opponent mean |
| --- | ---: | ---: | ---: | ---: |
| 5m | 1,215 | 1,253 | 1,270 | 62.30% |
| 10m | 1,225 | 1,251 | 1,313 | 63.15% |

Both candidates used seeds 8,800,000–8,800,999 in both seats. The 10m improvement in the three-opponent mean was 0.85 percentage points, below the predeclared one-point threshold, so the **5m policy was selected**. This does not establish that 10m is weaker; the rule controls a small validation difference and preserves the smaller checkpoint. The 10m validation contained 6,000 complete matches and zero logged errors. Its approximate paired-seed 95% intervals were 58.19%–64.22% against v1, 59.51%–65.50% against Apprentice, and 62.65%–68.53% against original CFR. Exact or learned-backoff coverage was 100% in all three pairings; its persistent-process p95 decision latency was 1.03–1.05 ms. The selected policy SHA-256 is `4326b283fe865df94ced77bf5a2053ebe5520caf6c0d5df9ea7bf68c59c88bfb`, and its preserved gzip checkpoint SHA-256 is `8f62b02b737ade533c6100200850dc0d8af94f1d31f8c1c826e091e041fb2270`.

The 30,000-match final holdout used paired seeds 9,000,000–9,004,999, both seats, and 10,000 matches against each major opponent. It completed with zero logged errors and 861,255 recorded decisions. Its persistent-process run took 810.98 seconds, used a 180,817,920-byte SQLite log, and peaked at 222,035,968 bytes Python RSS and 17,334,272 bytes engine RSS. Policy and engine checksums were pinned in the run manifest.

| Held-out opponent | V2 wins / 10,000 | Win rate | Approximate 95% paired-seed interval | Exact / learned backoff / heuristic decisions | p95 decision latency |
| --- | ---: | ---: | ---: | ---: | ---: |
| MCCFR v1 | 5,951 | 59.51% | 58.14%–60.86% | 147,620 / 9 / 0 | 1.24 ms |
| Apprentice CFR | 6,329 | 63.29% | 61.94%–64.62% | 146,713 / 5 / 0 | 1.40 ms |
| Original CFR | 6,407 | 64.07% | 62.73%–65.39% | 128,085 / 2 / 0 | 1.31 ms |

The intervals treat each paired seed's two seats as one block and include a seed-count Wilson floor. They measure match-win uncertainty against these opponents; they are not exploitability bounds. Exact policy coverage exceeded 99.99% in these three pairings, and learned backoff covered every remaining v2 decision. Latency includes JSON transport in a persistent process and excludes process startup. The broader held-out heuristic league is recorded separately on seeds beginning at 9,100,000.

The broader league completed 18,000 matches on paired seeds 9,100,000–9,100,999, with 371,844 decisions and zero logged errors. It took 321.13 seconds, produced an 82,984,960-byte SQLite log, and peaked at 185,466,880 bytes Python RSS and 4,489,216 bytes engine RSS.

| Opponent | V2 wins / 2,000 | Win rate | Approximate 95% paired-seed interval | Exact policy coverage |
| --- | ---: | ---: | ---: | ---: |
| Random | 2,000 | 100.00% | 99.62%–100.00% | 37.08% |
| Probability | 1,409 | 70.45% | 67.55%–73.20% | 99.99% |
| Aggressive | 1,997 | 99.85% | 99.35%–100.00% | 67.70% |
| Conservative | 1,409 | 70.45% | 67.55%–73.20% | 99.99% |
| Truthful | 1,248 | 62.40% | 59.36%–65.35% | 91.33% |
| Adaptive | 1,278 | 63.90% | 60.88%–66.82% | 99.99% |
| High-call | 1,598 | 79.90% | 77.30%–82.27% | 100.00% |
| Always-call | 1,861 | 93.05% | 91.30%–94.47% | 100.00% |
| Switcher | 1,775 | 88.75% | 86.64%–90.56% | 86.56% |

Learned backoff covered every decision outside the exact key in this league; heuristic fallback was zero. Probability and conservative had identical match-win totals on these seeds. The direct major comparisons and this league support promoting v2 over the earlier Apprentice as the local champion. They do not show a five-dice equilibrium or guaranteed performance against human adaptation. The frontend now selects v2 by default; the deployed production site remains on its prior release until separately updated.

The raw final match, decision, and reveal logs plus manifests and derived metrics are packaged as `evidence/mccfr-v2-final-20261112.zip` (39,810,064 bytes; SHA-256 `6efbd319ae93ee06b2d4bb1e7bee52482c933b67e3137a303aed6659844d562e`). Validation and continuation evidence are in `evidence/mccfr-v2-selection-20261112.zip` (10,975,482 bytes; SHA-256 `87e7dac40f727c30af778573ce2c907805c24218e1458dc67cebe839a76d1654`). The 10m training manifest is tracked as `docs/mccfr_v2_training_manifest.json`; it records that `1fbcaa9` was the clean starting Git base while the executed trainer source was uncommitted, and identifies the trainer binary by SHA-256. The selected policy and checkpoint are tracked separately.
