import { Navigate } from "react-router";
import SiteDocMarkdown from "../components/SiteDocMarkdown";
import { SITE_DOC_SOURCES } from "../siteDocSources";
import { SITE_DOCS, type SiteDocId } from "../siteDocs";

type Props = {
  docId: SiteDocId;
};

/** Renders one docs/site Markdown page (mirrored from GitHub). */
export default function SiteDocPage({ docId }: Props) {
  const meta = SITE_DOCS.find((d) => d.id === docId);
  const source = SITE_DOC_SOURCES[docId];
  if (!meta || source == null) {
    return <Navigate to="/help" replace />;
  }

  return (
    <div style={{ maxWidth: 760 }}>
      <SiteDocMarkdown source={source} file={meta.file} className="card" />
    </div>
  );
}
