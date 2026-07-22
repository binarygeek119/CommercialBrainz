import { describe, expect, it } from "vitest";
import type { User } from "../api";
import { needsSubmissionTermsAgreement } from "./submissionTerms";

function user(partial: Partial<User> = {}): User {
  return {
    id: "1",
    username: "u",
    email: "u@example.com",
    role: "user",
    access_level: "vote_only",
    can_submit: false,
    email_verified: true,
    reputation_points: 0,
    submit_slots_max: 1,
    submit_slots_used: 0,
    submit_slots_available: 1,
    is_auto_editor: false,
    accepted_edits_count: 0,
    submission_terms_version: null,
    submission_terms_accepted_at: null,
    created_at: new Date().toISOString(),
    ...partial,
  };
}

describe("needsSubmissionTermsAgreement", () => {
  it("is false without a user or active terms version", () => {
    expect(needsSubmissionTermsAgreement(null, 2)).toBe(false);
    expect(needsSubmissionTermsAgreement(user(), null)).toBe(false);
  });

  it("is true for users who have never agreed", () => {
    expect(needsSubmissionTermsAgreement(user({ submission_terms_version: null }), 2)).toBe(true);
  });

  it("is true when the accepted version is outdated", () => {
    expect(needsSubmissionTermsAgreement(user({ submission_terms_version: 1 }), 2)).toBe(true);
  });

  it("is false when the accepted version matches or is newer", () => {
    expect(needsSubmissionTermsAgreement(user({ submission_terms_version: 2 }), 2)).toBe(false);
    expect(needsSubmissionTermsAgreement(user({ submission_terms_version: 3 }), 2)).toBe(false);
  });
});
