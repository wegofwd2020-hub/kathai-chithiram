"""Privacy utilities: identifier minimization for the child's data.

A child's real name is replaced with a placeholder token before any text leaves
the device for an LLM provider, and reinserted only at render time (PRIVACY.md
§6, CLAUDE.md). The name↔token mapping is held locally and never sent.
"""

from __future__ import annotations

from kathai_chithiram.privacy.pseudonymize import (
    DEFAULT_CHILD_TOKEN,
    NameMapping,
    contains_identifier,
    count_identifiers,
    pseudonymize,
    reinsert,
)

__all__ = [
    "DEFAULT_CHILD_TOKEN",
    "NameMapping",
    "contains_identifier",
    "count_identifiers",
    "pseudonymize",
    "reinsert",
]
