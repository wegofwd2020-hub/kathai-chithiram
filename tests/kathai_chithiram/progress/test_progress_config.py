"""Tests for loading a ProgressPolicy from JSON config (the gated enabling seam)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kathai_chithiram.progress.config import load_policy, policy_from_mapping
from kathai_chithiram.progress.policy import Comparator, Metric

_VALID: dict = {
    "policy_id": "example-v1",
    "window": 3,
    "min_sessions": 2,
    "enabled": True,
    "rules": [
        {
            "rule_id": "advance",
            "signal": "advance",
            "conditions": [
                {"metric": "independence_rate", "comparator": ">=", "threshold": 0.8}
            ],
            "suggested_premise": "Try a slightly harder step.",
            "rationale": "Independence has held across recent sessions.",
        }
    ],
}


# ── happy path ──────────────────────────────────────────────────────────────────
def test_parses_a_valid_policy():
    policy = policy_from_mapping(_VALID)
    assert policy.policy_id == "example-v1"
    assert policy.window == 3
    assert policy.min_sessions == 2
    assert policy.enabled is True

    rule = policy.rules[0]
    assert rule.rule_id == "advance"
    assert rule.suggests
    cond = rule.conditions[0]
    assert cond.metric is Metric.INDEPENDENCE_RATE
    assert cond.comparator is Comparator.GE
    assert cond.threshold == 0.8


def test_load_policy_reads_a_file(tmp_path: Path):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(_VALID), encoding="utf-8")
    policy = load_policy(path)
    assert policy.policy_id == "example-v1"


def test_a_rule_may_signal_without_suggesting():
    data = {**_VALID, "rules": [
        {"rule_id": "hold", "signal": "hold",
         "conditions": [{"metric": "refusal_rate", "comparator": ">", "threshold": 0.5}]}
    ]}
    policy = policy_from_mapping(data)
    assert not policy.rules[0].suggests


# ── validation / errors ─────────────────────────────────────────────────────────
def test_missing_required_field_is_rejected():
    data = {k: v for k, v in _VALID.items() if k != "window"}
    with pytest.raises(ValueError, match="window"):
        policy_from_mapping(data)


def test_unknown_metric_is_rejected():
    data = {**_VALID, "rules": [
        {"rule_id": "r", "signal": "s",
         "conditions": [{"metric": "vibes", "comparator": ">=", "threshold": 0.5}]}
    ]}
    with pytest.raises(ValueError, match="not a valid metric"):
        policy_from_mapping(data)


def test_unknown_comparator_is_rejected():
    data = {**_VALID, "rules": [
        {"rule_id": "r", "signal": "s",
         "conditions": [{"metric": "mean_mood", "comparator": "~=", "threshold": 3.0}]}
    ]}
    with pytest.raises(ValueError, match="not a valid comparator"):
        policy_from_mapping(data)


def test_out_of_range_threshold_is_rejected_by_the_schema():
    # independence_rate is a 0-1 rate; 5.0 is out of range (a config typo).
    data = {**_VALID, "rules": [
        {"rule_id": "r", "signal": "s",
         "conditions": [{"metric": "independence_rate", "comparator": ">=", "threshold": 5.0}]}
    ]}
    with pytest.raises(ValueError, match="range"):
        policy_from_mapping(data)


def test_non_object_policy_is_rejected():
    with pytest.raises(ValueError, match="must be a JSON object"):
        policy_from_mapping(["not", "an", "object"])


def test_invalid_json_file_is_rejected(tmp_path: Path):
    path = tmp_path / "policy.json"
    path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        load_policy(path)


def test_shipped_policy_template_loads_and_is_inert():
    # The collaborator's starter template must load + validate, and ship disabled so
    # it cannot emit a suggestion until a clinician deliberately turns it on.
    examples = Path(__file__).resolve().parents[3] / "docs" / "examples"
    policy = load_policy(examples / "progress_policy.template.json")
    assert policy.enabled is False  # inert by construction
    assert policy.window >= 1 and 1 <= policy.min_sessions <= policy.window
    assert len(policy.rules) >= 1
