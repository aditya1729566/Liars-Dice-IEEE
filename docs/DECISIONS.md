# Decisions

- The 2026-11-07 fixed-five scoring specification supersedes the earlier elimination and lexicographic-bid draft. It is versioned as `fixed5_score5_quantity_only_v1`.
- The C++20 engine owns random rolls, legal moves, scores, phase transitions, and AI actions. The Python loopback HTTP adapter stores full state in SQLite, logs invalid attempts, and returns only a human-redacted view.
- The opener is selected uniformly from the two players by the engine. The next opener is the prior round's loser. New rounds require an explicit, idempotent HTTP transition.
- Visitor dice use system entropy; simulations use deterministic seeds. Active payloads omit AI dice and both RNG states.
- Prior experiment runs and the N=1 CFR policy are retained as legacy evidence. Their rules differ, so the current API excludes them and the engine cannot load that policy.
- Five opponents are selectable: random, probability, aggressive, a fixed-five quantity-only sampled-CFR champion, and a public-outcome adaptive candidate. The trained policy uses an imperfect-recall one-round abstraction, so the UI names that limitation. CFR passed the registered paired-seed and hard-opponent gates; adaptive remains experimental pending its corrected evaluation.
- The tournament runner enforces a 1.5 GiB artifact cap and 2 GiB free-disk guard.
- The Research page replays completed matches one event at a time. Both hands appear on slides as post-match evidence, with an explicit note that the AI did not see the human hand during play. Recorded AI policy weights explain stochastic action selection; short first-person readings of human bids are deterministic hypotheses from the AI hand and public move, not recovered CFR thoughts or claims to know human intent. The replay is available only after the final score.
