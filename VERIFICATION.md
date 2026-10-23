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
- Browser rendering was not checked: the in-app browser is unavailable in this session. Swagger HTML and OpenAPI were checked over HTTP.
- Docker and HTTPS configuration are packaged but not executed here because Docker is unavailable.
- Server deployment awaits SSH connection details and an API domain. No public server was provisioned or modified.

Remaining editorial work: review ambiguous citations and quote attributions; verify paragraph/quote translations before presenting them as exact bilingual pairs. Remaining external dependency: an authorized NKJV dataset or licensed API access.
