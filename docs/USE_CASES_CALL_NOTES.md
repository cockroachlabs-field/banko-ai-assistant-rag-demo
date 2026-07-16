# Banko AI Assistant: use-case crib sheet (local only, do not commit)

One Flask app, one CockroachDB cluster underneath everything. The through-line
for the customer: the same database that holds the transactions also holds the
vectors, the chat memory, the agent checkpoints, the cache, and the streaming
signal queue. No bolt-on vector database, no separate memory store, and
everything inherits CRDB's survivability.

Demo from the feat/coach-core-v1a branch; it contains everything on main plus
the Coach.

## 1. RAG and semantic search

Expense data is embedded locally with all-MiniLM-L6-v2 (384-dim,
sentence-transformers, no API key needed for embeddings) and indexed with
CockroachDB's C-SPANN vector indexes using cosine distance. Ask "how much did
I spend on coffee last month?" and the answer comes back grounded in actual
rows, with a transaction table.

Demo move: the /banko chat, then /api/search if they want raw similarity
scores.

## 2. Multi-agent workflows

Upload a receipt photo and three LangGraph agents run in sequence: Receipt
(tesseract OCR plus LLM field extraction, with a Pydantic validation gate that
rejects bad extractions), Fraud, and Budget. The response shows each agent's
verdict and the expense lands in the ledger. Agent decisions are recorded in
the database, so the activity you show is real, not staged.

Demo move: upload any receipt image; the JSON response names all three agents.

## 3. Memory and durability

Chat history persists in CRDB via langchain-cockroachdb, and LangGraph agent
state checkpoints into CRDB through CockroachDBSaver with a 7-day TTL, so a
conversation survives an app restart. The three-tier semantic cache (query,
embedding, vector search) also lives in CRDB; /cache-stats shows live hit
rates and a running tokens-saved counter, a nice cost-story moment.

## 4. Streaming + agentic (the Coach, on the coach branch)

The part that speaks first instead of waiting to be asked. A spending signal
arrives over a CDC-style webhook (HMAC authenticated; a flag-gated
Kafka/Debezium path exists for the production shape), an idempotent handler
queues it, and the Coach agent plans, calls real budget and transaction tools,
and produces a nudge like "you've used 82% of your dining budget with nine
days left," pushed live to the /coach tab over SocketIO and persisted with
full provider attribution. If the LLM is unreachable it degrades to a plain
rule-based nudge rather than failing.

Demo move: with the app open on /coach,
    uv run python scripts/coach/mock_signals.py --type=budget_threshold
and watch the card arrive. Other types: anomaly, recurring_drift.

## 5. Provider freedom

Same app against watsonx (default), OpenAI, AWS Bedrock, and Gemini with a
single AI_SERVICE env switch; all LLM traffic goes through one provider
abstraction layer. Embeddings are always local, which matters for the
regulated-industry conversation. Full airgap with Ollama and Granite is the
next planned increment; present as direction, not shipped.

## Pre-call checklist

- Run from the coach branch:
    DATABASE_URL=cockroachdb://root@localhost:26257/banko_ai \
    AI_SERVICE=watsonx CDC_WEBHOOK_HMAC_SECRET=dev-only-secret \
    uv run banko-ai run
- CRDB is already up in Docker with 5,000 sample expenses.
- Clean Gemini-outage artifacts first so every nudge card is real LLM output:
    DELETE FROM coach_nudges WHERE provider_used = 'fallback';
- Gemini is temporarily down for us (GCP project cockroach-harsh-432021
  returns CONSUMER_INVALID project-wide since ~12:00 July 15; Harsh's email
  about Gemini model access is related; check the project in the console).
  watsonx, OpenAI, Bedrock are all verified working today.
