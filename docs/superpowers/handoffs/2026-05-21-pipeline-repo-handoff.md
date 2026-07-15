# Handoff prompt — pipeline repo (cockroachdb-watsonx-data-pipeline)

Drafted 2026-05-21. **Local artifact only — not committed.**

This is the prompt to paste into your separate Claude Code session that is working on `~/idea_workspace/cockroachdb-watsonx-data-pipeline` so it can build the producer side of the **Proactive Spending Coach** contract while the banko-ai-assistant session builds the consumer side.

The two sessions are independent; the only thing they share is a written contract (this prompt, and the eventual `PIPELINE_CONTRACT.md` at the root of banko-ai-assistant once it ships).

---

## Paste this into the pipeline-repo Claude Code session

```
We're building the producer side of a streaming contract with a sibling
repo, banko-ai-assistant (at ~/idea_workspace/banko-ai-assistant, GitHub:
cockroachlabs-field/banko-ai-assistant). That repo is in the middle of
adding a "Proactive Spending Coach" agent that consumes streaming
spending signals from this pipeline.

The full design lives in the banko-ai-assistant repo at:
docs/superpowers/specs/2026-05-21-proactive-spending-coach-design.md
(local, uncommitted — read it from the filesystem). Sections 3 (Data Flow)
and 11 (PIPELINE_CONTRACT outline) describe what banko expects from us.

## What we need to produce

A new event type called "spending_signals." Three signal types in v1:

  1. budget_threshold   — user crossed a configurable percentage of a
                          monthly category budget (default trigger: 80%)
  2. anomaly            — current period spend deviates >2σ from the
                          user's rolling 6-week baseline in some category
  3. recurring_drift    — a known recurring charge (subscriptions,
                          utilities) came in materially above its
                          historical norm

Each signal lands as a row in a CockroachDB table named
`spending_signals` and is simultaneously published to a Kafka topic of
the same name. Banko consumes from EITHER path depending on deployment
mode (webhook for demo/dev, Kafka for prod).

## Contract: `spending_signals` schema

```sql
CREATE TABLE spending_signals (
  signal_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          UUID NOT NULL,
  signal_type      STRING NOT NULL,    -- budget_threshold | anomaly | recurring_drift
  severity         STRING NOT NULL,    -- info | warn | critical
  payload          JSONB NOT NULL,     -- type-specific detail, see below
  produced_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  consumed_at      TIMESTAMPTZ,        -- consumer sets this; nullable
  idempotency_key  STRING NOT NULL UNIQUE,
  INDEX (user_id, produced_at DESC)
) WITH (ttl_expire_after = '30 days');
```

The `idempotency_key` MUST be deterministic from the signal's content —
banko relies on it to deduplicate redeliveries. Recommended format:
`{signal_type}:{user_id}:{period_start_iso}:{category}` for
budget_threshold, similar for the others. Same input → same key.

## Payload schemas (JSONB)

budget_threshold:
  {
    "category": "dining",
    "threshold_pct": 0.80,
    "current_pct": 0.83,
    "budget_amount_cents": 50000,
    "spent_amount_cents": 41500,
    "period_start": "2026-05-01",
    "period_end": "2026-05-31",
    "days_remaining": 11
  }

anomaly:
  {
    "category": "rideshare",
    "current_amount_cents": 28400,
    "baseline_mean_cents": 12100,
    "baseline_stddev_cents": 4200,
    "z_score": 3.88,
    "window_weeks": 6,
    "period_start": "2026-05-15",
    "period_end": "2026-05-21"
  }

recurring_drift:
  {
    "merchant": "Netflix",
    "expected_amount_cents": 1599,
    "actual_amount_cents": 2299,
    "delta_pct": 0.438,
    "last_seen": "2026-04-19",
    "this_seen": "2026-05-19"
  }

Severity rule of thumb:
  info     — gentle nudge (e.g., crossed 80% threshold mid-month)
  warn     — needs attention this week (crossed 90%, or 2-3σ anomaly)
  critical — needs attention today (overspend, 4σ+ anomaly,
             subscription >50% drift)

## Delivery: two paths, banko picks

1. Webhook (demo / dev mode)
   POST {BANKO_WEBHOOK_URL}/api/coach/signals
   Headers:
     Content-Type: application/json
     X-Signature: hmac-sha256 of body using shared secret
                  (env: BANKO_WEBHOOK_HMAC_SECRET)
     X-Idempotency-Key: same as the row's idempotency_key
   Body: the row contents serialized as JSON (snake_case keys).

   Retry policy: exponential backoff (1s, 2s, 4s, 8s, 16s),
   max 5 attempts. On final failure, leave row in the table with
   consumed_at=NULL; banko will reconcile on its next poll.

2. Kafka (prod)
   Topic: spending_signals
   Partition key: user_id (so per-user signals stay ordered)
   Value: same JSON as the webhook body
   Headers: idempotency-key, signal-type, severity

## What the pipeline repo needs to do

1. Add a new processor stage that runs (probably nightly + on-demand
   trigger) and emits these signals. Inputs come from the same Iceberg
   tables we're already producing for the lakehouse work — expenses,
   budgets, and recurring charges.

2. Write each emitted signal to (a) the CockroachDB `spending_signals`
   table AND (b) the Kafka `spending_signals` topic, in one transactional
   unit so they can't drift.

3. For the webhook path, a small sender service polls the table for
   rows where consumed_at IS NULL and produced_at is in the last 5 min,
   POSTs them to banko, and updates consumed_at on success.

4. Expose a Prometheus metric `spending_signals_emitted_total{type,severity}`
   and `spending_signals_dropped_total{reason}` so banko-side observability
   can join across both sides via shared trace IDs (we use W3C trace
   context — propagate the traceparent header on webhooks).

## Test fixtures

The banko-ai-assistant repo has `scripts/coach/mock_signals.py` (planned)
that emits hand-crafted signals through the webhook for end-to-end
testing. Use the same payload shapes there as a forcing function — if
our real producer's shapes drift from those fixtures, banko's tests
will catch it.

## What to ask the user

Before implementing, confirm with Virag:
  - Which Iceberg tables on watsonx.data already have the budget /
    recurring-charge data we need, vs which need to be added.
  - Whether the nightly trigger and on-demand trigger should be one
    code path or two.
  - Whether the webhook sender should live in this repo or be a tiny
    sidecar in the banko repo (the spec leans toward "this repo owns
    delivery"; confirm).
  - Default values for the budget threshold trigger (banko-side spec
    uses 80% but says "configurable" — does the pipeline own that
    config or does banko send it as a per-user setting?).

## Things to NOT do

  - Don't import banko-ai-assistant code, even via path manipulation.
    The only coupling is the schema + delivery contract.
  - Don't write to any banko table other than `spending_signals`.
  - Don't introduce a different signal-shape version mid-stream;
    add a new signal_type instead.
  - Don't commit/push until tested end-to-end against banko locally.
    Virag has a strict "test locally before push" rule for both repos.

When this lands on the pipeline side, ping Virag and he'll wire the
banko-side consumer (which is the Coach v1 work) against your producer.
```

---

## Notes for the banko-ai-assistant session (i.e., us)

- This handoff prompt is **frozen at 2026-05-21**. If the spec changes (e.g., we add a 4th signal type, or rename `consumed_at`), update both this file AND coordinate with the pipeline-side session — don't let the contract drift silently.
- The `PIPELINE_CONTRACT.md` that lives at the banko repo root (planned during Coach v1 implementation) is the canonical version once it ships. This handoff prompt is the bootstrap.
- The pipeline session may push back on schema details (e.g., "we already have a `severity_score` column elsewhere, can we use a number not a string?"). That's expected — negotiate, then update both sides.
- After the pipeline session finishes its producer, run the full end-to-end smoke from the banko side using `scripts/coach/mock_signals.py` first (proves the consumer works), then point banko at the real pipeline output and re-run.
