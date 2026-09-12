"""Tests for the grounding seam types and the prompt block (KC-21)."""

from __future__ import annotations

import importlib.util

import pytest

from kathai_chithiram.generation.grounding import (
    ArivuGroundingSource,
    GroundingPassage,
    build_grounding_block,
    open_grounding_source,
)

_ARIVU_AVAILABLE = importlib.util.find_spec("wegofwd_arivu") is not None


def _passages() -> list[GroundingPassage]:
    return [
        GroundingPassage(
            text="Warm up to the toothbrush gradually.",
            source_id="cdc:oral-1",
            licence_ref="cdc:pd",
        ),
        GroundingPassage(
            text="Use a visual schedule for the routine.",
            source_id="ed:idea-2",
            licence_ref="ed:pd",
        ),
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


def test_open_grounding_source_none_path_is_disabled() -> None:
    assert open_grounding_source(None) is None
    assert open_grounding_source("") is None


def test_open_grounding_source_none_when_extra_absent(monkeypatch) -> None:
    import builtins

    real_import = builtins.__import__

    def _blocked(name, *a, **k):
        if name == "wegofwd_arivu" or name.startswith("wegofwd_arivu."):
            raise ImportError("wegofwd-arivu not installed")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _blocked)
    assert open_grounding_source("/tmp/whatever.corpus.db") is None


@pytest.mark.skipif(not _ARIVU_AVAILABLE, reason="wegofwd-arivu extra not installed")
def test_arivu_source_fails_safe_on_missing_corpus() -> None:
    # Pointing at a path with no valid corpus must yield [] (never raise),
    # so grounding degrades to "no support" rather than breaking generation.
    src = ArivuGroundingSource("/nonexistent/dir/does-not-exist.corpus.db")
    assert src.retrieve("toothbrushing routine") == []
