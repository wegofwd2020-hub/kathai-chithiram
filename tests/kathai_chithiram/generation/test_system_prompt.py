"""Tests for the content-safety generation system prompt (KC-4)."""

from __future__ import annotations

from kathai_chithiram.generation import (
    MUST,
    MUST_NOT,
    build_generation_system_prompt,
)


def test_prompt_includes_every_must_and_must_not_rule() -> None:
    prompt = build_generation_system_prompt()
    for rule in MUST:
        assert rule in prompt
    for rule in MUST_NOT:
        assert rule in prompt


def test_prompt_encodes_key_safety_clauses() -> None:
    prompt = build_generation_system_prompt().lower()
    assert "flashing" in prompt or "strobing" in prompt
    assert "medical" in prompt  # no medical claims / diagnoses
    assert "social stories" in prompt
    # Distress is transformed, not reproduced.
    assert "supportive" in prompt and "distress" in prompt


def test_prompt_instructs_token_usage_not_real_name() -> None:
    prompt = build_generation_system_prompt()
    assert "CHILD" in prompt
    assert "Never write a real name" in prompt


def test_prompt_uses_custom_token() -> None:
    prompt = build_generation_system_prompt(child_token="KIDDO")
    assert "KIDDO" in prompt


def test_prompt_requires_contract_conformant_output() -> None:
    prompt = build_generation_system_prompt().lower()
    assert "scene script" in prompt
