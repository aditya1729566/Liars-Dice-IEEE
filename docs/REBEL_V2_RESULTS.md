# Updated ReBeL BLUFF.EXE evaluation

## Model and rules

The separately selectable `rebel_bluff_v2` is the upstream BLUFF.EXE epoch-5 checkpoint from [`shivangijod-creator/ReBeL-Liars-Dice`](https://github.com/shivangijod-creator/ReBeL-Liars-Dice), commit `05607c7a208189ac6b0149337f45d46ad3828894`. Its checkpoint SHA-256 is `6c629db416e337bbce06e07375238b62fa3e414b8d36ae01b90635175fdbbc77`. The original `rebel_transfer_v1` and all CFR/MCCFR policies and prior evidence are preserved. The pinned upstream tree has no license file, so its source and checkpoint are fetched as ignored external dependencies rather than vendored here.

The checkpoint metadata specifies two players, five six-sided dice each, no wild faces, quantity-only raising, five points to win, multiset hands, and the upstream `linear_fp` model. Local inference uses 32 fictitious-play iterations with depth-one search. A separate worker isolates the updated upstream Python packages from the original ReBeL Transfer packages. The C++ engine remains the match referee. The worker receives the acting hand, public game state, and an independent search seed. The adapter validates the returned action before applying it.

One match-level rule still differs: the upstream engine alternates the next opener, while BLUFF.EXE makes the previous round loser open next. Search receives the actual BLUFF.EXE opener and scores; this does not make the upstream training objective identical to the local rules. The upstream public-belief update also uses a uniform placeholder for external action observation, so its belief should not be described as a fully learned strategic posterior. The model is a bounded search and value-network approximation; no equilibrium or convergence claim is made.

## Upstream evidence, separate from this evaluation

The upstream repository's `docs/bluff_evaluation_report.md` reports epoch 5 winning **3 of 200** matches against its ProbabilityAgent, **200 of 200** against RandomAgent, and **198 of 200** against an untrained search agent at depth one and 32 fictitious-play iterations. Those are upstream match-engine results, not BLUFF.EXE C++ matches, and are not combined with the local tournament below.

## Local verification and comparison

The bridge tests check redaction and hidden-hand invariance, quantity-only legal actions, second-seat play, and seed repeatability. A local HTTP test completes a human match, verifies active-view privacy, saves updated-ReBeL decisions, and retrieves the complete post-match replay. The final tournament uses the C++ rules engine, fresh paired seeds, both seats, a frozen checkpoint, and full decision/reveal logs. Per-opponent win intervals cluster the two seats by seed; they are approximate 95% intervals, and small samples should be read accordingly. Decision coverage counts worker responses, not learned information-set coverage.

The corrected final run `rebel_bluff_v2_final_random_20261114` completed all **2,800** planned matches on game seeds 10,000,000–10,000,099 in both seats against the 14 other opponents. It logged **59,028** total decisions, including **30,251** updated ReBeL decisions, and **zero** errors. Every action came from the ReBeL worker (100% worker response coverage); learned information-set coverage was **not measured**. The run took **679.20 seconds**. Updated ReBeL decision latency had a **21.32 ms median** and **25.97 ms 95th percentile** in persistent-process mode, excluding worker startup. The SQLite log is **13,537,280 bytes**. The parent Python process peaked at **1,228,636,160 bytes RSS**; the child-process RSS figure was **1,769,996,288 bytes** and includes the PyTorch worker, so it should not be interpreted as engine-only memory.

| Opponent | Updated ReBeL wins / 200 | Win rate | Approx. 95% paired-seed interval |
| --- | ---: | ---: | ---: |
| Original ReBeL Transfer | 190 | 95.0% | 88.8%–98.0% |
| MCCFR v2 (Monte Carlo II) | 37 | 18.5% | 12.1%–27.2% |
| MCCFR v1 (Monte Carlo) | 81 | 40.5% | 31.4%–50.3% |
| Apprentice CFR | 70 | 35.0% | 26.4%–44.7% |
| Original CFR | 29 | 14.5% | 8.9%–22.7% |
| Adaptive Observer | 19 | 9.5% | 5.2%–16.8% |
| Probability | 2 | 1.0% | 0.0%–5.4% |
| Random | 200 | 100.0% | 96.3%–100.0% |
| Aggressive | 198 | 99.0% | 94.6%–100.0% |
| Conservative | 0 | 0.0% | 0.0%–3.7% |
| Truthful | 0 | 0.0% | 0.0%–3.7% |
| High-call | 16 | 8.0% | 4.1%–15.0% |
| Always-call | 143 | 71.5% | 62.0%–79.4% |
| Switcher | 25 | 12.5% | 7.4%–20.4% |

The updated model is much stronger than the original rule-transfer checkpoint (**190/200**, 95.0%) and beats random (**200/200**) and the aggressive heuristic (**198/200**). It remains well behind the frozen MCCFR v2 champion (**37/200**, 18.5%) and the probability baseline (**2/200**, 1.0%). It also lost every match against the conservative and truthful heuristics in this sample. The MCCFR v2 result varied by seat: **7/100** when updated ReBeL occupied seat 0 and **30/100** in seat 1. The aggregate rate is seat-balanced; this asymmetry cautions against interpreting a single-seat result as overall strength. The updated model is selectable locally but was **not promoted**.

These results are for this checkpoint, 32-iteration depth-one search, and this exact ruleset. They do not show that all ReBeL approaches are weak, that the model converged, or that its play against humans will match the bot league. Upstream describes its checkpoint as an early 50-match pilot. Larger training budgets, improved public-belief updates, and testing opener-rule alignment remain hypotheses for future work, not measured improvements here.

The archived match log, decision and reveal records, manifest, metrics, and independently sampled search seeds are in `evidence/rebel-bluff-v2-final-20261114.zip` (**1,950,549 bytes**, SHA-256 `e6eeab923812393d4345bdb47ae9d992cb80e8aad833ba6703420bc4723a9986`). The checkpoint itself remains an external pinned dependency.

A separate two-match replay check ran the same game seeds and recorded search seeds twice. Both runs produced identical 36 decision records, match winners, and 10 reveals. This verifies that `--policy-seed-file` can reproduce recorded actions for that small check; it is not additional strength evidence.

## Reproduction

```sh
make setup-rebel-v2
make test-rebel-v2
make evaluate-rebel-v2 RUN_ID=rebel_bluff_v2_final_random_20261114 PER_SEAT=100 SEED_OFFSET=10000000 MIN_FREE_MIB=2048
make research-index
```

For an exact rerun of the recorded search RNG streams, pass `--policy-seed-file experiments/runs/rebel_bluff_v2_final_random_20261114/policy_seeds.json` to `scripts/tournament.py` with the same agent order, seed offset, and per-seat count but a new run ID. The archived `policy_seeds.json` can be extracted first on a fresh checkout.

The one-time run in this workspace used `MIN_FREE_MIB=512` because the existing machine's free disk space fluctuated around 1–2 GiB; it retained the 1.5 GiB experiment artifact cap. The first attempt stopped after 400 matches at the disk guard. A second attempt was deliberately interrupted after 1,800 matches when we found that the updated search RNG received the game seed. A third short attempt revealed the same historical issue in the original ReBeL Transfer baseline and was also stopped. A fourth short attempt used a deterministic seed derived from the numbered game-seed index; it was stopped to remove even that indirect link. The partial runs remain in this workspace's ignored `experiments/runs` directory as failed diagnostics and are excluded from the delivered archive and final comparison. The final run gives both ReBeL searches independent OS-random seeds, recorded in `policy_seeds.json` and reused across the two seats for each paired seed. Neither ReBeL policy receives the game seed; the recorded search seeds allow exact reruns.
