"""Tests for the wegofwd-llm seam request type.

The seam is text-first but may carry an optional output schema so a
structured-output-capable provider can constrain its reply; providers that
cannot honour it ignore the field.
"""

from __future__ import annotations

from kathai_chithiram.wegofwd_llm.provider import LLMRequest, ProviderConfig

CONFIG = ProviderConfig(provider_id="fake:no-train-zdr", no_training=True, zero_retention=True)


def test_output_schema_defaults_to_none() -> None:
    req = LLMRequest(prompt="p", config=CONFIG)
    assert req.output_schema is None


def test_output_schema_round_trips() -> None:
    schema = {"type": "object", "additionalProperties": False}
    req = LLMRequest(prompt="p", config=CONFIG, output_schema=schema)
    assert req.output_schema == schema
