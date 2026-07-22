import type { Edit } from "../api";
import {
  CATALOG_EDIT_TYPES,
  catalogKindFromEditType,
} from "../catalog/kinds";

export function editTitle(edit: Edit): string {
  if (edit.edit_type === "create_advertiser") {
    return (edit.after_state.name as string) || "New brand";
  }
  if (edit.edit_type === "add_advertiser_logo") {
    return (edit.after_state.label as string) || "Brand logo version";
  }
  if (edit.edit_type === "edit_advertiser_logo") {
    return (edit.after_state.label as string) || "Logo metadata";
  }
  if (edit.edit_type === "edit_advertiser" && edit.after_state.logo_url) {
    return "Brand logo";
  }
  if (edit.edit_type === "edit_advertiser") {
    return (edit.after_state.name as string) || "Brand metadata";
  }

  const catalogKind = catalogKindFromEditType(edit.edit_type);
  if (catalogKind) {
    if (edit.edit_type === catalogKind.createEdit) {
      return (edit.after_state.name as string) || `New ${catalogKind.label.toLowerCase()}`;
    }
    if (edit.edit_type === catalogKind.addLogoEdit) {
      return (edit.after_state.label as string) || `${catalogKind.label} logo version`;
    }
    if (edit.edit_type === catalogKind.editLogoEdit) {
      return (edit.after_state.label as string) || "Logo metadata";
    }
    if (edit.edit_type === catalogKind.editEdit && edit.after_state.logo_url) {
      return `${catalogKind.label} logo`;
    }
    if (edit.edit_type === catalogKind.editEdit) {
      return (edit.after_state.name as string) || `${catalogKind.label} metadata`;
    }
  }

  if (edit.edit_type === "edit_commercial") {
    return (edit.after_state.title as string) || "Commercial metadata";
  }
  if (edit.edit_type === "split_commercial") {
    const commercial = edit.after_state.commercial as { title?: string } | undefined;
    const video = edit.before_state?.video as { version_label?: string; youtube_id?: string } | undefined;
    const linkLabel = video?.version_label || video?.youtube_id || "link";
    return commercial?.title ? `Split: ${linkLabel} → ${commercial.title}` : "Split link to own commercial";
  }
  if (edit.edit_type === "edit_video" && edit.after_state.thumbnail_url) {
    return "Custom thumbnail";
  }
  return (
    (edit.after_state.title as string) ||
    (edit.after_state.commercial as { title?: string })?.title ||
    edit.entity_type
  );
}

export function editVoteThreshold(edit: Edit): number {
  return edit.edit_type === "create_advertiser" ||
    edit.edit_type === "edit_advertiser" ||
    edit.edit_type === "add_advertiser_logo" ||
    edit.edit_type === "edit_advertiser_logo" ||
    CATALOG_EDIT_TYPES.includes(edit.edit_type)
    ? 10
    : 3;
}

export function nextSlotAtPoints(reputationPoints: number, pointsPerSlot = 20, base = 1, max = 20): number | null {
  const bonus = Math.floor(reputationPoints / pointsPerSlot);
  const currentMax = Math.min(max, base + bonus);
  if (currentMax >= max) return null;
  return (bonus + 1) * pointsPerSlot;
}
