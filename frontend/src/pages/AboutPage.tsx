import { APP_VERSION } from "../version";
import SiteDocPage from "./SiteDocPage";

export default function AboutPage() {
  return (
    <>
      <SiteDocPage docId="about" />
      <p className="muted" style={{ fontSize: "0.9rem", marginTop: "1.25rem", maxWidth: 760 }}>
        CommercialBrainz v{APP_VERSION}
      </p>
    </>
  );
}
