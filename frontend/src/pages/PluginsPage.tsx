type RelatedLink = {
  label: string;
  url: string;
  description: string;
};

type PluginListing = {
  id: string;
  name: string;
  summary: string;
  requirements: string;
  repoUrl: string;
  installHint: string;
  note?: string;
  relatedLinks?: RelatedLink[];
};

const PLUGINS: PluginListing[] = [
  {
    id: "jellyfin",
    name: "Jellyfin",
    summary:
      "Native Jellyfin metadata provider. Install from the CommercialBrainz plugin repository or a release zip.",
    requirements: "Jellyfin 12.0+, ffmpeg/ffprobe; optional fpcalc for audio matching",
    repoUrl: "https://github.com/binarygeek119/CommercialBrainz-jellyfin-plugin",
    installHint:
      "Dashboard → Plugins → Repositories → add the CommercialBrainz manifest, then install from Catalog.",
    relatedLinks: [
      {
        label: "Jellyfin+",
        url: "https://github.com/binarygeek119/jellyfinplus",
        description:
          "Docker image based on jellyfin/jellyfin:unstable with yt-dlp and fpcalc bundled for CommercialBrainz YouTube streaming and audio fingerprinting.",
      },
    ],
  },
  {
    id: "plex",
    name: "Plex",
    summary:
      "HTTP custom metadata provider for Plex Media Server. Run the provider (Docker or local), then add it as a metadata agent.",
    requirements: "Plex Media Server 1.43.0+",
    repoUrl: "https://github.com/binarygeek119/Plex-CommercialBrainz-Plugin",
    installHint:
      "Start the provider, then Settings → Troubleshooting → Metadata Agents → Add Provider.",
  },
  {
    id: "emby",
    name: "Emby",
    summary:
      "Emby metadata provider (port of the Jellyfin plugin). Install from a release zip into Emby’s plugins folder.",
    requirements: "Emby Server 4.9+, ffmpeg/ffprobe; optional fpcalc",
    repoUrl: "https://github.com/binarygeek119/Emby-CommercialBrainz-Plugin",
    installHint:
      "Extract the release zip into Emby’s plugins folder, restart, then enable CommercialBrainz on your library.",
    note: "Emby support is untested against a live server; builds and unit tests pass.",
  },
];

export default function PluginsPage() {
  return (
    <div>
      <h1 className="page-title">Media server plugins</h1>
      <p className="muted" style={{ maxWidth: 720, marginTop: "-0.75rem", marginBottom: "1.5rem" }}>
        Match commercial files in your library to CommercialBrainz using file SHA-256, Chromaprint,
        video pHash, or title search. Pick your media server below for install instructions and
        source.
      </p>

      <div className="stack">
        {PLUGINS.map((plugin) => (
          <section key={plugin.id} className="card" aria-labelledby={`plugin-${plugin.id}`}>
            <div className="flex-between" style={{ alignItems: "flex-start" }}>
              <div style={{ minWidth: 0, flex: 1 }}>
                <h2 id={`plugin-${plugin.id}`} style={{ margin: "0 0 0.5rem" }}>
                  {plugin.name}
                </h2>
                <p style={{ margin: "0 0 0.75rem" }}>{plugin.summary}</p>
                <p className="muted" style={{ margin: "0 0 0.5rem", fontSize: "0.9rem" }}>
                  <strong>Requires:</strong> {plugin.requirements}
                </p>
                <p className="muted" style={{ margin: 0, fontSize: "0.9rem" }}>
                  <strong>Install:</strong> {plugin.installHint}
                </p>
                {plugin.note ? (
                  <p className="muted" style={{ margin: "0.75rem 0 0", fontSize: "0.9rem" }}>
                    {plugin.note}
                  </p>
                ) : null}
                {plugin.relatedLinks && plugin.relatedLinks.length > 0 ? (
                  <div style={{ marginTop: "1rem" }}>
                    <h3 style={{ margin: "0 0 0.5rem", fontSize: "0.95rem" }}>Also useful</h3>
                    <ul style={{ margin: 0, paddingLeft: "1.1rem" }}>
                      {plugin.relatedLinks.map((link) => (
                        <li key={link.url} style={{ marginBottom: "0.5rem" }}>
                          <a href={link.url} target="_blank" rel="noreferrer noopener">
                            {link.label}
                          </a>
                          <span className="muted" style={{ display: "block", fontSize: "0.9rem" }}>
                            {link.description}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
              <a
                href={plugin.repoUrl}
                className="btn btn-primary"
                target="_blank"
                rel="noreferrer noopener"
                style={{ flexShrink: 0 }}
              >
                GitHub
              </a>
            </div>
          </section>
        ))}
      </div>

      <p className="muted" style={{ marginTop: "1.5rem", fontSize: "0.9rem", maxWidth: 720 }}>
        Matching uses the public hash lookup and search APIs. See{" "}
        <a href="/docs" target="_blank" rel="noreferrer">
          API docs
        </a>{" "}
        for details.
      </p>
    </div>
  );
}
