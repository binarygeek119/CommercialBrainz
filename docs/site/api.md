# API for scrapers and apps

CommercialBrainz exposes a versioned JSON API under **`/api/v1`**. Interactive OpenAPI docs (try-it-out) live at **[/docs](/docs)**; the raw schema is at **`/openapi.json`**.

Database contents are released under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).

## Base URL

On the public site, call paths relative to the same host, for example:

```text
https://commercialbrainz.org/api/v1/...
```

(Testing: `https://commercialbrainz.duckdns.org/api/v1/...`.)

## Common endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /videos/{cbid}` | Video with nested commercial / advertiser |
| `GET /commercials/{cbid}` | Commercial with linked videos |
| `GET /advertisers/{cbid}` | Advertiser with commercials |
| `GET /search?query=&type=video` | Full-text search |
| `GET /browse/videos?...` | Filtered browse |
| `GET /edits/{id}` | Public edit history |
| `GET /hashes/types` | Media hash types |
| `GET /hashes` | Paginated video hashes |
| `GET /hashes/videos/{cbid}` | Hashes for a video CBID |
| `GET /hashes/youtube/{youtube_id}` | Hashes by YouTube ID |
| `GET /hashes/lookup?phash=` | Lookup by perceptual hash |
| `GET /hashes/lookup?file_sha256=` | Lookup by file SHA-256 |
| `POST /hashes/lookup` | Same lookups (use for long Chromaprint values) |
| `GET /dumps/latest` | Latest nightly dump metadata + download URL |

CBIDs are UUIDs used in site URLs and API paths (sometimes called SBID in older notes — same idea).

## Scraper etiquette

1. **Send a real User-Agent** with contact info, e.g. `YourApp/1.0 (contact@example.com)`.
2. **Respect rate limits**: about **1 request/second** anonymous, **5/s** when authenticated.
3. **Use ETags**: cache `ETag` and send `If-None-Match` for `304 Not Modified` when nothing changed.
4. **Prefer dumps for bulk**: start from `GET /api/v1/dumps/latest` instead of crawling every entity.

## Auth

Most read endpoints work anonymously (within rate limits). Write actions (submit edits, vote, account) need a logged-in session / bearer token from the auth endpoints — see [/docs](/docs).

## DMCA and hidden links

Valid DMCA notices can hide a YouTube link from public responses while keeping archival metadata. Do not treat a missing public link as “never existed.” Policy: [/dmca](/dmca).

## Related

- Live schema: [/docs](/docs)
- Source: [GitHub](https://github.com/binarygeek119/CommercialBrainz)
- [Using the site](/help/basic-usage)
