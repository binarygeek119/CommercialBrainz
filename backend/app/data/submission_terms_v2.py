"""Submission terms version 2 — master/sub links and split voting."""

SUBMISSION_TERMS_V2 = {
    "version": 2,
    "title": "Terms of Submission",
    "intro": "By submitting a link to CommercialBrainz, you agree to the following:",
    "sections": [
        {
            "number": 1,
            "heading": "Content Requirements",
            "paragraphs": [
                "You may only submit links to publicly available YouTube videos of television/streaming commercials"
            ],
            "bullet_label": "Do not submit links to:",
            "bullets": [
                "Unlisted or private videos",
                "User-generated content (fan uploads of commercials are acceptable if they don't violate copyright)",
                "Non-commercial content (movie trailers, music videos, etc.)",
                "Duplicate entries for the same commercial video",
            ],
        },
        {
            "number": 2,
            "heading": "Master Links and Sub Links",
            "paragraphs": [
                "Each commercial page groups one campaign with one or more YouTube uploads.",
                "A master link is the main link on that commercial. It carries the primary metadata for the campaign — title, brand, air date, products, and related fields.",
                "Sub links are additional YouTube uploads attached to the same commercial as the master link. They represent alternate cuts, lengths, regional copies, backup mirrors, or other variants of the same spot.",
                "Sub links inherit metadata from the master link and the commercial. When you add a sub link, you only need to fill in what differs for that upload — version label, language, region, transcript, tags, or other link-specific details.",
                "Community popularity votes decide which link is the master link (highest net score). Other links on the same commercial remain sub links.",
            ],
            "bullet_label": "Use sub links when:",
            "bullets": [
                "The upload is the same commercial with a different cut length, quality, or mirror",
                "The upload is a regional or language variant of the same spot",
                "The upload is a backup copy of the same campaign video",
            ],
            "subsections": [
                {
                    "heading": "When a sub link should become its own master link",
                    "paragraphs": [
                        "If a link is actually a different commercial — different product, campaign, or spot — it should not stay as a sub link. Any logged-in user with submit access may propose splitting a sub link into its own commercial (its own master link with its own page).",
                    ],
                },
                {
                    "heading": "Split vote rules",
                    "paragraphs": [
                        "Split proposals are open for up to 3 months. Other users vote yes or no on whether the link should leave the current commercial and become its own master link.",
                    ],
                    "bullets": [
                        "Early approval: if a split proposal receives 20 yes votes, it is applied immediately",
                        "After 3 months: if the proposal has at least one yes vote and more yes votes than no votes, the split is approved",
                        "After 3 months with competing votes: whichever side (yes or no) has the most votes wins; if there are no votes at all, the split is rejected",
                        "Moderators may approve or reject a split proposal at any time",
                        "You cannot split the only link on a commercial — at least one other link must remain",
                    ],
                },
            ],
        },
        {
            "number": 3,
            "heading": "Multiple Links Per Commercial",
            "paragraphs": [
                "When links belong on the same commercial as sub links, the following variations are acceptable when properly labeled:"
            ],
            "subsections": [
                {
                    "heading": "Same Content, Different Uploads",
                    "bullets": [
                        "Multiple uploads of the identical commercial (mirrors, reuploads, different channels)"
                    ],
                },
                {
                    "heading": "Different Versions of the Same Commercial",
                    "bullets": [
                        "Length cuts: Long cut, short cut, :15, :30, :60 versions",
                        "Broadcast versions: Super Bowl cut, extended cut, director's cut",
                        "Censorship variants: Censored/uncensored, daytime/TV-safe versions",
                        "Quality variants: Higher resolution, better bitrate, remastered, AI-enhanced",
                        "Regional versions: Different audio tracks, localized text, international cuts",
                        "Audio variants: Better sound mix, music-only, dialogue-only",
                    ],
                },
            ],
            "bullet_label": "Requirements:",
            "bullets": [
                "Each sub link must be labeled clearly with its version type",
                "Do not submit the same URL multiple times",
                "Links should be ordered by quality when possible",
                "Dead or removed links may be flagged for removal by moderators",
            ],
        },
        {
            "number": 4,
            "heading": "Copyright & Intellectual Property",
            "bullets": [
                "You acknowledge that the commercial content is owned by its respective advertisers, agencies, or broadcasters",
                "You are not uploading content—only linking to publicly hosted videos",
                "CommercialBrainz does not claim ownership of any linked content",
            ],
        },
        {
            "number": 5,
            "heading": "Accuracy of Information",
            "bullets": [
                "You agree to provide accurate metadata when available (brand, product, air date, etc.)",
                "Do not submit misleading titles or descriptions",
                "Commercials should be categorized correctly by industry/type when possible",
            ],
        },
        {
            "number": 6,
            "heading": "Data Usage",
            "bullets": [
                "Submitted links and metadata become part of the CommercialBrainz database",
                "We reserve the right to edit submissions for clarity, categorization, or formatting",
                "Your submission may be displayed publicly on the site",
            ],
        },
        {
            "number": 7,
            "heading": "Prohibited Content",
            "paragraphs": ["Do not submit links to commercials that:"],
            "bullets": [
                "Promote illegal products or services",
                "Contain hate speech, discrimination, or harassment",
                "Are sexually explicit (unless clearly marked as adult content and appropriately categorized)",
                "Violate YouTube's Terms of Service",
            ],
        },
        {
            "number": 8,
            "heading": "Moderation",
            "bullets": [
                "All submissions are subject to review and approval",
                "We reserve the right to reject or remove any submission without explanation",
                "Repeat violations of these terms may result in submission privileges being revoked",
            ],
        },
        {
            "number": 9,
            "heading": "Disclaimer",
            "bullets": [
                "CommercialBrainz is an index/indexing service only—we do not host video content",
                "We are not responsible for the availability, quality, or legality of linked videos",
                "YouTube videos may be removed by uploaders or rightsholders at any time; dead links may be periodically purged",
            ],
        },
        {
            "number": 10,
            "heading": "Changes to Terms",
            "bullets": [
                "These terms may be updated at any time",
                "Continued submission after changes constitutes acceptance of new terms",
            ],
        },
    ],
}
