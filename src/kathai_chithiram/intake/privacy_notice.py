"""The parent-facing privacy notice — versioned so consent can reference it (KC-8).

Consent is only *informed* if the parent is shown, in plain words, what happens
to their story before they agree (PRIVACY.md §8). This module holds a short,
plain-language **summary** of that handling and a **version** string, kept
together so the two can't drift. The full notice lives in
``docs/PARENT_PRIVACY_NOTICE.md``; this is the copy the intake flow presents
inline, and :data:`PRIVACY_NOTICE_VERSION` is what :func:`submit_intake` records
so an informed-consent audit can tie a consent to the exact notice a parent saw.

Bump :data:`PRIVACY_NOTICE_VERSION` whenever the summary or the full notice
changes in a way that affects what a parent is agreeing to.
"""

from __future__ import annotations

__all__ = [
    "PRIVACY_NOTICE_DOC",
    "PRIVACY_NOTICE_SUMMARY",
    "PRIVACY_NOTICE_VERSION",
    "format_notice_preamble",
]

#: Version of the parent-facing notice currently in effect. Matches the
#: ``Version:`` header of ``docs/PARENT_PRIVACY_NOTICE.md``. Bump on any change
#: to what a parent is agreeing to.
PRIVACY_NOTICE_VERSION = "2026-07-01"

#: Where the full plain-language notice lives (repo-relative), shown as a pointer.
PRIVACY_NOTICE_DOC = "docs/PARENT_PRIVACY_NOTICE.md"

#: The plain-language key points shown before the consent questions. Each line is
#: one commitment from ``PRIVACY.md``, in parent-readable words.
PRIVACY_NOTICE_SUMMARY: tuple[str, ...] = (
    "We only need your story and your child's first name — no surname, birthday, "
    "address, school, or medical details.",
    "Your story is used only to make your family's animation — never for "
    "advertising, and never shared for anyone else's purposes.",
    "We never use your story to train or improve any AI; the AI provider we use "
    "does not retain your text or train on it.",
    "Your child's name is removed before the story is sent to the AI, and added "
    "back only when the video is made — the saved script holds a placeholder.",
    "A person reviews every animation before it is shown to your child; nothing "
    "reaches them automatically.",
    "We delete your story within 30 days unless you save it, and you can delete "
    "everything at any time (contact wegofwd2020@gmail.com).",
)


def format_notice_preamble() -> str:
    """Return the notice summary to show a parent before asking for consent.

    Returns:
        A plain-language block: a heading, the summarized commitments, the notice
        version, and a pointer to the full notice. Safe to print to a terminal;
        contains no story text or child data.
    """
    lines = ["Before we begin — how we handle your story and your child's data:"]
    lines.extend(f"  • {point}" for point in PRIVACY_NOTICE_SUMMARY)
    lines.append("")
    lines.append(
        f"Full privacy notice (version {PRIVACY_NOTICE_VERSION}): {PRIVACY_NOTICE_DOC}"
    )
    return "\n".join(lines)
