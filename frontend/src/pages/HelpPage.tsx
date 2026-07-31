import helpMd from "@site-docs/help.md?raw";
import SiteDocMarkdown from "../components/SiteDocMarkdown";

export default function HelpPage() {
  return (
    <div style={{ maxWidth: 760 }}>
      <SiteDocMarkdown source={helpMd} file="help.md" className="card" />
    </div>
  );
}
