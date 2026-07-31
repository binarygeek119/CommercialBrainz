# Site documentation (mirrored on the web UI)

Markdown in this folder is the **source of truth** for public help pages on CommercialBrainz.
The React app imports these files at build time and renders them on the site.

| File | Site route |
|------|------------|
| [help.md](help.md) | `/help` |
| [basic-usage.md](basic-usage.md) | `/help/basic-usage` |
| [api.md](api.md) | `/help/api` |
| [become-a-mod.md](become-a-mod.md) | `/help/become-a-mod` |
| [about.md](about.md) | `/about` |
| [donate.md](donate.md) | `/donate` (copy; donation buttons stay in the app) |
| [terms-overview.md](terms-overview.md) | `/terms` (intro; versioned submission terms stay in the API) |
| [dmca.md](dmca.md) | `/dmca` (policy text; form stays in the app) |

## How to edit

1. Open the file on GitHub (or clone the repo).
2. Edit the Markdown.
3. Open a PR against the **`testing`** branch (default for all changes).
4. After merge + deploy, the site shows the new text.

Each mirrored page has an **Edit on GitHub** link that opens the file in the GitHub web editor.

## What does *not* live here

- **Submission Terms** (agree-to-submit gate) — versioned JSON in the database / API so acceptance can be tracked.
- **Interactive OpenAPI UI** — FastAPI at `/docs` (human API guide is [api.md](api.md)).
- **Ops / deploy notes** — sibling files under `docs/` (e.g. `branches.md`).
