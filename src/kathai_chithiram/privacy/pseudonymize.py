"""Replace a child's real name with a placeholder token, and reverse it.

The mapping between real identifiers and the token is a *local-only* value
object (:class:`NameMapping`). Generation pseudonymizes story text with it
before any provider call; rendering reinserts the display name from it. The
mapping itself is never sent to a provider or written to logs.

Design choices:

* Matching is **case-insensitive** and **word-boundary aware**, so ``"Sam"``
  never matches inside ``"Samuel"`` or ``"sample"``, while ``"Sam's"`` becomes
  ``"CHILD's"``.
* Multiple identifiers (e.g. a first name and a nickname) all collapse to the
  one token, longest first so an overlapping nickname can't leave a fragment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

__all__ = [
    "DEFAULT_CHILD_TOKEN",
    "NameMapping",
    "contains_identifier",
    "count_identifiers",
    "pseudonymize",
    "reinsert",
]

#: Default placeholder. Matches the scene-script ``child_token`` shape
#: (``^[A-Z][A-Z0-9_]*$``) so a pseudonymized story can populate a valid script.
DEFAULT_CHILD_TOKEN = "CHILD"

_TOKEN_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


@dataclass(frozen=True)
class NameMapping:
    """A local-only mapping from a child's real identifiers to a token.

    Args:
        identifiers: The real names to strip — typically the child's first name
            and any nickname. Blank entries are ignored. Never logged or sent.
        token: The placeholder substituted for every identifier. Must match the
            scene-script ``child_token`` shape (uppercase token).
        display_name: The name reinserted at render time. Defaults to the first
            identifier. ``None`` only when no identifier was supplied.

    Raises:
        ValueError: If ``token`` is not a valid uppercase token.
    """

    identifiers: tuple[str, ...]
    token: str = DEFAULT_CHILD_TOKEN
    display_name: str | None = None
    _pattern: re.Pattern[str] | None = field(default=None, compare=False, repr=False)

    def __post_init__(self) -> None:
        if not _TOKEN_PATTERN.match(self.token):
            raise ValueError(
                f"token must match {_TOKEN_PATTERN.pattern!r} (got a non-conforming token)"
            )
        cleaned = tuple(name for name in self.identifiers if name and name.strip())
        object.__setattr__(self, "identifiers", cleaned)

        if self.display_name is None and cleaned:
            object.__setattr__(self, "display_name", cleaned[0])

        object.__setattr__(self, "_pattern", _compile_identifier_pattern(cleaned))

    @classmethod
    def for_child(
        cls,
        first_name: str,
        *,
        nickname: str | None = None,
        token: str = DEFAULT_CHILD_TOKEN,
        display_name: str | None = None,
    ) -> NameMapping:
        """Build a mapping for one child from a first name and optional nickname.

        Args:
            first_name: The child's first name (the default display name).
            nickname: An optional second identifier to strip as well.
            token: Placeholder token; see :class:`NameMapping`.
            display_name: Override for what is reinserted at render time.

        Returns:
            A :class:`NameMapping` covering both identifiers.

        Raises:
            ValueError: If ``first_name`` is blank.
        """
        if not first_name or not first_name.strip():
            raise ValueError("first_name must be a non-empty name")
        identifiers = (first_name,) if nickname is None else (first_name, nickname)
        return cls(
            identifiers=identifiers,
            token=token,
            display_name=display_name or first_name,
        )


def _compile_identifier_pattern(identifiers: tuple[str, ...]) -> re.Pattern[str] | None:
    """Compile one case-insensitive, boundary-aware alternation of identifiers.

    Longest identifiers come first so an alternation never matches a shorter
    nickname inside a longer name and leaves a fragment behind.
    """
    unique = sorted({name for name in identifiers if name}, key=len, reverse=True)
    if not unique:
        return None
    alternation = "|".join(re.escape(name) for name in unique)
    # (?<!\w) / (?!\w) act as word boundaries that also behave well next to
    # apostrophes and hyphens (e.g. possessives) where \b is awkward.
    return re.compile(rf"(?<!\w)(?:{alternation})(?!\w)", re.IGNORECASE)


def pseudonymize(text: str, mapping: NameMapping) -> str:
    """Return ``text`` with every identifier in ``mapping`` replaced by the token.

    Args:
        text: Free-form story text to minimize before it leaves the device.
        mapping: The local identifier→token mapping.

    Returns:
        The text with identifiers replaced. If the mapping has no identifiers
        (no name supplied), the text is returned unchanged.

    Raises:
        TypeError: If ``text`` is not a string.
    """
    if not isinstance(text, str):
        raise TypeError(f"text must be a str, got {type(text).__name__}")
    if mapping._pattern is None:
        return text
    return mapping._pattern.sub(mapping.token, text)


def contains_identifier(text: str, mapping: NameMapping) -> bool:
    """Return whether ``text`` still contains any identifier from ``mapping``.

    Used as a post-pseudonymization guard before dispatch: a ``True`` here means
    minimization failed and the payload must not be sent.

    Args:
        text: The (expected-to-be-clean) outbound text.
        mapping: The local identifier→token mapping.

    Returns:
        ``True`` if any identifier occurs as a whole word, else ``False``.

    Raises:
        TypeError: If ``text`` is not a string.
    """
    if not isinstance(text, str):
        raise TypeError(f"text must be a str, got {type(text).__name__}")
    if mapping._pattern is None:
        return False
    return mapping._pattern.search(text) is not None


def count_identifiers(text: str, mapping: NameMapping) -> int:
    """Return how many identifier occurrences remain in ``text``.

    Used by the seam to report the size of a leak without revealing it.

    Args:
        text: The text to scan.
        mapping: The local identifier→token mapping.

    Returns:
        The number of whole-word identifier matches (``0`` if none).

    Raises:
        TypeError: If ``text`` is not a string.
    """
    if not isinstance(text, str):
        raise TypeError(f"text must be a str, got {type(text).__name__}")
    if mapping._pattern is None:
        return 0
    return len(mapping._pattern.findall(text))


def reinsert(text: str, mapping: NameMapping) -> str:
    """Return ``text`` with the token replaced by the mapping's display name.

    This is the render-time substitution: the child's real name appears only in
    the final, locally-rendered output, never in stored scripts or outbound
    payloads.

    Args:
        text: Text containing the placeholder token (e.g. a scene caption).
        mapping: The local mapping holding the display name.

    Returns:
        The text with whole-word token occurrences replaced by the display
        name. If the mapping has no display name, the text is returned
        unchanged (there is nothing to reinsert).

    Raises:
        TypeError: If ``text`` is not a string.
    """
    if not isinstance(text, str):
        raise TypeError(f"text must be a str, got {type(text).__name__}")
    if mapping.display_name is None:
        return text
    token_pattern = re.compile(rf"(?<!\w){re.escape(mapping.token)}(?!\w)")
    return token_pattern.sub(mapping.display_name, text)
