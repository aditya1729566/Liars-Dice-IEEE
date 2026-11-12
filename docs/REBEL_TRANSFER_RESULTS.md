# ReBeL transfer agent: integration and measured tournament

## Provenance and rule audit

The source is [ReBeL-Liars-Dice](https://github.com/shivangijod-creator/ReBeL-Liars-Dice), pinned to commit `1d915cc2dcecf9670aaec652ab78bf528241ce21`. The source tree contains no license file, so this repository fetches it at setup and does not vendor its code or weights. The `rebel_5x6f_epoch_6.pt` checkpoint has SHA-256 `028b9708fe60848cd409fde581bee1e92e20aa67b7cbd65c475e7bf0149f2f3a`. It loads with PyTorch's `weights_only=True`; its saved configuration is five dice, six faces, multiset hands, **highest face wild**, with a 567-input/252-output value network. The source action codec allows quantity-preserving face raises and its search learns a one-round payoff. BLUFF.EXE instead has no wild face, permits only strictly increasing quantities, and awards the first-to-five match. Upstream benchmark numbers therefore do not apply to this game.

The separately named `rebel_transfer_v1` adapts the source codec's legal range to quantity-only bids, disables wild matching in the upstream game configuration, reindexes the starter as the source's player zero each round, and gives the search only the acting hand and current-round public bids. The C++ engine validates every selected move and remains authoritative for rolls, scores, replay, and persistence. The agent uses the saved network plus depth-one, four-iteration linear fictitious-play search on CPU. Its public-belief tracker resets after each reroll. The upstream agent's external-action update uses a uniform placeholder, so this is an approximate transfer implementation and does not claim a faithful ReBeL belief posterior or equilibrium guarantee. It does not retrain the checkpoint under BLUFF.EXE rules.

The four-iteration development screen on seeds 9,300,000–9,300,099 won 1/200 against MCCFR v2, 5/200 against MCCFR v1, 7/200 against Apprentice, 5/200 against original CFR, and 1/200 against probability. It did beat random 200/200 and aggressive 123/200. This showed a major rule-transfer failure rather than competitive strength. Increasing depth-one search to 16 iterations on a separate 80-match development screen (20 per seat against probability and MCCFR v2, seeds 9,450,000–9,450,019) won 0/40 against each, while a separate 32-iteration opening probe took 0.224 seconds versus 0.028 seconds for four iterations. A depth-two, 16-iteration opening took 3.31 seconds and still opened at quantity three. We retained the four-iteration version for its lower inference cost; none of these small screens proves it is the optimal search setting.

`make setup-rebel` fetches the pinned source, verifies the checkpoint, and installs the local PyTorch runtime. `make test-rebel` checks hidden-hand redaction, action invariance when only the unseen hand changes, second-seat indexing, and quantity-only legality. `make dev` then offers the ReBeL Transfer as a human opponent through the Python API and local web proxy. The Vercel Node deployment reports it unavailable because that runtime does not contain this local PyTorch dependency; the UI disables its card there. A full local human match was completed through the API and recorded seven ReBeL decisions, a final score of 2–5, and a 35-slide post-match replay. That single match is an integration check, not a strength estimate.

## Tournament protocol

Run `rebel_transfer_league_20261112` uses the authoritative fixed-five rules, paired seeds starting at 9,300,000, both seats, and 100 matches per seat against each of the 13 other engine opponents: MCCFR v2, MCCFR v1, Apprentice CFR, original CFR, adaptive, random, probability, aggressive, conservative, truthful, high-call, always-call, and switcher. It is a development screen: the search sampler was reset between matches but its random stream was not reseeded per match. The final tournament will use a fresh seed range beginning at 9,400,000 and reset the sampler to each match seed. Every match, decision, reveal, policy checksum, source commit, latency, and process resource usage is recorded in its ignored run folder. A tracked summary will be generated for the Research page. Confidence intervals group both seats for each seed. This sample size is useful for a broad screen but cannot resolve close pairings as precisely as the 10,000-match MCCFR v2 comparisons.

## Results

The corrected final tournament completed all 2,600 planned matches on seeds 9,400,000–9,400,099 in both seats, with 40,715 logged decisions and zero logged errors. The ReBeL sampler was reseeded for each match. The run took 565.20 seconds, peaked at 2,094,022,656 bytes Python RSS and 16,957,440 bytes engine RSS, and produced a 9,924,608-byte SQLite log. Persistent-process ReBeL decision p95 ranged from 30.22 to 51.73 ms by opponent; this excludes process startup. Each interval below treats the two seats for a seed as one block, with a Wilson floor for small or extreme results.

| Opponent | ReBeL wins / 200 | Win rate | Approximate 95% paired-seed interval |
| --- | ---: | ---: | ---: |
| MCCFR v2 | 0 | 0.00% | 0.00%–3.70% |
| MCCFR v1 | 2 | 1.00% | 0.00%–5.45% |
| Apprentice CFR | 8 | 4.00% | 1.33%–9.84% |
| Original CFR | 9 | 4.50% | 1.36%–10.51% |
| Adaptive | 8 | 4.00% | 0.99%–9.84% |
| Random | 199 | 99.50% | 95.39%–100.00% |
| Probability | 1 | 0.50% | 0.00%–4.61% |
| Aggressive | 134 | 67.00% | 57.31%–75.44% |
| Conservative | 1 | 0.50% | 0.00%–4.61% |
| Truthful | 0 | 0.00% | 0.00%–3.70% |
| High-call | 3 | 1.50% | 0.00%–6.24% |
| Always-call | 27 | 13.50% | 7.45%–21.56% |
| Switcher | 8 | 4.00% | 1.33%–9.84% |

This model is selectable locally because it implements the requested checkpoint and search, but it was **not promoted**. The results support a narrow conclusion: directly transferring this value network to no-wild, quantity-only play is weak against most existing opponents. They do not measure how a ReBeL model retrained under the correct rules would play. The results also do not provide a full-game exploitability bound or human-match performance estimate.

Every final match, decision, reveal, manifest, and derived metric is archived in `evidence/rebel-transfer-final-20261112.zip` (1,459,304 bytes; SHA-256 `2a04eea04c750b2eb4eb1e52de98d105e5eca204dd766634d335b108e3a11cd7`). Development screens are archived separately in `evidence/rebel-transfer-development-20261112.zip` (1,547,339 bytes; SHA-256 `b3d7ae99e48d9dc1905387fb05e5d2e385e6549934e3dd1e67647fc4b1b1ada4`). The model checkpoint is fetched from the pinned upstream source and is not embedded in either archive.
