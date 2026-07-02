"""Tests for the end-to-end CLI.

Driven with a scripted stub provider and ``--no-render`` so the wiring is
exercised without a network call or a heavy matplotlib render. The privacy and
review boundaries are the focus: the raw story (with the name) is stored, the
scene script is not (token only), the name never reaches the provider, and the
provider's privacy posture must be asserted before anything is sent.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from kathai_chithiram.cli import _cmd_intake, build_arg_parser, main
from kathai_chithiram.generation import EXAMPLE_SCENE_SCRIPT
from kathai_chithiram.wegofwd_llm.provider import LLMRequest, LLMResponse

CHILD = "Robin"
STORY = "Robin is scared of the dark. Robin turns on a light and feels calm."


@dataclass
class ScriptedProvider:
    """A fake provider returning one canned JSON reply, recording requests."""

    reply: str
    requests: list[LLMRequest] = field(default_factory=list)

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(text=self.reply)


def _provider() -> ScriptedProvider:
    return ScriptedProvider(reply=json.dumps(copy.deepcopy(EXAMPLE_SCENE_SCRIPT)))


def _write_story(tmp_path: Path) -> Path:
    story_file = tmp_path / "story.txt"
    story_file.write_text(STORY, encoding="utf-8")
    return story_file


def _argv(story_file: Path, store_root: Path, *extra: str) -> list[str]:
    return [
        "generate",
        str(story_file),
        "--child-name",
        CHILD,
        "--story-id",
        "test-story",
        "--store-root",
        str(store_root),
        *extra,
    ]


def test_happy_path_stores_story_and_scene_script(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    provider = _provider()
    code = main(
        _argv(_write_story(tmp_path), store_root, "--provider-no-train-zdr", "--no-render"),
        provider=provider,
    )
    assert code == 0

    story_dir = store_root / "test-story"
    # The raw story (which names the child) is stored as story.txt by design.
    assert (story_dir / "story.txt").read_text(encoding="utf-8") == STORY
    # The scene script must carry only the token — never the real name.
    script_text = (story_dir / "scene_script.json").read_text(encoding="utf-8")
    assert CHILD not in script_text
    assert "CHILD" in json.loads(script_text)["child_token"]


def test_child_name_never_reaches_provider(tmp_path: Path) -> None:
    provider = _provider()
    main(
        _argv(_write_story(tmp_path), tmp_path / "store", "--provider-no-train-zdr", "--no-render"),
        provider=provider,
    )
    sent = provider.requests[0].prompt
    assert CHILD not in sent
    assert "CHILD" in sent


def test_refuses_without_privacy_assertion(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    provider = _provider()
    # No --provider-no-train-zdr: generation must refuse before dispatch.
    code = main(
        _argv(_write_story(tmp_path), store_root, "--no-render"),
        provider=provider,
    )
    assert code == 2
    assert provider.requests == []  # nothing was sent
    assert not (store_root / "test-story").exists()  # nothing was stored


def test_missing_story_file_errors(tmp_path: Path) -> None:
    code = main(
        _argv(tmp_path / "does-not-exist.txt", tmp_path / "store", "--provider-no-train-zdr"),
        provider=_provider(),
    )
    assert code == 2


def test_empty_story_errors(tmp_path: Path) -> None:
    empty = tmp_path / "empty.txt"
    empty.write_text("   \n", encoding="utf-8")
    code = main(
        _argv(empty, tmp_path / "store", "--provider-no-train-zdr"),
        provider=_provider(),
    )
    assert code == 2


# --- intake subcommand ---------------------------------------------------------


def _scripted_input(answers: list[str]) -> Callable[[str], str]:
    it = iter(answers)

    def _input(_prompt: str) -> str:
        return next(it)

    return _input


def _intake_args(store_root: Path) -> object:
    return build_arg_parser().parse_args(
        ["intake", "--story-id", "intake-story", "--store-root", str(store_root), "--no-render"]
    )


def test_intake_happy_path_records_consent(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    provider = _provider()
    code = _cmd_intake(
        _intake_args(store_root),
        provider=provider,
        input_fn=_scripted_input(["y", "y", "y", CHILD, ""]),  # 3 consents, name, no nickname
        story_reader=lambda: STORY,
    )
    assert code == 0

    story_dir = store_root / "intake-story"
    assert (story_dir / "story.txt").read_text(encoding="utf-8") == STORY
    # Scene script carries the token only.
    assert CHILD not in (story_dir / "scene_script.json").read_text(encoding="utf-8")
    # The intake record proves consent and carries no story text or name.
    intake = json.loads((story_dir / "intake.json").read_text(encoding="utf-8"))
    assert intake["consent"] == {
        "is_guardian": True,
        "ai_processing": True,
        "human_review_ack": True,
    }
    assert CHILD not in json.dumps(intake)
    assert "dark" not in json.dumps(intake)  # no story fragment leaked
    # Name was stripped before the provider saw it.
    assert CHILD not in provider.requests[0].prompt


def test_intake_declined_consent_submits_nothing(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    provider = _provider()
    code = _cmd_intake(
        _intake_args(store_root),
        provider=provider,
        input_fn=_scripted_input(["y", "n", "y", CHILD, ""]),  # consent #2 declined
        story_reader=lambda: STORY,
    )
    assert code == 2
    assert provider.requests == []  # nothing was generated
    assert not (store_root / "intake-story").exists()  # nothing was stored


def test_intake_shows_privacy_notice_before_consent(tmp_path: Path, capsys) -> None:
    from kathai_chithiram.intake import PRIVACY_NOTICE_DOC, PRIVACY_NOTICE_VERSION

    store_root = tmp_path / "store"
    _cmd_intake(
        _intake_args(store_root),
        provider=_provider(),
        input_fn=_scripted_input(["y", "y", "y", CHILD, ""]),
        story_reader=lambda: STORY,
    )
    out = capsys.readouterr().out
    # The notice (version + doc pointer) is shown, and before the consent prompt.
    assert PRIVACY_NOTICE_VERSION in out
    assert PRIVACY_NOTICE_DOC in out
    assert out.index(PRIVACY_NOTICE_DOC) < out.index("please confirm")


# --- review subcommand ---------------------------------------------------------


def _seed_rendered_story(store_root: Path, story_id: str = "review-story") -> None:
    """Create a story with a scene script and a rendered draft, ready to review.

    Grants ownership to the CLI's default local principal so the migrated,
    access-controlled ``kc review`` flow is authorized (ADR-004 / KC-11).
    """
    from datetime import datetime, timezone

    from kathai_chithiram.cli import _LOCAL_PRINCIPAL_ID
    from kathai_chithiram.storage import StoryArtifactStore

    store = StoryArtifactStore(store_root)
    store.create_story(
        story_id, created_at=datetime(2026, 6, 1, tzinfo=timezone.utc), story_text=STORY
    )
    store.write_scene_script(story_id, copy.deepcopy(EXAMPLE_SCENE_SCRIPT))
    store.add_media(story_id, "animation.mp4", b"\x00mp4\x01")
    store.write_grants(story_id, {"owner_id": _LOCAL_PRINCIPAL_ID, "assignments": {}})


def _review_argv(store_root: Path, *extra: str) -> list[str]:
    return ["review", "review-story", "--store-root", str(store_root), *extra]


def test_review_show_lists_the_draft(tmp_path: Path, capsys) -> None:
    store_root = tmp_path / "store"
    _seed_rendered_story(store_root)
    code = main(_review_argv(store_root, "--show"))
    assert code == 0
    out = capsys.readouterr().out
    assert "animation.mp4" in out
    assert "delivered: False" in out


def test_review_approve_marks_delivered(tmp_path: Path) -> None:
    from kathai_chithiram.storage import StoryArtifactStore

    store_root = tmp_path / "store"
    _seed_rendered_story(store_root)
    code = main(_review_argv(store_root, "--approve", "--reviewer", "alex"))
    assert code == 0
    assert StoryArtifactStore(store_root).read_metadata("review-story").delivered is True


def test_review_approve_requires_reviewer(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    _seed_rendered_story(store_root)
    code = main(_review_argv(store_root, "--approve"))
    assert code == 2


def test_review_reject_without_reason_errors(tmp_path: Path) -> None:
    from kathai_chithiram.storage import StoryArtifactStore

    store_root = tmp_path / "store"
    _seed_rendered_story(store_root)
    code = main(_review_argv(store_root, "--reject", "--reviewer", "alex"))
    assert code == 2
    assert StoryArtifactStore(store_root).read_metadata("review-story").delivered is False


def test_review_missing_story_errors(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    code = main(["review", "ghost", "--store-root", str(store_root), "--show"])
    assert code == 2


# --- access control (KC-11 / ADR-004) ------------------------------------------


def test_generate_records_owner_from_principal_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("KC_PRINCIPAL", "parent-1")
    store_root = tmp_path / "store"
    code = main(
        _argv(_write_story(tmp_path), store_root, "--provider-no-train-zdr", "--no-render"),
        provider=_provider(),
    )
    assert code == 0
    grants = json.loads((store_root / "test-story" / "grants.json").read_text(encoding="utf-8"))
    assert grants["owner_id"] == "parent-1"  # the acting principal owns what it creates


def test_review_denied_for_unrelated_principal(tmp_path: Path, monkeypatch) -> None:
    # A story owned by the default local principal is not readable by a stranger:
    # enforcement is on, not merely available (deny-by-default).
    store_root = tmp_path / "store"
    _seed_rendered_story(store_root)
    monkeypatch.setenv("KC_PRINCIPAL", "intruder")
    code = main(_review_argv(store_root, "--show"))
    assert code == 2


def _assign_argv(store_root: Path, principal: str, role: str) -> list[str]:
    return [
        "assign",
        "review-story",
        "--principal",
        principal,
        "--role",
        role,
        "--store-root",
        str(store_root),
    ]


def test_assign_lets_the_owner_grant_a_reviewer(tmp_path: Path, monkeypatch) -> None:
    store_root = tmp_path / "store"
    _seed_rendered_story(store_root)  # owned by the default local principal

    # The owner (default principal) grants the reviewer role...
    assert main(_assign_argv(store_root, "rev-1", "reviewer")) == 0
    grants = json.loads((store_root / "review-story" / "grants.json").read_text(encoding="utf-8"))
    assert grants["assignments"] == {"rev-1": "reviewer"}

    # ...and that reviewer can now read the draft, which a stranger could not.
    monkeypatch.setenv("KC_PRINCIPAL", "rev-1")
    assert main(_review_argv(store_root, "--show")) == 0


def test_assign_denied_for_non_owner(tmp_path: Path, monkeypatch) -> None:
    store_root = tmp_path / "store"
    _seed_rendered_story(store_root)
    monkeypatch.setenv("KC_PRINCIPAL", "intruder")
    assert main(_assign_argv(store_root, "rev-1", "reviewer")) == 2


def test_cli_writes_a_log_safe_audit_trail(tmp_path: Path, monkeypatch) -> None:
    from kathai_chithiram.access import AccessOutcome, JsonlAuditSink

    store_root = tmp_path / "store"
    monkeypatch.setenv("KC_PRINCIPAL", "parent-1")
    main(
        _argv(_write_story(tmp_path), store_root, "--provider-no-train-zdr", "--no-render"),
        provider=_provider(),
    )
    monkeypatch.setenv("KC_PRINCIPAL", "intruder")
    # intruder reviews the story parent-1 created -> denied, recorded.
    main(["review", "test-story", "--store-root", str(store_root), "--show"])

    events = JsonlAuditSink(store_root / "access_audit.jsonl").read()
    kinds = {(e.principal_id, e.outcome) for e in events}
    assert ("parent-1", AccessOutcome.ALLOWED) in kinds  # ownership bootstrap
    assert ("intruder", AccessOutcome.DENIED) in kinds  # refused browse recorded
    # The story text never lands in the audit log.
    assert CHILD not in (store_root / "access_audit.jsonl").read_text(encoding="utf-8")


# --- at-rest encryption (KC-5) -------------------------------------------------


def test_generate_encrypts_at_rest_when_key_set(tmp_path: Path, monkeypatch) -> None:
    from kathai_chithiram.storage import STORAGE_KEY_ENV, generate_key, load_cipher_from_env

    key = generate_key()
    monkeypatch.setenv(STORAGE_KEY_ENV, key)
    store_root = tmp_path / "store"
    code = main(
        _argv(_write_story(tmp_path), store_root, "--provider-no-train-zdr", "--no-render"),
        provider=_provider(),
    )
    assert code == 0

    # Raw story on disk is ciphertext, not the plaintext story.
    raw = (store_root / "test-story" / "story.txt").read_bytes()
    assert STORY.encode() not in raw
    # ...but it decrypts back with the key.
    cipher = load_cipher_from_env({STORAGE_KEY_ENV: key})
    from kathai_chithiram.storage import StoryArtifactStore

    encrypted = StoryArtifactStore(store_root, cipher=cipher)
    assert encrypted.read_scene_script("test-story")["title"]


def test_generate_bad_storage_key_exits(tmp_path: Path, monkeypatch) -> None:
    from kathai_chithiram.storage import STORAGE_KEY_ENV

    monkeypatch.setenv(STORAGE_KEY_ENV, "not-valid-base64 !!!")
    code = main(
        _argv(_write_story(tmp_path), tmp_path / "store", "--provider-no-train-zdr", "--no-render"),
        provider=_provider(),
    )
    assert code == 2


# --- rendering through the video seam (ADR-026) --------------------------------


def test_generate_renders_through_seam_and_stamps_provenance(tmp_path: Path, monkeypatch) -> None:
    # kc generate must render on the shared wegofwd-video seam: the draft is filed
    # under media/, and a provenance stamp is persisted alongside it — the behavior
    # the seam adds over a bare renderer.render() call. A fast fake renderer stands
    # in for matplotlib (patched in) so the CLI wiring is what's under test.
    from tests.kathai_chithiram.rendering.fake_renderer import FakeRenderer

    import kathai_chithiram.cli as cli

    monkeypatch.setattr(cli, "_load_default_renderer", lambda: FakeRenderer())
    store_root = tmp_path / "store"
    out = tmp_path / "copy.mp4"
    code = main(
        _argv(_write_story(tmp_path), store_root, "--provider-no-train-zdr", "--out", str(out)),
        provider=_provider(),
    )
    assert code == 0

    story_dir = store_root / "test-story"
    assert (story_dir / "media" / "animation.mp4").is_file()
    prov = json.loads((story_dir / "cache" / "video_provenance.json").read_text(encoding="utf-8"))
    assert prov["provider"] == "deterministic-renderer"
    assert prov["model"] == "fake"  # renderer name flows into provenance
    # The --out copy is the playable bytes the renderer produced.
    assert out.read_bytes() == b"draft-bytes"


def test_generate_seam_seals_media_and_out_copy_is_decrypted(tmp_path: Path, monkeypatch) -> None:
    # With a storage key set, the seam-filed media is encrypted at rest (KC-5),
    # while the --out convenience copy must be the DECRYPTED, playable bytes.
    from tests.kathai_chithiram.rendering.fake_renderer import FakeRenderer

    import kathai_chithiram.cli as cli
    from kathai_chithiram.storage import STORAGE_KEY_ENV, generate_key

    monkeypatch.setenv(STORAGE_KEY_ENV, generate_key())
    monkeypatch.setattr(cli, "_load_default_renderer", lambda: FakeRenderer())
    store_root = tmp_path / "store"
    out = tmp_path / "copy.mp4"
    code = main(
        _argv(_write_story(tmp_path), store_root, "--provider-no-train-zdr", "--out", str(out)),
        provider=_provider(),
    )
    assert code == 0

    story_dir = store_root / "test-story"
    # On disk the media is sealed — not the raw renderer bytes.
    assert (story_dir / "media" / "animation.mp4").read_bytes() != b"draft-bytes"
    # Provenance is persisted too (sealed; existence is enough here).
    assert (story_dir / "cache" / "video_provenance.json").is_file()
    # …but the exported copy is decrypted and directly playable.
    assert out.read_bytes() == b"draft-bytes"


# --- narration voice (--voice) -------------------------------------------------


def test_load_voice_builds_a_synthesizer_or_none():
    from kathai_chithiram.cli import _load_voice
    from kathai_chithiram.rendering import CliTtsSynthesizer

    assert _load_voice(None) is None
    voice = _load_voice("espeak-ng -w {out} {text}")
    assert isinstance(voice, CliTtsSynthesizer)


def test_load_voice_rejects_a_bad_template():
    from kathai_chithiram.cli import _load_voice

    with pytest.raises(ValueError, match="must not be empty"):
        _load_voice("")
    with pytest.raises(ValueError, match=r"\{out\}"):
        _load_voice("espeak-ng {text}")  # no {out} token


def _capture_seam_narration(monkeypatch, captured: dict) -> None:
    """Replace the CLI's render path with a fast fake that records voice + sfx."""
    import kathai_chithiram.cli as cli

    class _Result:
        media_path = Path("unused/animation.mp4")

    def _fake_seam(*, renderer, script, store, story_id, mapping, narration, sfx, filename):
        captured["narration"] = narration
        captured["sfx"] = sfx
        return _Result()

    monkeypatch.setattr(cli, "_load_default_renderer", lambda: object())
    monkeypatch.setattr(cli, "generate_story_video", _fake_seam)


def test_voice_flag_threads_a_synthesizer_into_the_seam(tmp_path: Path, monkeypatch) -> None:
    from kathai_chithiram.rendering import CliTtsSynthesizer

    captured: dict = {}
    _capture_seam_narration(monkeypatch, captured)
    code = main(
        _argv(
            _write_story(tmp_path),
            tmp_path / "store",
            "--provider-no-train-zdr",
            "--voice",
            "espeak-ng -w {out} {text}",
        ),
        provider=_provider(),
    )
    assert code == 0
    assert isinstance(captured["narration"], CliTtsSynthesizer)


def test_no_voice_flag_renders_silent(tmp_path: Path, monkeypatch) -> None:
    captured: dict = {}
    _capture_seam_narration(monkeypatch, captured)
    code = main(
        _argv(_write_story(tmp_path), tmp_path / "store", "--provider-no-train-zdr"),
        provider=_provider(),
    )
    assert code == 0
    assert captured["narration"] is None


def test_invalid_voice_template_exits_cleanly(tmp_path: Path) -> None:
    # A template missing {out} is a usage error: exit 2, and no render is attempted.
    code = main(
        _argv(
            _write_story(tmp_path),
            tmp_path / "store",
            "--provider-no-train-zdr",
            "--voice",
            "espeak-ng {text}",
        ),
        provider=_provider(),
    )
    assert code == 2


# --- sound effects (--sfx) -----------------------------------------------------


def test_load_sfx_builds_a_source_or_none(tmp_path: Path):
    from kathai_chithiram.cli import _load_sfx
    from kathai_chithiram.rendering import SoundBankSfxSynthesizer

    assert _load_sfx(None) is None
    bank = tmp_path / "sounds"
    bank.mkdir()
    source = _load_sfx(str(bank))
    assert isinstance(source, SoundBankSfxSynthesizer)


def test_load_sfx_rejects_a_missing_directory(tmp_path: Path):
    from kathai_chithiram.cli import _load_sfx

    with pytest.raises(ValueError, match="not a directory"):
        _load_sfx(str(tmp_path / "does-not-exist"))


def test_sfx_flag_threads_a_source_into_the_seam(tmp_path: Path, monkeypatch) -> None:
    from kathai_chithiram.rendering import SoundBankSfxSynthesizer

    bank = tmp_path / "sounds"
    bank.mkdir()
    captured: dict = {}
    _capture_seam_narration(monkeypatch, captured)
    code = main(
        _argv(
            _write_story(tmp_path),
            tmp_path / "store",
            "--provider-no-train-zdr",
            "--sfx",
            str(bank),
        ),
        provider=_provider(),
    )
    assert code == 0
    assert isinstance(captured["sfx"], SoundBankSfxSynthesizer)


def test_no_sfx_flag_renders_without_effects(tmp_path: Path, monkeypatch) -> None:
    captured: dict = {}
    _capture_seam_narration(monkeypatch, captured)
    code = main(
        _argv(_write_story(tmp_path), tmp_path / "store", "--provider-no-train-zdr"),
        provider=_provider(),
    )
    assert code == 0
    assert captured["sfx"] is None


def test_invalid_sfx_dir_exits_cleanly(tmp_path: Path) -> None:
    # A non-existent sound bank is a usage error: exit 2, no render attempted.
    code = main(
        _argv(
            _write_story(tmp_path),
            tmp_path / "store",
            "--provider-no-train-zdr",
            "--sfx",
            str(tmp_path / "no-such-dir"),
        ),
        provider=_provider(),
    )
    assert code == 2


# --- caption sidecar (--captions) ----------------------------------------------


def test_write_captions_helper_builds_a_named_sidecar(tmp_path: Path):
    from kathai_chithiram.cli import _write_captions
    from kathai_chithiram.rendering.silas_story import SILAS_SCENE_SCRIPT, silas_mapping

    out = tmp_path / "v.mp4"
    path = _write_captions(SILAS_SCENE_SCRIPT, silas_mapping(), out, "vtt")
    assert path == tmp_path / "v.vtt"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("WEBVTT")
    assert "Silas" in text and "CHILD" not in text  # display name, not the token


def _capture_seam_storing(monkeypatch) -> None:
    """Replace the render seam with a fake that actually stores media bytes.

    Needed for --out/--captions tests: the CLI reads the stored media back to write
    the --out copy, so the fake must persist something.
    """
    import kathai_chithiram.cli as cli

    class _Result:
        media_path = Path("unused/animation.mp4")

    def _fake_seam(*, renderer, script, store, story_id, mapping, narration, sfx, filename):
        store.add_media(story_id, filename, b"\x00\x00fake-mp4-bytes")
        return _Result()

    monkeypatch.setattr(cli, "_load_default_renderer", lambda: object())
    monkeypatch.setattr(cli, "generate_story_video", _fake_seam)


def test_captions_srt_written_next_to_out(tmp_path: Path, monkeypatch) -> None:
    _capture_seam_storing(monkeypatch)
    out = tmp_path / "vid.mp4"
    code = main(
        _argv(
            _write_story(tmp_path),
            tmp_path / "store",
            "--provider-no-train-zdr",
            "--out",
            str(out),
            "--captions",
            "srt",
        ),
        provider=_provider(),
    )
    assert code == 0
    sidecar = out.with_suffix(".srt")
    assert sidecar.exists()
    assert "-->" in sidecar.read_text(encoding="utf-8")


def test_captions_requires_out(tmp_path: Path) -> None:
    # --captions without --out is a usage error: exit 2, no sidecar, no render.
    code = main(
        _argv(
            _write_story(tmp_path),
            tmp_path / "store",
            "--provider-no-train-zdr",
            "--captions",
            "vtt",
        ),
        provider=_provider(),
    )
    assert code == 2


# --- offline generation (--offline) --------------------------------------------


def test_offline_generate_needs_no_provider(tmp_path: Path) -> None:
    from kathai_chithiram.storage import StoryArtifactStore

    store_root = tmp_path / "store"
    # No provider passed and no ZDR key: the offline path must still succeed.
    code = main(_argv(_write_story(tmp_path), store_root, "--offline", "--no-render"))
    assert code == 0

    script = StoryArtifactStore(store_root).read_scene_script("test-story")
    assert script["child_token"] == "CHILD"
    assert len(script["scenes"]) >= 1
    assert "Robin" not in str(script)  # the child's name is stripped, never stored


def test_offline_flag_ignored_when_a_provider_is_supplied(tmp_path: Path) -> None:
    # An explicit provider (e.g. a test/real LLM) takes precedence over --offline.
    from kathai_chithiram.storage import StoryArtifactStore

    store_root = tmp_path / "store"
    code = main(
        _argv(
            _write_story(tmp_path),
            store_root,
            "--offline",
            "--provider-no-train-zdr",
            "--no-render",
        ),
        provider=_provider(),
    )
    assert code == 0
    # The scripted provider returns EXAMPLE_SCENE_SCRIPT, not the offline segmentation.
    script = StoryArtifactStore(store_root).read_scene_script("test-story")
    assert script["scenes"][0]["setting"] != "a calm, quiet place"


# --- ZDR / no-training credential (KC-6) ---------------------------------------


def test_generate_fails_closed_without_zdr_key(tmp_path: Path, monkeypatch) -> None:
    from kathai_chithiram.wegofwd_llm.anthropic_provider import ZDR_API_KEY_ENV

    monkeypatch.delenv(ZDR_API_KEY_ENV, raising=False)
    store_root = tmp_path / "store"
    # No provider injected -> the CLI must resolve the dedicated ZDR key and,
    # finding none, refuse rather than fall back to a general key.
    code = main(
        _argv(_write_story(tmp_path), store_root, "--provider-no-train-zdr", "--no-render")
    )
    assert code == 2
    assert not (store_root / "test-story").exists()  # nothing generated or stored
