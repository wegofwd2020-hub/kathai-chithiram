"""KC-21: the generate CLI reads KC_ARIVU_DB to build a grounding source."""

from __future__ import annotations

from kathai_chithiram import cli


def test_grounding_from_env_none_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("KC_ARIVU_DB", raising=False)
    assert cli._grounding_from_env() is None


def test_grounding_from_env_disabled_when_extra_absent(monkeypatch) -> None:
    monkeypatch.setenv("KC_ARIVU_DB", "/tmp/x.corpus.db")
    import builtins

    real_import = builtins.__import__

    def _blocked(name, *a, **k):
        if name == "wegofwd_arivu" or name.startswith("wegofwd_arivu."):
            raise ImportError("absent")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _blocked)
    assert cli._grounding_from_env() is None
