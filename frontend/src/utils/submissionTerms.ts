import type { User } from "../api";

/** True when the user must see/accept the current Terms of Submission. */
export function needsSubmissionTermsAgreement(
  user: User | null,
  activeTermsVersion: number | null | undefined,
): boolean {
  if (!user || activeTermsVersion == null) return false;
  return (
    user.submission_terms_version == null ||
    user.submission_terms_version < activeTermsVersion
  );
}
