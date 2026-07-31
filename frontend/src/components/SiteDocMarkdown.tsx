import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import { Link } from "react-router";
import { githubEditUrl } from "../siteDocs";

function isInternalPath(href: string | undefined): href is string {
  if (!href) return false;
  return href.startsWith("/") && !href.startsWith("//");
}

const markdownComponents: Components = {
  a({ href, children, ...rest }) {
    if (isInternalPath(href)) {
      return (
        <Link to={href} {...rest}>
          {children}
        </Link>
      );
    }
    return (
      <a href={href} target="_blank" rel="noreferrer noopener" {...rest}>
        {children}
      </a>
    );
  },
};

type Props = {
  /** Raw markdown from docs/site/*.md */
  source: string;
  /** Filename under docs/site/ for the Edit on GitHub link */
  file: string;
  className?: string;
  /** When false, hide the edit toolbar (rare). Default true. */
  showEditLink?: boolean;
};

/** Renders a docs/site markdown file and links to edit it on GitHub. */
export default function SiteDocMarkdown({
  source,
  file,
  className = "",
  showEditLink = true,
}: Props) {
  return (
    <div className={`site-doc ${className}`.trim()}>
      {showEditLink && (
        <p className="site-doc-edit muted">
          <a href={githubEditUrl(file)} target="_blank" rel="noreferrer noopener">
            Edit on GitHub
          </a>
          <span aria-hidden="true"> · </span>
          <span>Source: docs/site/{file}</span>
        </p>
      )}
      <div className="site-doc-body">
        <ReactMarkdown components={markdownComponents}>{source}</ReactMarkdown>
      </div>
    </div>
  );
}
