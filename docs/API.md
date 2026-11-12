# Local API

Ruleset: `fixed5_score5_quantity_only_v1`. Base URL: `http://127.0.0.1:8787`. CORS allows the bundled web app from localhost/127.0.0.1 port 3000. The server binds to loopback.

| Method | Path | Result |
| --- | --- | --- |
| GET | `/api/health` | Engine status, ruleset, and trained-policy checksum check |
| GET | `/api/rules` | Public fixed-five rules |
| GET | `/api/agents` | Agent IDs, availability, policy scope, and training metadata; ReBeL Transfer requires local setup |
| POST | `/api/matches` | New match; `{ "n": 5, "agent": "probability" }` |
| GET | `/api/matches/:id` | Redacted human view for reconnect |
| POST | `/api/matches/:id/actions` | Bid or call with `expected_version` and `idempotency_key` |
| POST | `/api/matches/:id/next-round` | One atomic fresh roll after `ROUND_OVER`, with version and idempotency key |
| GET | `/api/matches/:id/events` | Public claims and completed-round reveals |
| GET | `/api/matches/:id/analysis/:round` | Exact outcome and naive prior, after reveal only |
| GET | `/api/matches/:id/research` | Complete ordered replay slides, recorded AI decisions, and probabilities after match completion only; HTTP 409 while active |
| DELETE | `/api/matches/:id` | Deletes that visitor match, request cache, and invalid-action audit rows |
| GET | `/api/leaderboard` | Completed local current-ruleset matches only |
| GET | `/api/research/summary` | Completed current-ruleset evaluation summaries only |

Actions are `{ "type": "bid", "q": integer, "f": integer }` or `{ "type": "call" }`. A bid must have quantity 1–10 and face 1–6; after an existing bid, quantity must increase. At quantity 10, only call is legal. Successful responses include the new redacted view and increasing `version`. The same idempotency key returns its original response. A new key with a stale version receives HTTP 409. Invalid actions receive HTTP 400 and are recorded without advancing state. Active views omit AI dice, decision traces, and RNG state; completed-round reveal events contain both past hands. The post-match research response includes `replay`, an ordered array with one slide per authoritative event plus a separate `call` slide before each `reveal`. Slides include round, actor, both revealed hands, bid, scores, actual count, AI truth prior, hand support, sampled policy weight and options when recorded, and `ai_read`. The `ai_read` for human moves is a deterministic, post-match interpretation from the AI hand and public action, never knowledge of the human's intent. The prior is not an opponent-model posterior; the policy weight is not a win probability. The `mccfr_external_v1`, separately versioned `mccfr_external_v2`, and local-only `rebel_transfer_v1` identifiers are exposed in `/api/agents`, persisted match state, and post-match decisions; `cfr2` remains the frontend default. V2 decision traces identify exact versus learned-backoff policy use. ReBeL Transfer traces identify depth-one search and policy weight. The MCCFR agents are checksum-gated; ReBeL is available only after its pinned source, checkpoint, and PyTorch runtime pass local checks.
