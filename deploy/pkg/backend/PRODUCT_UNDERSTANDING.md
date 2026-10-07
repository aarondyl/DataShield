# Product Understanding Engine

This module observes product facts. It does not interpret laws, generate compliance findings,
modify analyzed repositories, or write a Product Digital Twin. `schemas.py` exports
`RepoAnalysisResult`, `WebsiteAnalysisResult`, `Evidence`, and `AnalysisConflict`.
`find_conflicts(repo, website)` preserves both values and evidence references without selecting a winner.

## Configuration and access

Set `UNDERSTANDING_API_KEY` in the server environment. Both submissions and result reads require
`Authorization: Bearer <key>`. Missing configuration disables the API with 503. Use a dedicated
service key per trusted deployment; this MVP service-key boundary is not multi-tenant user authentication.
Do not expose the service key in browser frontend code. Existing backend routes are unaffected.

Set `UNDERSTANDING_REPOSITORY_ROOTS` to an OS-path-separator-delimited allowlist of repository directories
(semicolon on Windows, colon on Linux). No directories are allowed by default. Mount analyzed repositories
read-only with restrictive filesystem permissions. Symlinks, Windows junctions, hardlinked files, sensitive
paths and generated files are skipped or rejected. Do not scan an actively hostile, concurrently modified
filesystem; platform path APIs cannot provide a fully race-free sandbox across operating systems.

## Repository API

`POST /v1/analyze-repository` returns HTTP 202 and a PENDING `AnalysisJob`:

```json
{"repository_path":"/mounted/product","analysis_mode":"SELECTED_PATHS","selected_paths":["src","package.json"],"product_description":"Optional product description"}
```

Modes: FULL reads eligible non-sensitive files; SELECTED_PATHS restricts traversal to the exact selections;
METADATA_ONLY (default) reads explicitly allowlisted manifests, README and metadata files; NO_REPOSITORY
performs no filesystem operations and can extract low-confidence user-described clues.

`GET /v1/repository-analysis/{analysis_id}` returns the stored job with `repository_analysis` on completion.
The `/api/v1/...` aliases support the existing frontend proxy. Evidence contains relative file names and
line numbers, never source snippets. Dependency findings do not prove that an SDK is used at runtime.
Feature/capability regex matches are PARTIAL clues; NOT_DETECTED applies only to the examined scope and
never asserts absence. Limited/unreadable scans return UNKNOWN for missing findings.

## Storage and execution

Jobs use the configured application SQLAlchemy database in a separate additive `product_understanding_jobs`
table created on first API access. PENDING/RUNNING/COMPLETED/FAILED and structured results persist across
processes when the configured database is durable. SQLite on ephemeral Vercel storage is not durable.
MVP execution uses FastAPI BackgroundTasks in the serving process; use a long-lived server. There is no
durable queue or automatic retry. An unfinished job older than 15 minutes is reported FAILED on retrieval.
Production serverless workers should replace the task runner with a durable queue while keeping the contracts.
Inputs, credentials, raw source, raw HTML and exception text are not stored. Add tenant authentication,
rate limiting and result retention appropriate to your deployment before exposing this internal API publicly.

## Validation

Run `python -m pytest tests/test_understanding_contracts.py tests/test_repository_understanding.py -q`
from `backend`, then the full backend suite. Confidence values are transparent deterministic heuristics,
not calibrated statistical probabilities. The optional description is recorded as USER_DESCRIPTION clues,
not verified implementation facts. Scope evidence documents non-detection limitations.
