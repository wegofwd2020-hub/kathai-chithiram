"""Load a collaborator-authored ``ProgressPolicy`` from a JSON config (the gate).

Loading a policy is the **enabling** step for the M1 engine, and it is deliberately
the only way a real policy enters the interpreter. This module ships **no policy** —
every value in the file is the collaborator's clinical judgment (ADR-002 Decision
7.1, ADR-003 Decision 2). Engineering owns this parser; a policy must not be loaded
in production until the ADR-002 Decision 7 gate opens (7.1 collaborator authorship,
7.4 clinical-copy review, 7.6 DPIA progress-profiling touchpoint). The parser only
constructs the schema types, so every clinical invariant is still enforced by their
own validation — a malformed or out-of-range policy is rejected, not best-guessed.

Config shape (JSON)::

    {
      "policy_id": "example-v1", "window": 6, "min_sessions": 3, "enabled": true,
      "rules": [
        {"rule_id": "advance", "signal": "advance",
         "conditions": [{"metric": "independence_rate", "comparator": ">=",
                         "threshold": 0.8}],
         "suggested_premise": "...", "rationale": "..."}
      ]
    }
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from kathai_chithiram.progress.policy import (
    Comparator,
    Condition,
    Metric,
    ProgressPolicy,
    ThresholdRule,
)

__all__ = ["load_policy", "policy_from_mapping"]


def load_policy(path: str | Path) -> ProgressPolicy:
    """Read and parse a ``ProgressPolicy`` from a JSON file at ``path``.

    Args:
        path: The policy JSON file (collaborator-authored).

    Returns:
        The validated :class:`ProgressPolicy`.

    Raises:
        OSError: If the file cannot be read.
        ValueError: If the file is not valid JSON, or the policy is malformed /
            violates a schema invariant.
    """
    text = Path(path).read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"policy file is not valid JSON: {exc}") from exc
    return policy_from_mapping(data)


def policy_from_mapping(data: Any) -> ProgressPolicy:
    """Build a :class:`ProgressPolicy` from a decoded mapping.

    Args:
        data: The decoded policy object.

    Returns:
        The validated :class:`ProgressPolicy`.

    Raises:
        ValueError: If a required field is missing or any value is invalid (the
            schema types enforce the clinical invariants).
    """
    if not isinstance(data, Mapping):
        raise ValueError("policy must be a JSON object")
    rules_raw = data.get("rules", [])
    if not isinstance(rules_raw, list):
        raise ValueError("policy 'rules' must be a list")
    rules = tuple(_rule(rule, index) for index, rule in enumerate(rules_raw))
    return ProgressPolicy(
        policy_id=_require(data, "policy_id"),
        window=_require(data, "window"),
        min_sessions=_require(data, "min_sessions"),
        rules=rules,
        enabled=_require(data, "enabled"),
    )


def _rule(raw: Any, index: int) -> ThresholdRule:
    """Build one :class:`ThresholdRule` from a mapping."""
    if not isinstance(raw, Mapping):
        raise ValueError(f"rule #{index} must be a JSON object")
    conditions_raw = raw.get("conditions", [])
    if not isinstance(conditions_raw, list):
        raise ValueError(f"rule #{index} 'conditions' must be a list")
    conditions = tuple(_condition(cond, index, j) for j, cond in enumerate(conditions_raw))
    return ThresholdRule(
        rule_id=_require(raw, "rule_id"),
        conditions=conditions,
        signal=_require(raw, "signal"),
        suggested_premise=raw.get("suggested_premise"),
        rationale=raw.get("rationale"),
    )


def _condition(raw: Any, rule_index: int, cond_index: int) -> Condition:
    """Build one :class:`Condition` from a mapping."""
    if not isinstance(raw, Mapping):
        raise ValueError(f"rule #{rule_index} condition #{cond_index} must be a JSON object")
    return Condition(
        metric=_enum(Metric, _require(raw, "metric"), "metric"),
        comparator=_enum(Comparator, _require(raw, "comparator"), "comparator"),
        threshold=_require(raw, "threshold"),
    )


def _require(data: Mapping[str, Any], key: str) -> Any:
    """Return ``data[key]`` or raise a clear error naming the missing field."""
    if key not in data:
        raise ValueError(f"policy: missing required field {key!r}")
    return data[key]


def _enum(enum_type: Any, value: Any, kind: str) -> Any:
    """Resolve ``value`` to a member of ``enum_type`` (its ``.value``)."""
    try:
        return enum_type(value)
    except ValueError as exc:
        allowed = [member.value for member in enum_type]
        raise ValueError(f"{value!r} is not a valid {kind}; expected one of {allowed}") from exc
