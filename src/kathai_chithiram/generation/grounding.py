"""Retrieval grounding for scene-script generation (KC-21).

Optional: consumes the ``wegofwd-arivu`` corpus to inform generation with cited
practice passages (ADR-009 D1, ADR-010). Purely additive — with no corpus, no
matches, or the ``grounding`` extra absent, generation is unchanged. ``wegofwd-
arivu`` is imported lazily and only in :class:`ArivuGroundingSource` /
:func:`open_grounding_source`, so the core generation modules never depend on it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

__all__ = [
    "GroundingPassage",
    "GroundingSource",
    "build_grounding_block",
    "ArivuGroundingSource",
    "open_grounding_source",
]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GroundingPassage:
    """A cited reference passage used to ground generation.

    Holds public reference material only — never personal data. ``source_id`` and
    ``licence_ref`` are log-safe identifiers (never document text).

    Args:
        text: The reference passage shown to the model (not to the child).
        source_id: The corpus source's stable, log-safe id.
        licence_ref: A reference to that source's recorded licence terms.
    """

    text: str
    source_id: str
    licence_ref: str


@runtime_checkable
class GroundingSource(Protocol):
    """A source of cited reference passages for grounding.

    Implementations MUST **fail safe**: return ``[]`` rather than raise, so
    grounding can never break generation.
    """

    def retrieve(self, query: str, *, limit: int = 5) -> list[GroundingPassage]:
        """Return up to ``limit`` cited passages relevant to ``query`` (or ``[]``)."""
        ...


@dataclass(frozen=True)
class ArivuGroundingSource:
    """A :class:`GroundingSource` backed by a local ``wegofwd-arivu`` SQLite corpus.

    Fails safe: any corpus error (missing/invalid DB, read error) returns ``[]``,
    so grounding is best-effort and never breaks generation. ``wegofwd-arivu`` is
    imported here, lazily, so importing this module never requires the extra.

    Args:
        db_path: Filesystem path to the corpus database.
    """

    db_path: str

    def retrieve(self, query: str, *, limit: int = 5) -> list[GroundingPassage]:
        """Retrieve up to ``limit`` cited passages for ``query``; ``[]`` on any error."""
        from wegofwd_arivu import open_corpus  # type: ignore[import-not-found]
        from wegofwd_arivu.errors import StoreError  # type: ignore[import-not-found]

        try:
            with open_corpus(self.db_path) as corpus:
                chunks = corpus.retrieve(query, limit=limit)
        except (StoreError, OSError) as exc:
            logger.warning(
                "grounding retrieval failed (%s); proceeding ungrounded", type(exc).__name__
            )
            return []
        return [
            GroundingPassage(text=c.text, source_id=c.source_id, licence_ref=c.licence_ref)
            for c in chunks
        ]


def open_grounding_source(db_path: str | None) -> GroundingSource | None:
    """Build a grounding source over the corpus at ``db_path``, or ``None``.

    Returns ``None`` (grounding off) when ``db_path`` is falsy or the optional
    ``wegofwd-arivu`` dependency is not installed — the caller then generates
    exactly as it does without grounding.

    Args:
        db_path: Filesystem path to a ``wegofwd-arivu`` SQLite corpus, or ``None``.

    Returns:
        An :class:`ArivuGroundingSource`, or ``None`` when grounding is unavailable.
    """
    if not db_path:
        return None
    try:
        import wegofwd_arivu  # noqa: F401
    except ImportError:
        logger.info(
            "grounding disabled: the 'grounding' extra (wegofwd-arivu) is not installed"
        )
        return None
    return ArivuGroundingSource(db_path)


def build_grounding_block(passages: list[GroundingPassage]) -> str:
    """Render cited reference passages as a prompt block.

    Args:
        passages: The retrieved passages; an empty list means "no grounding".

    Returns:
        A labelled, cited block for the system-prompt prefix, or ``""`` when
        there are no passages (so the prompt is unchanged).
    """
    if not passages:
        return ""
    lines = [
        "REFERENCE PRACTICE (cited; for grounding only)",
        "The following are published reference passages. Let them inform calm, "
        "accurate, literal steps. Do NOT quote them verbatim and do NOT copy "
        "their wording into narration or captions.",
        "",
    ]
    lines.extend(f"- [{p.source_id}] {p.text}" for p in passages)
    return "\n".join(lines)
