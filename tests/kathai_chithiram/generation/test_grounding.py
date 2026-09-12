"""Tests for the grounding seam types and the prompt block (KC-21)."""

from __future__ import annotations

from kathai_chithiram.generation.grounding import (
    GroundingPassage,
    build_grounding_block,
)


def _passages() -> list[GroundingPassage]:
    return [
        GroundingPassage(text="Warm up to the toothbrush gradually.", source_id="cdc:oral-1", licence_ref="cdc:pd"),
        GroundingPassage(text="Use a visual schedule for the routine.", source_id="ed:idea-2", licence_ref="ed:pd"),
    ]


def test_block_is_empty_when_no_passages() -> None:
    assert build_grounding_block([]) == ""


def test_block_cites_each_source_and_forbids_verbatim() -> None:
    block = build_grounding_block(_passages())
    assert "cdc:oral-1" in block
    assert "ed:idea-2" in block
    assert "REFERENCE PRACTICE" in block
    assert "verbatim" in block.lower()
    # the passage text is present (shown to the model, not the child)
    assert "visual schedule" in block
