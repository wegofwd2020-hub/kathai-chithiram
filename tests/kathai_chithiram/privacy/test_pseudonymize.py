"""Tests for identifier minimization (KC-2).

The child name used here ("Milo") is wholly fictional synthetic test data
(CLAUDE.md: no real child data in fixtures).
"""

from __future__ import annotations

import pytest

from kathai_chithiram.privacy import (
    DEFAULT_CHILD_TOKEN,
    NameMapping,
    contains_identifier,
    count_identifiers,
    pseudonymize,
    reinsert,
)


def test_default_token_matches_child_token_shape() -> None:
    # Keeps a pseudonymized story compatible with the scene-script child_token.
    assert DEFAULT_CHILD_TOKEN == "CHILD"


def test_replaces_name_with_token() -> None:
    mapping = NameMapping.for_child("Milo")
    assert pseudonymize("Milo walks to the slide.", mapping) == "CHILD walks to the slide."


def test_replacement_is_case_insensitive() -> None:
    mapping = NameMapping.for_child("Milo")
    out = pseudonymize("MILO and milo and Milo", mapping)
    assert out == "CHILD and CHILD and CHILD"


def test_possessive_keeps_suffix() -> None:
    mapping = NameMapping.for_child("Milo")
    assert pseudonymize("This is Milo's toothbrush.", mapping) == "This is CHILD's toothbrush."


def test_does_not_match_inside_longer_word() -> None:
    mapping = NameMapping.for_child("Sam")
    # "Samuel" / "sample" must be untouched; only the standalone word changes.
    assert pseudonymize("Samuel had a sample. Sam smiled.", mapping) == (
        "Samuel had a sample. CHILD smiled."
    )


def test_strips_nickname_too() -> None:
    mapping = NameMapping.for_child("Milo", nickname="Bug")
    assert pseudonymize("Milo, also called Bug, waved.", mapping) == (
        "CHILD, also called CHILD, waved."
    )


def test_no_identifier_is_noop() -> None:
    mapping = NameMapping(identifiers=())
    text = "The child walks to the slide."
    assert pseudonymize(text, mapping) == text
    assert contains_identifier(text, mapping) is False


def test_contains_and_count_identifiers() -> None:
    mapping = NameMapping.for_child("Milo")
    assert contains_identifier("CHILD walks", mapping) is False
    assert contains_identifier("Milo walks", mapping) is True
    assert count_identifiers("Milo and Milo and milo", mapping) == 3


def test_reinsert_restores_display_name() -> None:
    mapping = NameMapping.for_child("Milo")
    assert reinsert("CHILD walks to the slide.", mapping) == "Milo walks to the slide."


def test_reinsert_uses_explicit_display_name() -> None:
    # First name is stripped, but a preferred display name is reinserted verbatim.
    mapping = NameMapping.for_child("Milo", display_name="MJ")
    assert reinsert("CHILD waves.", mapping) == "MJ waves."


def test_roundtrip_pseudonymize_then_reinsert() -> None:
    mapping = NameMapping.for_child("Milo")
    original = "Milo walks. Milo smiles."
    masked = pseudonymize(original, mapping)
    assert "Milo" not in masked
    assert reinsert(masked, mapping) == original


def test_invalid_token_rejected() -> None:
    with pytest.raises(ValueError, match="token"):
        NameMapping(identifiers=("Milo",), token="child")  # lowercase not allowed


def test_blank_first_name_rejected() -> None:
    with pytest.raises(ValueError, match="first_name"):
        NameMapping.for_child("   ")


def test_non_string_text_rejected() -> None:
    mapping = NameMapping.for_child("Milo")
    with pytest.raises(TypeError):
        pseudonymize(123, mapping)  # type: ignore[arg-type]
