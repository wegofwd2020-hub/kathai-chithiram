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
