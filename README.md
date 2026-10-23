# Orthodox Prayer Library backend

Public API: [prayerlife.copticfaith.org](https://prayerlife.copticfaith.org/) · [Interactive API docs](https://prayerlife.copticfaith.org/docs) · [Health](https://prayerlife.copticfaith.org/health)

A self-hosted, read-only FastAPI library with Arabic and English editions of Matthew the Poor's *Orthodox Prayer Life*. It supports multiple books; the supplied sources populate one book in two editions. The Arabic app contains HTML rather than a pre-existing database. The English source is a Kindle ebook, converted with Calibre to EPUB without changing the original.

## What is included

- SQLite database, stable content IDs, hierarchical contents, headings, ordered passages, extracted sayings, source locations, and source hashes.
- Books → editions → parts/chapters → sections → passages/quotes.
- Arabic and English full-text search. Arabic search ignores diacritics, tatweel, and common alef/ya variants.
- Parent breadcrumbs, sibling links, and `reading_previous` / `reading_next` links across chapter boundaries. English contents retain the publisher's nested navigation and jump anchors.
- Structural links between corresponding chapters. **The editions differ.** Arabic includes additional chapters, an entire fourth part, biographies, and summaries. Links do not assert paragraph or quotation equivalence.
- Arabic Van Dyke Bible: 66 books, 1,189 chapters, 31,104 verses. Original downloaded JSON, normalized JSONL, hashes, repository revision, and public-domain provenance are in `data/` alongside the library database.
- Bible citation extraction with review states and an editable CSV queue. `validated` means the parsed reference exists in the imported Bible; `needs_review` identifies ambiguous notation. It does not certify the book's quotation matches that translation word for word.
- NKJV support in the schema, importer, and parallel endpoint. **NKJV text is not bundled.** Use a licensed NKJV source; never relabel KJV as NKJV. [API.Bible](https://www.api.bible/) offers NKJV access, including a free noncommercial plan subject to its terms. There is no configured live API integration in this package.

Quotes are extraction candidates. Numbered sayings are retained with source passages; attribution is explicitly unresolved or a candidate. Original spellings and source typos are preserved. Inferred author names and sentence translations are not invented. Bible references that the current parser does not recognize remain in the original passages; the extracted reference index is not a certified exhaustive concordance. Van Dyke's 66-book canon does not include deuterocanonical books.

## Run locally

Requires Python 3.13 or newer (tested with Python 3.14).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` for interactive API documentation or `/openapi.json` for the machine-readable schema. No frontend website is included. Any website can consume the JSON API; CORS permits all origins by default, without credentials. Set `CORS_ORIGINS=https://one.example,https://two.example` to restrict origins.

## Deploy on your own server

Copy this directory to the server, excluding `.venv`, caches, and `source/`. Install Docker Engine with Compose on that server.

```bash
docker compose up -d --build
curl http://127.0.0.1:8000/health
```

For HTTPS, point your API domain's DNS to the server and allow TCP ports 80 and 443. Then:

```bash
API_DOMAIN=api.yourdomain.example docker compose -f compose.yaml -f compose.proxy.yaml up -d --build
```

Caddy obtains and renews HTTPS certificates. Do not use the example domain literally. If the server already runs a reverse proxy, use `compose.yaml` alone and proxy to localhost port 8000. This package does not replace an existing proxy. The API container runs as a non-root user with a read-only database mount and filesystem.

Back up `data/library.sqlite3` and the source manifests before updates. Import/rebuild operations happen offline; replace the database and restart the API when ready. Restarting recreates no data. The Docker image has been built and deployed successfully on Coolify; Docker is unavailable in the local workspace.

## API examples

| Route | Purpose |
|---|---|
| `GET /v1/books` | Library books |
| `GET /v1/books/orthodox-prayer-life` | Book and editions |
| `GET /v1/editions/ar/toc` | Arabic nested contents |
| `GET /v1/editions/en/toc` | English publisher contents, plus content file list |
| `GET /v1/sections/ar:1:003` | Children, breadcrumbs, previous/next and bilingual chapter links |
| `GET /v1/sections/ar:1:003/passages?limit=50&offset=0` | Ordered source text and Bible references |
| `GET /v1/sections/en:nav:num_8` | Resolve an English contents entry to a content section and jump offset |
| `GET /v1/quotes?edition_id=ar&limit=30&offset=0` | Paginated sayings |
| `GET /v1/quotes/{id}` | Saying with its source passages and references |
| `GET /v1/search?q=prayer&edition_id=en` | Search passages; optional book filter |
| `GET /v1/bible/AVD/John/3/16` | Full Arabic verse |
| `GET /v1/bible/AVD/John/3` | Full Arabic chapter |
| `GET /v1/bible-parallel?book_code=John&chapter=3&verse_start=16` | NKJV / Van Dyke side by side, with explicit availability |
| `GET /v1/bible/references?status=needs_review` | Citation review queue |
| `GET /v1/bible/books` | Available Bible books and chapter counts |
| `GET /v1/bible/translations` | Available/missing translations |
| `GET /v1/status` | Extraction counts and source status |

Use OSIS book codes, e.g. `Gen`, `Ps`, `Matt`, `John`, `1Cor`. Read the actual IDs returned by the contents endpoint rather than constructing navigation IDs. Pagination uses `limit` and `offset` and returns `total`. Reference and verse text are plain strings; render using `textContent` or your framework's normal escaped text rendering.

```javascript
const base = 'https://prayerlife.copticfaith.org';
const results = await fetch(`${base}/v1/search?` + new URLSearchParams({
  q: 'الصلاة', edition_id: 'ar'
})).then(response => {
  if (!response.ok) throw new Error(`API error ${response.status}`);
  return response.json();
});
```

## Rebuild from the original sources

Keep the original XAPK and Kindle ebook. Convert the English ebook using Calibre:

```bash
ebook-convert /path/to/english.azw3 source/english.epub
.venv/bin/python scripts/build_database.py --xapk /path/to/book.xapk --epub source/english.epub
.venv/bin/python -m scripts.import_bible data/arabic-vandyke.jsonl
.venv/bin/python -m scripts.export_review
```

Rebuilding replaces the database, including Bible imports and review edits. Back it up first. The `data/schema.sql` file documents the normalized schema.

Fetch the same pinned Van Dyke dataset again with `.venv/bin/python -m scripts.fetch_vandyke`. It verifies the source's public-domain designation and verse count, saves original book files and SHA-256 hashes, and imports the JSONL.

To import an authorized NKJV file, supply UTF-8 JSONL with one verse per line:

```json
{"translation":"NKJV","book_code":"John","chapter":3,"verse":16,"text":"YOUR LICENSED VERSE TEXT"}
```

```bash
.venv/bin/python -m scripts.import_bible /path/to/nkjv.jsonl
```

An import atomically replaces each translation present in the file. It validates structure, book/chapter identifiers, duplicates and nonempty verse text; it does not prove the file's translation identity or completeness. Preserve your license and source attribution alongside the file.

To review citations, edit `data/bible-reference-review.csv`, correct book/chapter/verse values, and set only explicitly checked rows to `reviewed`. Apply them with:

```bash
.venv/bin/python -m scripts.apply_reference_review data/bible-reference-review.csv
```

Unreviewed rows remain unchanged. Uncertain references never return guessed verse text.

## Validation

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

Tests cover source counts and SQLite integrity, contents target resolution, ordered passages, quote provenance, Arabic/English search, pagination, CORS, translation identity, missing NKJV data, and withholding uncertain citations. See `VERIFICATION.md` for the delivery checks and remaining dependencies.


## Production hosting

Production runs on **AboHub (`155.248.209.35`)**, managed by the existing
[Coolify dashboard](https://hub.copticfaith.org). See [DEPLOYMENT.md](DEPLOYMENT.md)
for the deployment branch, application UUID, GitHub updates, data, and recovery.
