# Media server plugins

Match commercial files in your library to CommercialBrainz using file SHA-256, Chromaprint, video pHash, or title search. Install a metadata provider for your media server, then point it at the public API.

Matching uses the public [hash lookup](/help/api) and search APIs. Interactive OpenAPI is at [/docs](/docs).

## Jellyfin

Native Jellyfin metadata provider. Install from the CommercialBrainz plugin repository or a release zip.

- **Requires:** Jellyfin 12.0+, ffmpeg/ffprobe; optional fpcalc for audio matching
- **Source:** [CommercialBrainz-jellyfin-plugin](https://github.com/binarygeek119/CommercialBrainz-jellyfin-plugin)
- **Install:** Dashboard → Plugins → Repositories → add the CommercialBrainz manifest, then install from Catalog

### Also useful: Jellyfin+

[Jellyfin+](https://github.com/binarygeek119/jellyfinplus) is a Docker image based on `jellyfin/jellyfin:unstable` with **yt-dlp** and **fpcalc** bundled for CommercialBrainz YouTube streaming and audio fingerprinting.

```bash
docker pull ghcr.io/binarygeek119/jellyfinplus:unstable
```

## Plex

HTTP custom metadata provider for Plex Media Server. Run the provider (Docker or local), then add it as a metadata agent.

- **Requires:** Plex Media Server 1.43.0+
- **Source:** [Plex-CommercialBrainz-Plugin](https://github.com/binarygeek119/Plex-CommercialBrainz-Plugin)
- **Install:** Start the provider, then Settings → Troubleshooting → Metadata Agents → Add Provider

## Emby

Emby metadata provider (port of the Jellyfin plugin). Install from a release zip into Emby’s plugins folder.

- **Requires:** Emby Server 4.9+, ffmpeg/ffprobe; optional fpcalc
- **Source:** [Emby-CommercialBrainz-Plugin](https://github.com/binarygeek119/Emby-CommercialBrainz-Plugin)
- **Install:** Extract the release zip into Emby’s plugins folder, restart, then enable CommercialBrainz on your library

> **Note:** Emby support is untested against a live server; builds and unit tests pass. Pull requests welcome.
