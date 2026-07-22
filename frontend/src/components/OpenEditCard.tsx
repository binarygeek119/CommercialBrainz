import { Link } from "react-router-dom";
import type { Edit } from "../api";
import BrandLogoImage from "./BrandLogoImage";
import { isCatalogLogoEdit, catalogKindFromEditType } from "../catalog/kinds";
import { editTitle } from "../utils/editDisplay";
import { formatLogoContext } from "../utils/brandLogos";

function proposedLogoUrl(edit: Edit): string | null {
  const catalogKind = catalogKindFromEditType(edit.edit_type);
  const isLogoEdit =
    edit.edit_type === "add_advertiser_logo" ||
    edit.edit_type === "edit_advertiser_logo" ||
    edit.edit_type === "edit_advertiser" ||
    isCatalogLogoEdit(edit.edit_type) ||
    (catalogKind != null && edit.edit_type === catalogKind.editEdit);

  if (isLogoEdit && typeof edit.after_state.logo_url === "string") {
    return edit.after_state.logo_url;
  }
  if (
    (edit.edit_type === "edit_advertiser_logo" ||
      (catalogKind != null && edit.edit_type === catalogKind.editLogoEdit)) &&
    typeof edit.after_state.image_url === "string"
  ) {
    return edit.after_state.image_url;
  }
  return null;
}

export default function OpenEditCard({ edit }: { edit: Edit }) {
  const logoUrl = proposedLogoUrl(edit);
  const logoContext =
    edit.edit_type === "add_advertiser_logo" ||
    edit.edit_type === "edit_advertiser_logo" ||
    isCatalogLogoEdit(edit.edit_type)
      ? formatLogoContext(edit.after_state)
      : null;

  return (
    <Link
      to={`/edits/${edit.id}`}
      className="card"
      style={{ textDecoration: "none", color: "inherit" }}
    >
      <div className="flex-between">
        <span className={`badge badge-${edit.status === "open" ? "open" : edit.status}`}>
          {edit.status}
        </span>
        <span className="muted mono">{edit.edit_type}</span>
      </div>
      <div
        style={{
          display: "flex",
          gap: "1rem",
          alignItems: "flex-start",
          flexWrap: "wrap",
          marginTop: "0.5rem",
        }}
      >
        <div style={{ flex: "1 1 200px", minWidth: 0 }}>
          <h3 style={{ marginTop: 0 }}>{editTitle(edit)}</h3>
          {logoContext && logoContext !== editTitle(edit) && (
            <p className="muted" style={{ marginTop: "0.35rem" }}>
              {logoContext}
            </p>
          )}
          {edit.editor_username && (
            <p className="muted" style={{ marginTop: "0.35rem" }}>
              by{" "}
              <Link
                to={`/user/${encodeURIComponent(edit.editor_username)}`}
                onClick={(e) => e.stopPropagation()}
              >
                {edit.editor_username}
              </Link>
            </p>
          )}
          {edit.comment && <p className="muted">{edit.comment}</p>}
          <p className="muted">
            {edit.votes.length} vote(s) · expires {new Date(edit.expires_at).toLocaleDateString()}
          </p>
        </div>
        {logoUrl && <BrandLogoImage src={logoUrl} alt="Proposed logo" size="vote" />}
      </div>
    </Link>
  );
}
