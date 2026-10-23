# Delivery verification

Validated on October 22, 2026 (America/Los_Angeles), with Python 3.14.

- Nine integration tests pass against the delivered SQLite database.
- SQLite integrity check passes, with no foreign-key violations.
- All 167 Arabic source HTML files and all 28 English EPUB spine documents were compared with the extracted passages. Visible text matches after whitespace normalization, with zero mismatches. No Unicode replacement characters were introduced. This comparison checks the converted EPUB, not the original Kindle binary.
- English edition contains 16 chapters. Arabic content retains all six source groups, including extra chapters and supplements.
- Delivered database: 339 section/navigation records, 6,769 passages, 1,724 numbered quote candidates, 65 structural chapter links, and 1,045 recognized Bible-reference candidates.
- Van Dyke: 66 Bible books and 31,104 verses downloaded from a pinned public-domain GitHub dataset. Source metadata, checksums, and original files are retained in `data/`.
- Of the recognized references, 220 currently validate against available Bible data, 433 require notation review, and 392 remain candidates. An exported CSV provides source context for review. English citations cannot be validated against NKJV until its data is supplied. The original Bible citations remain in the book text even when unrecognized by the parser.
- Actual HTTP checks returned 200 for `/health`, `/docs`, `/openapi.json`, Arabic search, cross-chapter navigation, and parallel Bible lookup. API responses are backed by the delivered database. Missing NKJV data is reported explicitly.
- Live Swagger documentation rendered successfully in Chrome at `https://prayerlife.copticfaith.org/docs`. A delivery screenshot is retained locally as `live-api.png`.
- Coolify built the Docker image successfully and completed deployment `thxafki0dyatjwbzxtqvaxvc` from runtime commit `6520981`. The container passed its health check. HTTPS works through the existing Cloudflare proxy.
- Public GitHub repository: `https://github.com/boco-cyber/orthodox-prayer-life`. Public API: `https://prayerlife.copticfaith.org`. Added a separate Coolify project/application and the requested DNS subdomain. Public HTTPS checks returned 200 for health, books, Arabic/English contents and search, quotes, Arabic Bible text, status, and docs; all returned the expected CORS header.

Remaining editorial work: review ambiguous citations and quote attributions; verify paragraph/quote translations before presenting them as exact bilingual pairs. Remaining external dependency: an authorized NKJV dataset or licensed API access.
