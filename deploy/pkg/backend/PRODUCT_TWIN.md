# Product Twin MVP

Product Twin is an append-only record of observed product facts. It does not make
legal judgments, create findings or actions, change source code, or copy clues
into the existing `products` boolean columns. Existing product and analysis APIs
continue to use those columns unchanged.

## Setup and access

Run `alembic upgrade head` before starting a persistent deployment. Migration
`0005` adopts the existing `product_understanding_jobs` table if present and
adds the Product Twin tables. SQLite development uses the same migration.

Set `UNDERSTANDING_API_KEY` on the server. Every endpoint below requires
`Authorization: Bearer <key>`. This shared key is **not tenant or user identity**:
`company_id` and `product_id` are checked for a valid relationship, but the key
holder can name any company. `actor_label` is an unverified audit label. Do not
put the key in frontend code or expose these internal APIs to untrusted clients.
Tenant authentication, per-product authorization, rate limiting, retention and a
durable background queue remain necessary before public multi-tenant use.

## Flow

1. Submit `POST /v1/analyze-repository` or `POST /v1/analyze-website` with both
   `company_id` and `product_id` in the existing request body. The pair is
   optional for old clients; unlinked legacy jobs cannot be attached to a Twin.
2. Poll the corresponding existing result endpoint until `COMPLETED`.
3. Attach the result to the product with
   `POST /v1/products/{product_id}/twin/analyses`:

   ```json
   {"company_id":1,"analysis_id":"<completed job ID>","kind":"website"}
   ```

   Attachment copies the completed structured result into an immutable analysis
   reference and creates a new Product Twin version. The copy has a SHA-256 digest
   and can be read through `GET /v1/products/{product_id}/twin/analysis-refs/{analysis_id}?company_id=1`.
   Attaching the same job twice is rejected. Evidence IDs are prefixed with the
   analysis ID, for example `<analysis_id>:ev_0001`.

4. Read the current snapshot with `GET /v1/products/{product_id}/twin?company_id=1`,
   list history with `/versions?company_id=1`, or read a numbered snapshot with
   `/versions/{version_number}?company_id=1`.
5. Add a user observation with `POST /v1/products/{product_id}/twin/facts`:

   ```json
   {"company_id":1,"group":"features","fact":{"name":"login","status":"PRESENT","confidence":0.9},"note":"Observed in product walkthrough"}
   ```

6. Confirm a fact at `/facts/{fact_id}/confirm` with `company_id`, optional
   `note` and `actor_label`, or correct it at `/facts/{fact_id}/correct` with
   those fields plus a `fact` object. Only IDs in the current version can be
   decided. A correction retains the original observation as `CORRECTED` and
   appends a confirmed user observation that points to its prior ID. Both
   actions create a new snapshot and decision record.

All routes also have `/api/v1` aliases. Facts preserve their analyzer status,
confidence, scan scope and evidence. `UNKNOWN` and `NOT_DETECTED` remain scoped
observations, not false values or compliance violations. Different sources stay
side by side; the response reports status discrepancies as conflicts and never
chooses a winner. Confidence values remain analyzer heuristics, not calibrated
probabilities.
