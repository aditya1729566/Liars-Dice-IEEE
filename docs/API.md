# Local API

Ruleset: `fixed5_score5_quantity_only_v1`. Base URL: `http://127.0.0.1:8787`. CORS allows the bundled web app from localhost/127.0.0.1 port 3000. The server binds to loopback.

| Method | Path | Result |
| --- | --- | --- |
| GET | `/api/health` | Engine status, ruleset, and trained-policy checksum check |
| GET | `/api/rules` | Public fixed-five rules |
| GET | `/api/agents` | Five selectable agents with policy scope and training metadata |
| POST | `/api/matches` | New match; `{ "n": 5, "agent": "probability" }` |
| GET | `/api/matches/:id` | Redacted human view for reconnect |
| POST | `/api/matches/:id/actions` | Bid or call with `expected_version` and `idempotency_key` |
| POST | `/api/matches/:id/next-round` | One atomic fresh roll after `ROUND_OVER`, with version and idempotency key |
| GET | `/api/matches/:id/events` | Public claims and completed-round reveals |
| GET | `/api/matches/:id/analysis/:round` | Exact outcome and naive prior, after reveal only |
| DELETE | `/api/matches/:id` | Deletes that visitor match, request cache, and invalid-action audit rows |
| GET | `/api/leaderboard` | Completed local current-ruleset matches only |
| GET | `/api/research/summary` | Completed current-ruleset evaluation summaries only |

Actions are `{ "type": "bid", "q": integer, "f": integer }` or `{ "type": "call" }`. A bid must have quantity 1–10 and face 1–6; after an existing bid, quantity must increase. At quantity 10, only call is legal. Successful responses include the new redacted view and increasing `version`. The same idempotency key returns its original response. A new key with a stale version receives HTTP 409. Invalid actions receive HTTP 400 and are recorded without advancing state. Active views omit AI dice and RNG state; completed-round reveal events contain both past hands.
