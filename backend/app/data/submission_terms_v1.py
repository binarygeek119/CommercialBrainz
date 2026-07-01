"""Canonical submission terms content (version 1). Used for DB seeding."""

SUBMISSION_TERMS_V1 = {
    "version": 1,
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
            "heading": "Multiple Links Per Commercial",
            "paragraphs": [
                "A single commercial listing may include multiple YouTube links. The following variations are acceptable when properly labeled:"
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
                "Each link must be labeled clearly with its version type",
                "Do not submit the same URL multiple times",
                "Links should be ordered by quality when possible",
                "Dead or removed links may be flagged for removal by moderators",
            ],
        },
        {
            "number": 3,
            "heading": "Copyright & Intellectual Property",
            "bullets": [
                "You acknowledge that the commercial content is owned by its respective advertisers, agencies, or broadcasters",
                "You are not uploading content—only linking to publicly hosted videos",
                "CommercialBrainz does not claim ownership of any linked content",
            ],
        },
        {
            "number": 4,
            "heading": "Accuracy of Information",
            "bullets": [
                "You agree to provide accurate metadata when available (brand, product, air date, etc.)",
                "Do not submit misleading titles or descriptions",
                "Commercials should be categorized correctly by industry/type when possible",
            ],
        },
        {
            "number": 5,
            "heading": "Data Usage",
            "bullets": [
                "Submitted links and metadata become part of the CommercialBrainz database",
                "We reserve the right to edit submissions for clarity, categorization, or formatting",
                "Your submission may be displayed publicly on the site",
            ],
        },
        {
            "number": 6,
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
            "number": 7,
            "heading": "Moderation",
            "bullets": [
                "All submissions are subject to review and approval",
                "We reserve the right to reject or remove any submission without explanation",
                "Repeat violations of these terms may result in submission privileges being revoked",
            ],
        },
        {
            "number": 8,
            "heading": "Disclaimer",
            "bullets": [
                "CommercialBrainz is an index/indexing service only—we do not host video content",
                "We are not responsible for the availability, quality, or legality of linked videos",
                "YouTube videos may be removed by uploaders or rightsholders at any time; dead links may be periodically purged",
            ],
        },
        {
            "number": 9,
            "heading": "Changes to Terms",
            "bullets": [
                "These terms may be updated at any time",
                "Continued submission after changes constitutes acceptance of new terms",
            ],
        },
    ],
}
