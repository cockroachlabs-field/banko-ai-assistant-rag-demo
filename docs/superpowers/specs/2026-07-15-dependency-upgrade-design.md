# Dependency upgrade and preflight landing

2026-07-15. Status: approved, pending implementation.

## Where things stand

The GitHub repo has 21 open PRs: 18 dependabot bumps for Python deps, 2 for GitHub
Actions, and one Backline security PR for sentence-transformers. None of them have
been touched since May.

Meanwhile, two branches from the May sessions exist only on this laptop:

- `chore/preflight-housekeeping` (12 commits, May 21-22): a batched dependabot
  upgrade plus real fixes. Makefile baseline, the SECRET_KEY prod fix, parameterized
  DROP TABLE identifiers, receipt OCR validation, watsonx model discovery caching,
  AWS Bedrock parameter fixes, the Gemini migration off the deprecated vertexai SDK,
  and a CLAUDE.md refresh. The two "open bugs" CLAUDE.md still lists (SECRET_KEY
  drift, DROP TABLE interpolation) are already fixed here.
- `feat/coach-core-v1a` (15 commits, May 22): Coach v1 feature code, about 3,000
  lines. Not part of this effort beyond keeping it safe.

Both branch off local main at c87b076 (the commit that added CLAUDE.md), which was
also never pushed. origin/main is one commit behind local main and knows nothing
about any of this.

So the open dependabot PRs are bumps that piled up since the May batch. Landing
preflight with a refreshed batch supersedes all of them.

## The plan

### 1. Back everything up before touching anything

Commit the loose working tree files (README edit, docs/superpowers/) to the coach
branch where they belong, then push both local branches to origin as plain branches,
no PRs. After this step nothing exists only on one machine.

### 2. Refresh the dep batch on chore/preflight-housekeeping

Update pyproject.toml constraints to cover what the open PRs ask for, then let
`uv lock --upgrade` bring the lockfile current in one pass instead of replaying 18
individual bumps. Notable constraint changes:

- sentence-transformers: `<4.0.0` to `<6.0.0`. Two majors, but the model weights
  (all-MiniLM-L6-v2) do not change, so stored 384-dim vectors should be identical.
  We verify that rather than assume it (see test gate).
- gunicorn: ceiling from `<24.0.0` to `<27.0.0`.
- Everything else stays within existing constraints; the lock refresh picks up the
  new versions (langchain 1.3.x, langchain-core 1.3.x, langsmith 0.8.x,
  cryptography 48, aiohttp 3.14, pypdf 6.13, and the rest).

Also bump the two GitHub Actions in the workflow files: actions/checkout to v7 and
softprops/action-gh-release to v3.

### 3. Test gate, in order

1. `make test-local` (unit, integration, eval with mock judge, ruff, mypy).
2. Embedding parity: encode a few fixed strings with the upgraded
   sentence-transformers and compare against vectors already stored in CockroachDB.
   Cosine similarity should be 1.0 within float tolerance. If parity fails, pin
   sentence-transformers back to `<4.0.0`, note it in the commit body, and move on.
3. Boot the app and smoke all five providers: watsonx, OpenAI, AWS Bedrock, Gemini,
   Ollama. Claude drives the automatable parts.
4. Virag runs the 14-item human checklist (docs/coach-smoke-checklist.md).

Any single dep that breaks the suite gets pinned back to its last good version in
the same commit, with a note in the commit body. The batch still lands.

### 4. Land and clean up

Merge chore/preflight-housekeeping into main and push. Dependabot closes its own
PRs once main is current; close stragglers and the Backline PR by hand with a short
comment. Then rebase feat/coach-core-v1a onto the new main (expected conflict
surface: settings.py, app.py, migration.py, uv.lock), run the coach test suite, and
force-push the backup branch.

### 5. CLAUDE.md refresh

Preflight already updates the open-bugs section. After landing, do one more pass so
CLAUDE.md matches reality: dep state as of July 2026, where the coach branch lives
and what is in it, and which bugs actually got fixed.

## Out of scope

What happens to Coach v1 (finish it, merge it, park it) is a separate decision for
a separate session. This effort only keeps the branch safe and rebased.
