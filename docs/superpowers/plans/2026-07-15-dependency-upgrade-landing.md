# Dependency upgrade landing plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land `chore/preflight-housekeeping` on main with a refreshed dependency batch that supersedes all 21 open PRs, fully gated by local tests and a five provider smoke, then rebase the coach branch on top.

**Architecture:** This is an operations plan, not a feature build. The work is git hygiene (backup pushes, merge, rebase), one `uv lock --upgrade` refresh with an embedding parity check around the sentence-transformers 3.x to 5.x jump, and the repo's standard local test gate before anything touches origin/main.

**Tech Stack:** git, gh CLI, uv 0.11.x, pytest, docker compose (services: `cockroachdb`, `banko-ai`), sentence-transformers.

## Global constraints

- No em-dashes anywhere: commits, docs, comments. Use commas, periods, or parentheses.
- No bot trailers or "Generated with" lines. Commits read like Virag wrote them.
- Nothing merges to main until Task 4 (automated gate) and Task 5 (provider smoke) pass. Backup pushes of WIP branches (Task 1) are allowed, merging is not.
- All five providers must smoke clean: watsonx, OpenAI, AWS Bedrock (env value `aws`, not `bedrock`), Gemini, Ollama.
- Never touch provider SDKs directly; if a dep bump breaks a provider, the fix goes in `banko_ai/ai_providers/`.
- Spec: `docs/superpowers/specs/2026-07-15-dependency-upgrade-design.md`.

---

### Task 1: Back up all local-only work

**Files:**
- Commit (on `feat/coach-core-v1a`): `README.md`, `docs/superpowers/` (specs, plans, handoffs)

**Interfaces:**
- Produces: both local branches exist on origin; later tasks may rewrite them only with `--force-with-lease`.

- [ ] **Step 1: Confirm starting state**

Run: `git status --short && git branch --show-current`
Expected: on `feat/coach-core-v1a`, modified `README.md`, untracked `docs/superpowers/`.

- [ ] **Step 2: Commit the loose docs to the coach branch**

```bash
git add README.md docs/superpowers/
git commit -m "docs: capture the coach spec, plans, and readme edits locally

These were sitting uncommitted in the working tree since the May
sessions. Committing them here so the branch is self contained before
it gets pushed as a backup."
```

- [ ] **Step 3: Push both branches as backups (no PRs)**

```bash
git push -u origin feat/coach-core-v1a
git push -u origin chore/preflight-housekeeping
```

Expected: two new remote branches. Do not open PRs for them.

- [ ] **Step 4: Verify**

Run: `git branch -r | grep -E 'coach-core-v1a|preflight-housekeeping'`
Expected: both listed.

- [ ] **Step 5: Capture the embedding baseline under the old lockfile**

Still on the coach branch (its lockfile predates the sentence-transformers jump):

```bash
uv sync --extra dev
uv run python - <<'EOF'
from sentence_transformers import SentenceTransformer
import numpy as np
model = SentenceTransformer('all-MiniLM-L6-v2')
texts = ["coffee at starbucks 4.85",
         "monthly rent payment to hudson apartments",
         "uber ride downtown 18.20"]
vecs = model.encode(texts, normalize_embeddings=False)
np.save('/tmp/st_baseline.npy', vecs)
print("saved", vecs.shape)
EOF
```

Expected output: `saved (3, 384)`.

---

### Task 2: Refresh the dependency batch on chore/preflight-housekeeping

**Files:**
- Modify: `.github/workflows/ci.yml` (4 checkout refs), `.github/workflows/docker.yml` (1), `.github/workflows/release.yml` (1)
- Modify: `pyproject.toml` (comment style only), `uv.lock` (regenerated)

**Interfaces:**
- Consumes: `/tmp/st_baseline.npy` from Task 1.
- Produces: a preflight branch whose lockfile is current as of July 2026. Task 3 tests exactly this state.

- [ ] **Step 1: Switch branches**

Run: `git switch chore/preflight-housekeeping`

- [ ] **Step 2: Bump actions/checkout to v7 in all three workflows**

```bash
sed -i '' 's|uses: actions/checkout@v6|uses: actions/checkout@v7|' \
  .github/workflows/ci.yml .github/workflows/docker.yml .github/workflows/release.yml
git diff --stat
```

Expected: 3 files changed, 6 lines. (gh-release is already at v3 on this branch.)

- [ ] **Step 3: Commit the CI bump**

```bash
git add .github/workflows
git commit -m "ci: move to actions/checkout v7"
```

- [ ] **Step 4: Clean up the em-dash comment in pyproject.toml**

In the Google Integration comment block, replace the line

```
# vertexai SDK removed 2026-05-22 — deprecated 2025-06-24, hard removal
```

with

```
# vertexai SDK removed 2026-05-22 (deprecated 2025-06-24, hard removal
```

- [ ] **Step 5: Refresh the lockfile and install**

```bash
uv lock --upgrade
uv sync --extra dev
```

- [ ] **Step 6: Confirm the headline versions landed**

```bash
grep -A1 -E '^name = "(sentence-transformers|langchain|langchain-core|langsmith|cryptography|aiohttp|pypdf|gunicorn|python-socketio)"$' uv.lock | grep -E 'name|version'
```

Expected: sentence-transformers 5.x, langchain 1.3.x, langchain-core 1.3.x, langsmith 0.8.x, cryptography 48.x, aiohttp 3.14.x, pypdf 6.13.x, gunicorn 26.x or the newest below 27, python-socketio 5.16.2.

- [ ] **Step 7: Embedding parity check against the Task 1 baseline**

```bash
uv run python - <<'EOF'
from sentence_transformers import SentenceTransformer
import numpy as np
model = SentenceTransformer('all-MiniLM-L6-v2')
texts = ["coffee at starbucks 4.85",
         "monthly rent payment to hudson apartments",
         "uber ride downtown 18.20"]
new = model.encode(texts, normalize_embeddings=False)
old = np.load('/tmp/st_baseline.npy')
cos = [float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
       for a, b in zip(old, new)]
print("cosine:", cos)
assert all(c > 0.9999 for c in cos), "embedding drift, do not proceed"
print("parity OK")
EOF
```

Expected: `parity OK`.
If it fails: pin `sentence-transformers>=3.1.0,<4.0.0` back in pyproject.toml, rerun `uv lock --upgrade && uv sync --extra dev`, note the deferral in the Step 8 commit body, and continue.

- [ ] **Step 8: Commit the refreshed batch**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: refresh the dependency batch to current versions

The May batch sat unmerged while dependabot kept filing bumps, so this
brings the lockfile current in one pass instead of replaying 18 PRs.
Notable jumps: langchain 1.3.9, langchain-core 1.3.3, langsmith 0.8.x,
cryptography 48, aiohttp 3.14, pypdf 6.13, and sentence-transformers 5.x
(verified same vectors for all-MiniLM-L6-v2, so stored embeddings in
CockroachDB stay valid)."
```

Adjust the version numbers in the body to whatever Step 6 actually shows.

---

### Task 3: Automated test gate

**Files:** none modified (unless a dep needs pinning back)

**Interfaces:**
- Consumes: the preflight branch state from Task 2.
- Produces: a green `make test-local` run that Task 5 (merge) depends on.

- [ ] **Step 1: Start CockroachDB**

```bash
docker compose up -d cockroachdb
export DATABASE_URL=cockroachdb://root@localhost:26257/banko_ai
```

- [ ] **Step 2: Run the full local gate**

Run: `make test-local`
Expected: ruff clean, mypy clean, pytest green (integration tests that need a populated DB self skip if the data is not there).

- [ ] **Step 3: If a single dep broke something, pin it back**

Procedure, not optional wording: find the offending package from the traceback, add an upper bound in `pyproject.toml` at its last good major, rerun `uv lock --upgrade && uv sync --extra dev && make test-local`, then amend the Task 2 Step 8 commit and mention the pin and why in the body.

```bash
git add pyproject.toml uv.lock
git commit --amend
```

---

### Task 4: Five provider smoke

**Files:** none

**Interfaces:**
- Consumes: green gate from Task 3, provider credentials in the shell environment.
- Produces: the human sign off required before merging.

- [ ] **Step 1: Scripted provider pass**

Run: `uv run python tests/test_all_providers.py`
Expected: watsonx, OpenAI, Bedrock, and Gemini sections pass (it skips providers whose env vars are missing; none should skip, since all creds are available).

- [ ] **Step 2: Ollama up for the airgap path**

```bash
ollama list | grep granite3.3 || ollama pull granite3.3:8b
```

- [ ] **Step 3: Boot the app against each provider in turn**

For each of `watsonx openai aws gemini ollama`:

```bash
AI_SERVICE=<provider> uv run banko-ai run &
sleep 8
curl -s -X POST http://localhost:5000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "How much did I spend on coffee last month?"}' | head -c 400
kill %1
```

Expected per provider: an HTTP 200 with a coherent expense answer, no traceback in the app log. Remember `aws` is the Bedrock value, never `bedrock`.

- [ ] **Step 4: Human checklist (Virag drives, app running under the default provider)**

There is no committed smoke checklist yet (docs/coach-smoke-checklist.md is still a planned artifact), so this is the pass list:

1. Chat query returns a grounded answer with expense figures.
2. Provider switcher shows the right logo for the active `AI_SERVICE`.
3. Receipt upload extracts merchant, date, and amount (tesseract on PATH).
4. Agent dashboard activity feed shows the real events from steps 1 and 3.
5. `/api/cache/stats` shows hits climbing on a repeated query.
6. Vector search returns relevant expenses for a semantic query.
7. App boots clean with `AI_SERVICE=ollama` and answers offline.
8. No errors in the server log across the session.

Pause here for Virag's go ahead before Task 5.

---

### Task 5: Merge to main, push, close the PR pile

**Files:** none (merge only)

**Interfaces:**
- Consumes: Virag's sign off from Task 4.
- Produces: origin/main containing the batch; dependabot PRs closing.

- [ ] **Step 1: Merge**

```bash
git switch main
git merge --no-ff chore/preflight-housekeeping
```

Keep the default merge message. Expected: clean merge, no conflicts (preflight is a descendant of local main).

- [ ] **Step 2: Push main**

Run: `git push origin main`
Expected: origin/main moves from f67f308 to the merge commit (this also publishes the CLAUDE.md commit c87b076).

- [ ] **Step 3: Let dependabot react, then sweep the leftovers**

Wait a few minutes, then:

```bash
gh pr list --repo cockroachlabs-field/banko-ai-assistant --state open
```

For each dep PR still open (dependabot usually closes its own once main is current):

```bash
gh pr close <N> --repo cockroachlabs-field/banko-ai-assistant \
  --comment "Superseded by the dependency batch that just landed on main."
```

Close Backline #36 the same way (the sentence-transformers jump it asked for is in the batch).

- [ ] **Step 4: Verify**

Run: `gh pr list --repo cockroachlabs-field/banko-ai-assistant --state open`
Expected: zero dependency PRs remaining.

---

### Task 6: Rebase the coach branch onto the new main

**Files:**
- Conflict candidates: `pyproject.toml`, `uv.lock`, `banko_ai/config/settings.py`, `banko_ai/web/app.py`, `banko_ai/utils/migration.py`, `CLAUDE.md`, `README.md`

**Interfaces:**
- Consumes: the merged main from Task 5.
- Produces: `feat/coach-core-v1a` rebased, tested, and force pushed with lease.

- [ ] **Step 1: Rebase**

```bash
git switch feat/coach-core-v1a
git rebase main
```

- [ ] **Step 2: Resolve conflicts with these rules**

- `pyproject.toml`: keep main's version of everything, plus the coach branch's `kafka-python>=2.0.0,<3.0.0` line in dependencies.
- `uv.lock`: do not hand merge. Take main's side, then regenerate:

```bash
git checkout --ours uv.lock
uv lock
git add uv.lock
```

(During a rebase, `--ours` is main's side.)
- `settings.py`, `app.py`, `migration.py`, `CLAUDE.md`, `README.md`: keep both sides' intent; coach additions layer on top of preflight's fixes. Read each hunk, do not bulk resolve.

- [ ] **Step 3: Run the coach suite plus the full gate**

```bash
uv sync --extra dev
uv run pytest tests/coach/ tests/test_coach_migrations.py -v
make test-local
```

Expected: green. The coach code has never run against langchain 1.3 or sentence-transformers 5.x, so failures here are real information; fix forward in `banko_ai/coach/` if small, otherwise note and stop for discussion.

- [ ] **Step 4: Push the rebased backup**

Run: `git push --force-with-lease origin feat/coach-core-v1a`

---

### Task 7: CLAUDE.md refresh and wrap up

**Files:**
- Modify: `CLAUDE.md` (on main)

**Interfaces:**
- Consumes: everything landed.
- Produces: docs matching reality; the "easily maintainable in the future" ask.

- [ ] **Step 1: Update CLAUDE.md on main**

```bash
git switch main
```

Edits, keeping the existing voice and section layout:
- Open bugs: remove the SECRET_KEY drift and DROP TABLE interpolation entries (both fixed by preflight), keep the other three.
- Tech stack: sentence-transformers is now 5.x; the deprecated vertexai SDK is gone (google-genai covers Vertex).
- Testing section: note the smoke checklist file does not exist yet and point at the pass list in this plan until Coach v1 ships it.
- Add one line to Active design docs: the 2026-07-15 dependency upgrade spec, marked landed.
- Note where Coach v1 lives: `feat/coach-core-v1a`, rebased onto main July 2026, fate undecided.

- [ ] **Step 2: Commit and push**

```bash
git add CLAUDE.md
git commit -m "docs: bring CLAUDE.md up to date after the dependency landing

The SECRET_KEY and DROP TABLE fixes shipped with preflight, so they come
off the open bugs list. Also notes the sentence-transformers 5.x state,
the vertexai SDK removal, and where the coach branch stands."
git push origin main
```

- [ ] **Step 3: Final sweep**

```bash
gh pr list --repo cockroachlabs-field/banko-ai-assistant --state open
git branch -vv
```

Expected: no dependency PRs open, all three branches in sync with their remotes, working tree clean.
