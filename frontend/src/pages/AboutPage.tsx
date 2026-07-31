import aboutMd from "@site-docs/about.md?raw";
import { APP_VERSION } from "../version";
import SiteDocMarkdown from "../components/SiteDocMarkdown";

export default function AboutPage() {
  return (
    <div style={{ maxWidth: 760 }}>
      <SiteDocMarkdown source={aboutMd} file="about.md" className="card" />
      <p className="muted" style={{ fontSize: "0.9rem", marginTop: "1.25rem" }}>
        CommercialBrainz v{APP_VERSION}
      </p>
    </div>
  );
}
