import aboutMd from "@site-docs/about.md?raw";
import apiMd from "@site-docs/api.md?raw";
import basicUsageMd from "@site-docs/basic-usage.md?raw";
import becomeAModMd from "@site-docs/become-a-mod.md?raw";
import dmcaMd from "@site-docs/dmca.md?raw";
import donateMd from "@site-docs/donate.md?raw";
import helpMd from "@site-docs/help.md?raw";
import termsOverviewMd from "@site-docs/terms-overview.md?raw";
import type { SiteDocId } from "./siteDocs";

/** Raw Markdown bundled at build time from docs/site/. */
export const SITE_DOC_SOURCES: Record<SiteDocId, string> = {
  about: aboutMd,
  help: helpMd,
  donate: donateMd,
  "terms-overview": termsOverviewMd,
  dmca: dmcaMd,
  "basic-usage": basicUsageMd,
  api: apiMd,
  "become-a-mod": becomeAModMd,
};
