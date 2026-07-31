/** Site docs live in docs/site/ and are mirrored into the web UI at build time. */

export const GITHUB_REPO = "https://github.com/binarygeek119/CommercialBrainz";
/** PRs and doc edits target the default integration branch. */
export const GITHUB_DOCS_BRANCH = "google";
export const SITE_DOCS_DIR = "docs/site";

export type SiteDocId = "about" | "dmca" | "terms-overview" | "donate" | "help";

export type SiteDocMeta = {
  id: SiteDocId;
  /** Filename under docs/site/ */
  file: string;
  title: string;
  route: string;
  /** Short blurb for the help index (optional). */
  summary?: string;
};

export const SITE_DOCS: SiteDocMeta[] = [
  {
    id: "about",
    file: "about.md",
    title: "About",
    route: "/about",
    summary: "What CommercialBrainz is and how to get involved",
  },
  {
    id: "help",
    file: "help.md",
    title: "Help",
    route: "/help",
    summary: "Index of site docs and how to edit them on GitHub",
  },
  {
    id: "donate",
    file: "donate.md",
    title: "Donate",
    route: "/donate",
    summary: "Domain, VM, cookies, and volunteering",
  },
  {
    id: "terms-overview",
    file: "terms-overview.md",
    title: "Terms overview",
    route: "/terms",
    summary: "Master/sub links and split rules (intro)",
  },
  {
    id: "dmca",
    file: "dmca.md",
    title: "DMCA policy",
    route: "/dmca",
    summary: "Takedown policy (form stays on the page)",
  },
];

export function githubBlobUrl(file: string): string {
  return `${GITHUB_REPO}/blob/${GITHUB_DOCS_BRANCH}/${SITE_DOCS_DIR}/${file}`;
}

export function githubEditUrl(file: string): string {
  return `${GITHUB_REPO}/edit/${GITHUB_DOCS_BRANCH}/${SITE_DOCS_DIR}/${file}`;
}
