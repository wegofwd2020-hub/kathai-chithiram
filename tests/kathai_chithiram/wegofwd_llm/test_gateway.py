"""Tests for the wegofwd-llm seam (KC-2).

Asserts the three acceptance criteria: the name is gone from the outbound
payload before any provider call, no raw story text / name reaches the logs,
and the provider's no-training / zero-retention config is recorded per request.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pytest
from mock_story import (
    MOCK_CHILD_NAME,
    MOCK_STORY,
    CapturingProvider,
    ExplodingProvider,
)

from kathai_chithiram.errors import IdentifierLeakError, ProviderConfigError
from kathai_chithiram.privacy import NameMapping
from kathai_chithiram.wegofwd_llm import ProviderConfig, run_generation

COMPLIANT = ProviderConfig(provider_id="fake:no-train-zdr", no_training=True, zero_retention=True)


def _mapping() -> NameMapping:
    return NameMapping.for_child(MOCK_CHILD_NAME)


def test_outbound_payload_contains_no_name() -> None:
    provider = CapturingProvider()
    run_generation(
        story_text=MOCK_STORY,
        mapping=_mapping(),
        provider=provider,
        config=COMPLIANT,
        request_id="req-1",
    )
    assert len(provider.requests) == 1
    sent = provider.requests[0].prompt
    assert MOCK_CHILD_NAME not in sent
    assert "Milo" not in sent
    assert "CHILD" in sent  # the token took its place


def test_real_name_never_reaches_logs(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        run_generation(
            story_text=MOCK_STORY,
            mapping=_mapping(),
            provider=CapturingProvider(),
            config=COMPLIANT,
            request_id="req-1",
        )
    assert "wegofwd-llm dispatch" in caplog.text
    assert MOCK_CHILD_NAME not in caplog.text
    # No raw story fragment should appear either.
    assert "toothbrush" not in caplog.text and "dentist" not in caplog.text


def test_provider_config_recorded_per_request() -> None:
    clock = lambda: datetime(2026, 6, 13, tzinfo=timezone.utc)  # noqa: E731 (terse test clock)
    result = run_generation(
        story_text=MOCK_STORY,
        mapping=_mapping(),
        provider=CapturingProvider(),
        config=COMPLIANT,
        request_id="req-42",
        clock=clock,
    )
    record = result.record
    assert record.request_id == "req-42"
    assert record.provider_id == "fake:no-train-zdr"
    assert record.no_training is True
    assert record.zero_retention is True
    assert record.prompt_chars > 0
    assert record.created_at == datetime(2026, 6, 13, tzinfo=timezone.utc)


def test_response_is_returned() -> None:
    result = run_generation(
        story_text=MOCK_STORY,
        mapping=_mapping(),
        provider=CapturingProvider(reply="generated"),
        config=COMPLIANT,
        request_id="req-1",
    )
    assert result.response.text == "generated"


@pytest.mark.parametrize(
    "config",
    [
        ProviderConfig(provider_id="fake:trains", no_training=False, zero_retention=True),
        ProviderConfig(provider_id="fake:retains", no_training=True, zero_retention=False),
        ProviderConfig(provider_id="fake:neither", no_training=False, zero_retention=False),
    ],
)
def test_noncompliant_provider_rejected_before_dispatch(config: ProviderConfig) -> None:
    with pytest.raises(ProviderConfigError):
        run_generation(
            story_text=MOCK_STORY,
            mapping=_mapping(),
            provider=ExplodingProvider(),  # would raise if reached
            config=config,
            request_id="req-1",
        )


def test_blank_request_id_rejected() -> None:
    with pytest.raises(ValueError, match="request_id"):
        run_generation(
            story_text=MOCK_STORY,
            mapping=_mapping(),
            provider=CapturingProvider(),
            config=COMPLIANT,
            request_id="   ",
        )


def test_leak_guard_blocks_dispatch(caplog: pytest.LogCaptureFixture) -> None:
    # A mapping whose token *is* one of the identifiers can never be cleaned:
    # pseudonymize maps "Milo" -> "MILO", which still matches the identifier
    # "MILO" (case-insensitive). The guard must catch this and refuse to send.
    mapping = NameMapping(identifiers=("Milo", "MILO"), token="MILO")
    provider = ExplodingProvider()
    with caplog.at_level(logging.WARNING):
        with pytest.raises(IdentifierLeakError) as exc:
            run_generation(
                story_text=MOCK_STORY,
                mapping=mapping,
                provider=provider,
                config=COMPLIANT,
                request_id="req-leak",
            )
    assert exc.value.residual_count > 0
    assert MOCK_CHILD_NAME not in caplog.text
