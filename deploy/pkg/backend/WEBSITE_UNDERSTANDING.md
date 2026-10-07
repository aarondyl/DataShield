# Website Product Understanding

`POST /v1/analyze-website` accepts `{"url":"https://example.com","max_depth":2,"max_pages":30}`
and an optional `product_description`. It returns HTTP 202, an analysis ID and PENDING status.
`GET /v1/website-analysis/{id}` returns RUNNING, COMPLETED with `website_analysis`, or FAILED.
Both endpoints also have `/api/v1` aliases for the existing frontend proxy.

Configure `UNDERSTANDING_API_KEY` and send `Authorization: Bearer <key>` for both calls. No key disables
the endpoints. This is an internal service-key boundary, not multi-tenant user authentication. Never
place this key in frontend code. Use tenant-aware authorization and rate limits before public deployment.

Jobs and structured results use an additive `product_understanding_jobs` SQLAlchemy table in the configured
application database, created at first use. BackgroundTasks is an MVP in-process executor for a long-lived
server; it is not a durable queue. After 15 minutes, unfinished jobs are marked FAILED on retrieval.
Database persistence depends on the deployment: ephemeral Vercel SQLite is not durable. A production
serverless deployment needs a persistent database and durable job executor.

The crawler fetches public HTML only, up to 30 pages and depth 2, with a 60-second crawl deadline,
8-second socket timeouts and 512 KB page limit. DNS uses the host resolver's timeout. Each destination's
DNS answers must all be public IP addresses. The socket connects directly to the validated address;
HTTPS still verifies the original hostname. No proxies, cookies, automatic redirects, JavaScript,
login, form submission or SDK execution are used. Redirects stay on the original host and cannot downgrade
HTTPS; private, loopback, link-local, mapped IPv6 and nonstandard-port destinations are blocked. URLs with
queries/credentials/suspicious secret paths are rejected. GET-only crawling cannot guarantee an arbitrary
server has no GET side effects; common action paths are excluded. Only important public pages are followed.

Source text, script contents, input values, request descriptions and raw error details are never returned
or persisted. Evidence links to visited pages. Public statements are PARTIAL clues; HTML input controls
can establish PRESENT UI evidence without proving a working backend. A document requires a fetched heading,
not merely a footer link. Missing pages/limits yield UNKNOWN; NOT_DETECTED applies only to inspected pages.
Confidence values are heuristics. Market clues are not legal jurisdiction decisions. No legal judgment or
Product Digital Twin mutation is performed. Category conflicts yield UNKNOWN.

The shared schemas export `WebsiteAnalysisResult`, `RepoAnalysisResult`, `Evidence` and `AnalysisConflict`.
`find_conflicts(repo, website)` retains both sources for User Agent resolution. The repository analyzer
is implemented separately on `feat/repo-analyzer`; merge both branches to enable all four endpoints.

Run `python -m pytest tests -q` from `backend`. Fixtures cover crawl boundaries, private IPs, redirects,
DNS pinning, hidden content, documents, evidence and asynchronous API state.
