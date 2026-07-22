"""Power User Terms version 1 — quality control for bulk playlist submit."""

POWER_USER_TERMS_V1 = {
    "version": 1,
    "title": "Power User Terms",
    "intro": (
        "Bulk playlist submit is a privileged tool. By accepting, you agree to "
        "personally quality-control every staged video before it enters the catalog."
    ),
    "sections": [
        {
            "number": 1,
            "heading": "Personal review required",
            "paragraphs": [
                "You must review each playlist item yourself before clicking Submit.",
                "Prefetched YouTube metadata and hashes are helpers only — they do not "
                "replace your judgment about brand, campaign, and catalog fit.",
            ],
            "bullet_label": "For every item you submit, confirm:",
            "bullets": [
                "The upload is a real commercial suitable for CommercialBrainz",
                "Title, brand/advertiser, and campaign fields are accurate",
                "It is not spam, junk, a duplicate dump, or an unreviewed batch paste",
                "Tags and region/language fields are correct when you set them",
            ],
        },
        {
            "number": 2,
            "heading": "No unreviewed dumps",
            "paragraphs": [
                "Do not import a playlist and mass-submit without reviewing each link.",
                "Skip items that do not belong; do not force bad entries into the catalog.",
            ],
        },
        {
            "number": 3,
            "heading": "Revocation",
            "paragraphs": [
                "Failure to uphold these quality standards can result in immediate "
                "removal of power-user / bulk-submit access by an administrator.",
                "Admins may also remove access for abuse or any other operational need.",
                "Re-granting access later requires a new admin enable and may require "
                "accepting updated Power User Terms.",
            ],
        },
    ],
}
