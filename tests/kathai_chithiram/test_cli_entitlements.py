"""Tests for ``kc entitlements`` — navigate-never-determine CLI surface.

Uses a real in-memory corpus (not mocks) so cite-or-refuse validation runs end-to-end.
``load_programs`` is patched to return lightweight synthetic programs whose quotes are
verbatim substrings of the synthetic corpus chunk.
"""

from __future__ import annotations

import builtins
import sqlite3

import pytest

from kathai_chithiram.cli import main

# ---------------------------------------------------------------------------
# Synthetic corpus helpers
# ---------------------------------------------------------------------------

_SYNTHETIC_SOURCE_ID = "test.synthetic"
_SYNTHETIC_CHUNK = (
    "Children with disabilities may receive educational support under this program. "
    "Contact your state agency to learn how to apply."
)
_CRITERIA_QUOTE = "Children with disabilities may receive educational support"
_WHO_QUOTE = "Contact your state agency"
_HOW_QUOTE = "to learn how to apply"


def _build_synthetic_programs():
    """Two synthetic programs (federal + michigan) citing the synthetic source."""
    from wegofwd_arivu.entitlements.schema import Citation, EntitlementProgram, Jurisdiction

    federal = EntitlementProgram(
        program_id="test.federal.program",
        name="Test Educational Support",
        jurisdiction=Jurisdiction.FEDERAL,
        summary="Provides educational support for children with disabilities.",
        criteria_as_written=(Citation(source_id=_SYNTHETIC_SOURCE_ID, quote=_CRITERIA_QUOTE),),
        who_decides=Citation(source_id=_SYNTHETIC_SOURCE_ID, quote=_WHO_QUOTE),
        how_to_apply=Citation(source_id=_SYNTHETIC_SOURCE_ID, quote=_HOW_QUOTE),
        aliases=("disability support", "special education"),
    )
    michigan = EntitlementProgram(
        program_id="test.michigan.program",
        name="Michigan Services Program",
        jurisdiction=Jurisdiction.MICHIGAN,
        summary="State services for children in Michigan.",
        criteria_as_written=(Citation(source_id=_SYNTHETIC_SOURCE_ID, quote=_CRITERIA_QUOTE),),
        who_decides=Citation(source_id=_SYNTHETIC_SOURCE_ID, quote=_WHO_QUOTE),
        how_to_apply=Citation(source_id=_SYNTHETIC_SOURCE_ID, quote=_HOW_QUOTE),
        aliases=("michigan services",),
    )
    return [federal, michigan]


def _seed_corpus(db_path: str) -> None:
    """Write the synthetic source and chunk into a fresh SqliteCorpus at db_path."""
    from wegofwd_arivu.corpus import Chunk, CurrencyStatus, Source
    from wegofwd_arivu.rights import SourceTier
    from wegofwd_arivu.store import open_corpus

    source = Source(
        source_id=_SYNTHETIC_SOURCE_ID,
        tier=SourceTier.TIER_1,
        rights=None,
        currency=CurrencyStatus.CURRENT,
    )
    chunk = Chunk(
        text=_SYNTHETIC_CHUNK,
        source_id=_SYNTHETIC_SOURCE_ID,
        licence_ref="",
        currency=CurrencyStatus.CURRENT,
    )
    with open_corpus(db_path) as corpus:
        corpus.write_source(source, [chunk])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def corpus_db(tmp_path, monkeypatch):
    """A tmp corpus DB seeded with synthetic data; KC_ARIVU_DB set; load_programs patched."""
    db_path = str(tmp_path / "test.corpus.db")
    _seed_corpus(db_path)
    monkeypatch.setenv("KC_ARIVU_DB", db_path)
    monkeypatch.setattr(
        "wegofwd_arivu.entitlements.registry.load_programs",
        _build_synthetic_programs,
    )
    return db_path


# ---------------------------------------------------------------------------
# Tests: configuration errors
# ---------------------------------------------------------------------------

def test_entitlements_no_db_env_exits_2(monkeypatch, capsys) -> None:
    """Exits 2 with a helpful message when KC_ARIVU_DB is not set."""
    monkeypatch.delenv("KC_ARIVU_DB", raising=False)
    code = main(["entitlements", "--situation", "disability support"])
    assert code == 2
    err = capsys.readouterr().err
    assert "KC_ARIVU_DB" in err


def test_entitlements_arivu_not_installed_exits_2(monkeypatch, capsys) -> None:
    """Exits 2 gracefully when wegofwd-arivu is not importable."""
    monkeypatch.setenv("KC_ARIVU_DB", "/tmp/irrelevant.db")
    real_import = builtins.__import__

    def _block(name, *a, **k):
        if name.startswith("wegofwd_arivu"):
            raise ImportError(f"blocked: {name}")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _block)
    code = main(["entitlements", "--situation", "disability support"])
    assert code == 2
    err = capsys.readouterr().err
    assert "wegofwd-arivu" in err or "grounding" in err


# ---------------------------------------------------------------------------
# Tests: lookup behaviour
# ---------------------------------------------------------------------------

def test_entitlements_matching_situation_exits_0(corpus_db, capsys) -> None:
    """Returns 0 and prints matching program(s) for a relevant situation."""
    code = main(["entitlements", "--situation", "disability educational support for children"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Test Educational Support" in out
    assert "navigational information only" in out


def test_entitlements_shows_criteria_and_citations(corpus_db, capsys) -> None:
    """Output includes the criteria quote and source id for each matching card."""
    main(["entitlements", "--situation", "disability educational support"])
    out = capsys.readouterr().out
    assert _CRITERIA_QUOTE[:40] in out
    assert _SYNTHETIC_SOURCE_ID in out


def test_entitlements_no_match_prints_message(corpus_db, capsys) -> None:
    """Returns 0 and prints 'No programs matched' when nothing overlaps."""
    code = main(["entitlements", "--situation", "completely unrelated query xyz123"])
    assert code == 0
    out = capsys.readouterr().out
    assert "No programs matched" in out


def test_entitlements_jurisdiction_federal_filters(corpus_db, capsys) -> None:
    """--jurisdiction federal excludes the Michigan program."""
    main(["entitlements", "--situation", "disability educational support", "--jurisdiction", "federal"])
    out = capsys.readouterr().out
    assert "Test Educational Support" in out
    assert "Michigan Services Program" not in out


def test_entitlements_jurisdiction_michigan_filters(corpus_db, capsys) -> None:
    """--jurisdiction michigan excludes the federal program."""
    main(["entitlements", "--situation", "michigan services children", "--jurisdiction", "michigan"])
    out = capsys.readouterr().out
    assert "Michigan Services Program" in out
    assert "Test Educational Support" not in out


def test_entitlements_limit_respected(corpus_db, capsys) -> None:
    """--limit 1 returns at most one program even if two match."""
    # Both programs share the same source/aliases; a broad query can hit both.
    main(["entitlements", "--situation", "disability educational support children", "--limit", "1"])
    out = capsys.readouterr().out
    # At most one program block (count "Who decides:" occurrences as a proxy)
    assert out.count("Who decides:") <= 1
