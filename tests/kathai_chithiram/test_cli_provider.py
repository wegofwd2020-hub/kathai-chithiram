"""CLI provider selection + the synthetic-data guard."""

from __future__ import annotations

import json

# A scripted provider that returns a valid scene script (reuse the generation helper).
from tests.kathai_chithiram.generation.test_generator import (  # type: ignore
    ScriptedProvider,
    _valid_script,
)

from kathai_chithiram import cli
from kathai_chithiram.wegofwd_llm import __all__ as seam_exports


def test_seam_reexports_new_providers() -> None:
    for name in ("GeminiProvider", "QwenProvider", "build_gemini_provider", "build_qwen_provider"):
        assert name in seam_exports


def test_generate_gemini_without_synthetic_flag_fails_closed(tmp_path, capsys) -> None:
    story = tmp_path / "s.txt"
    story.write_text("a synthetic story", encoding="utf-8")
    # Inject a provider so no key is needed; the guard must still refuse (non-ZDR + no flag).
    code = cli.main(
        ["generate", "--provider", "gemini", "--child-name", "Milo", str(story)],
        provider=ScriptedProvider(replies=[json.dumps(_valid_script())]),
    )
    assert code == 2
    assert "synthetic-data" in (capsys.readouterr().err.lower())


def test_generate_gemini_with_synthetic_flag_runs(tmp_path) -> None:
    story = tmp_path / "s.txt"
    story.write_text("a synthetic story", encoding="utf-8")
    code = cli.main(
        [
            "generate",
            "--provider", "gemini",
            "--synthetic-data",
            "--no-render",
            "--child-name", "Milo",
            str(story),
        ],
        provider=ScriptedProvider(replies=[json.dumps(_valid_script())]),
    )
    assert code == 0
