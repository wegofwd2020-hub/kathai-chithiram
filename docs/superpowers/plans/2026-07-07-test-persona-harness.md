# Test-Persona Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a test-only persona layer (parent/child/therapist) with synthetic committed handles and a git-ignored local override for the owner's three real inboxes.

**Architecture:** Everything lives under `tests/kathai_chithiram/people/`. A `Persona` value type pairs a domain opaque id with an email-shaped login handle. Builders assemble a consent-gated, grant-wired family from the existing `people` domain + `PeopleRegistry`. A resolver overlays real inboxes from a git-ignored `personas.local.json` when present, falling back to `@example.test` placeholders otherwise. No `src/` changes.

**Tech Stack:** Python 3.12, `dataclasses`, `pathlib`, `json`, `pytest`. Domain types from `kathai_chithiram.people.models`, `kathai_chithiram.people.registry.PeopleRegistry`, `kathai_chithiram.access.principal.Role`.

## Global Constraints

- No `src/` changes — the harness is test-side only.
- No email/name/DOB added to the domain model (DPIA A8, Art. 5(1)(c)).
- Committed login handles MUST end in `@example.test`. Real addresses only ever in git-ignored `personas.local.json`.
- Opaque ids match `^[A-Za-z0-9_-]+$` (hyphens allowed).
- No real child data in fixtures (CLAUDE.md); every new function ships a test.
- `ParentalConsent.granted_at` must be timezone-aware.
- `Family.owner_id` must be a member of `Family.member_ids`.

---

### Task 1: Personas + family builders

**Files:**
- Create: `tests/kathai_chithiram/people/mock_personas.py`
- Test: `tests/kathai_chithiram/people/test_mock_personas.py`

**Interfaces:**
- Consumes: `kathai_chithiram.people.models` (`Family`, `Parent`, `Child`, `Therapist`, `ParentalConsent`, `AgeBand`); `kathai_chithiram.people.registry.PeopleRegistry`; `kathai_chithiram.access.principal.Role`.
- Produces:
  - `Persona(key: str, subject_id: str, login_handle: str)` — frozen dataclass.
  - Constants `PARENT`, `CHILD`, `THERAPIST` (`Persona`).
  - `FAMILY_ID: str`, `POLICY_VERSION: str`.
  - `mock_family() -> Family`
  - `mock_registry() -> PeopleRegistry` — family + child + therapist added, therapist assigned to child (`Role.THERAPIST`), parental consent recorded.

- [ ] **Step 1: Write the failing test**

```python
# tests/kathai_chithiram/people/test_mock_personas.py
"""Tests for the synthetic test-persona harness."""

from __future__ import annotations

from kathai_chithiram.access.principal import Role
from kathai_chithiram.people.models import AgeBand, Family

from tests.kathai_chithiram.people import mock_personas as mp


def test_personas_have_stable_ids_and_placeholder_handles():
    assert mp.PARENT.subject_id == "parent-mock-001"
    assert mp.CHILD.subject_id == "child-mock-001"
    assert mp.THERAPIST.subject_id == "therapist-mock-001"
    for persona in (mp.PARENT, mp.CHILD, mp.THERAPIST):
        assert persona.login_handle.endswith("@example.test")


def test_mock_family_is_valid():
    family = mp.mock_family()
    assert isinstance(family, Family)
    assert family.owner_id == mp.PARENT.subject_id
    assert mp.PARENT.subject_id in family.member_ids


def test_mock_registry_wires_consent_and_therapist_grant():
    reg = mp.mock_registry()
    assert reg.has_consent(mp.CHILD.subject_id) is True
    grants = reg.child_grants(mp.CHILD.subject_id)
    assert grants.assignments.get(mp.THERAPIST.subject_id) == Role.THERAPIST
    assert mp.PARENT.subject_id in grants.family_member_ids


def test_child_persona_uses_an_age_band_not_a_dob():
    reg = mp.mock_registry()
    child = reg.get_child(mp.CHILD.subject_id)
    assert isinstance(child.age_band, AgeBand)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/kathai_chithiram/people/test_mock_personas.py -v`
Expected: FAIL — `ModuleNotFoundError` / `AttributeError` (mock_personas not defined).

- [ ] **Step 3: Write minimal implementation**

```python
# tests/kathai_chithiram/people/mock_personas.py
"""Synthetic test personas for the people/family domain.

A test-only layer (CLAUDE.md: no real data in fixtures). Pairs each domain
opaque id with an email-shaped ``login_handle``; the domain model itself holds
no email. Committed handles are always ``@example.test`` — the owner's real
inboxes are supplied at runtime via the git-ignored ``personas.local.json``
override (see :mod:`resolve_handles`), never committed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from kathai_chithiram.access.principal import Role
from kathai_chithiram.people.models import (
    AgeBand,
    Child,
    Family,
    ParentalConsent,
    Parent,
    Therapist,
)
from kathai_chithiram.people.registry import PeopleRegistry

__all__ = [
    "Persona",
    "PARENT",
    "CHILD",
    "THERAPIST",
    "FAMILY_ID",
    "POLICY_VERSION",
    "mock_family",
    "mock_registry",
]

#: Opaque family id shared by the mock personas.
FAMILY_ID = "fam-mock-001"

#: Synthetic consent policy version (not a real notice version).
POLICY_VERSION = "v0-mock"


@dataclass(frozen=True)
class Persona:
    """A synthetic test identity: a domain opaque id plus a login handle.

    Attributes:
        key: The override-lookup key (``"parent"`` / ``"child"`` / ``"therapist"``).
        subject_id: The opaque id used in the domain layer (a principal id for the
            parent/therapist, the child id for the child).
        login_handle: An email-shaped handle. Committed value ends in
            ``@example.test``; the owner's real inbox overrides it at runtime only.
    """

    key: str
    subject_id: str
    login_handle: str


#: The owning parent of the mock family.
PARENT = Persona("parent", "parent-mock-001", "parent@example.test")

#: The child in the mock family (addressed via the guardian inbox for delivery E2E).
CHILD = Persona("child", "child-mock-001", "child@example.test")

#: A therapist assigned to the mock child.
THERAPIST = Persona("therapist", "therapist-mock-001", "therapist@example.test")


def mock_family() -> Family:
    """Return the synthetic :class:`Family` for the mock personas.

    Returns:
        A one-parent family owned by :data:`PARENT`.
    """
    return Family(
        family_id=FAMILY_ID,
        owner_id=PARENT.subject_id,
        member_ids=frozenset({PARENT.subject_id}),
    )


def mock_registry() -> PeopleRegistry:
    """Return a :class:`PeopleRegistry` with the mock family fully wired.

    The family, child, and therapist are registered; the therapist is assigned to
    the child (``Role.THERAPIST``); and parental consent is recorded so the child's
    content is consent-gated.

    Returns:
        A ready-to-use registry for consent-gated, grant-wired tests.
    """
    reg = PeopleRegistry()
    reg.add_family(mock_family())
    reg.add_child(
        Child(
            child_id=CHILD.subject_id,
            family_id=FAMILY_ID,
            age_band=AgeBand.AGE_6_8,
        )
    )
    reg.add_therapist(Therapist(principal_id=THERAPIST.subject_id))
    reg.assign(CHILD.subject_id, THERAPIST.subject_id, Role.THERAPIST)
    reg.record_consent(
        ParentalConsent(
            consenting_parent_id=PARENT.subject_id,
            child_id=CHILD.subject_id,
            policy_version=POLICY_VERSION,
            granted_at=datetime.now(timezone.utc),
        )
    )
    return reg
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/kathai_chithiram/people/test_mock_personas.py -v`
Expected: PASS (4 tests). If `Parent` is flagged as unused-import by ruff, keep it — it documents the family role; otherwise remove it. Run `ruff check tests/kathai_chithiram/people/mock_personas.py` and fix any unused import it reports.

- [ ] **Step 5: Commit**

```bash
git add tests/kathai_chithiram/people/mock_personas.py tests/kathai_chithiram/people/test_mock_personas.py
git commit -m "test: synthetic persona harness — Persona + family builders

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Handle resolver + local override + safety guards

**Files:**
- Modify: `tests/kathai_chithiram/people/mock_personas.py` (add resolver)
- Create: `tests/kathai_chithiram/people/personas.local.example.json`
- Modify: `.gitignore`
- Test: `tests/kathai_chithiram/people/test_mock_personas.py` (add resolver + guard tests)

**Interfaces:**
- Consumes: `PARENT`, `CHILD`, `THERAPIST` from Task 1.
- Produces:
  - `DEFAULT_LOCAL_PATH: Path` — `<this dir>/personas.local.json`.
  - `resolve_handles(path: Path | None = None) -> dict[str, str]` — keys `"parent"`, `"child"`, `"therapist"`; placeholder handles overridden by the local file when present; unknown keys in the file ignored.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/kathai_chithiram/people/test_mock_personas.py
import json
import re
from pathlib import Path


def test_resolve_handles_defaults_to_placeholders(tmp_path):
    # Point at a non-existent file so the real personas.local.json can't interfere.
    handles = mp.resolve_handles(tmp_path / "absent.json")
    assert handles == {
        "parent": "parent@example.test",
        "child": "child@example.test",
        "therapist": "therapist@example.test",
    }


def test_resolve_handles_applies_local_override(tmp_path):
    local = tmp_path / "personas.local.json"
    local.write_text(
        json.dumps(
            {
                "parent": "me+parent@gmail.test",
                "therapist": "me+ot@gmail.test",
                "bogus": "ignored@gmail.test",
            }
        )
    )
    handles = mp.resolve_handles(local)
    assert handles["parent"] == "me+parent@gmail.test"
    assert handles["therapist"] == "me+ot@gmail.test"
    # Unspecified key keeps its placeholder; unknown key is dropped.
    assert handles["child"] == "child@example.test"
    assert "bogus" not in handles


def test_committed_module_contains_no_real_email():
    source = Path(mp.__file__).read_text()
    emails = re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", source)
    assert emails, "expected the placeholder handles to be present"
    for email in emails:
        assert email.endswith("@example.test"), f"non-placeholder email committed: {email}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/kathai_chithiram/people/test_mock_personas.py -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'resolve_handles'`.

- [ ] **Step 3: Write minimal implementation**

Add to the imports of `mock_personas.py`:

```python
import json
from pathlib import Path
```

Add `"DEFAULT_LOCAL_PATH"` and `"resolve_handles"` to `__all__`, then append:

```python
#: The keys the override file may set; anything else is ignored.
_PERSONA_KEYS = ("parent", "child", "therapist")

#: Default location of the git-ignored real-inbox override (owner's machine only).
DEFAULT_LOCAL_PATH = Path(__file__).parent / "personas.local.json"


def resolve_handles(path: Path | None = None) -> dict[str, str]:
    """Return each persona's effective login handle, applying a local override.

    Committed placeholders (``@example.test``) are returned unless a
    ``personas.local.json`` file exists, in which case its values override the
    matching keys — for the owner's manual end-to-end runs only. Only the three
    known persona keys are honoured; any other key in the file is ignored.

    Args:
        path: Override file location. Defaults to :data:`DEFAULT_LOCAL_PATH`.

    Returns:
        A dict mapping ``"parent"`` / ``"child"`` / ``"therapist"`` to a handle.

    Raises:
        ValueError: If the override file exists but is not a JSON object.
    """
    handles = {
        "parent": PARENT.login_handle,
        "child": CHILD.login_handle,
        "therapist": THERAPIST.login_handle,
    }
    local = path if path is not None else DEFAULT_LOCAL_PATH
    if not local.exists():
        return handles
    try:
        overrides = json.loads(local.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"{local} is not valid JSON: {exc}") from exc
    if not isinstance(overrides, dict):
        raise ValueError(f"{local} must contain a JSON object of handle overrides")
    for key in _PERSONA_KEYS:
        if key in overrides:
            handles[key] = str(overrides[key])
    return handles
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/kathai_chithiram/people/test_mock_personas.py -v`
Expected: PASS (7 tests total).

- [ ] **Step 5: Add the git-ignore entry and committed example template**

Append to `.gitignore` (under the `# Personal story data — NEVER commit` block):

```
# Test-persona real-inbox override (owner's machine only)
tests/kathai_chithiram/people/personas.local.json
```

Create `tests/kathai_chithiram/people/personas.local.example.json`:

```json
{
  "parent": "you+parent@example.test",
  "child": "you+child@example.test",
  "therapist": "you+therapist@example.test"
}
```

- [ ] **Step 6: Verify the override is ignored by git**

Run: `printf '{}' > tests/kathai_chithiram/people/personas.local.json && git check-ignore tests/kathai_chithiram/people/personas.local.json && rm tests/kathai_chithiram/people/personas.local.json`
Expected: prints the path (ignored), then removes it. If it prints nothing, the `.gitignore` entry is wrong — fix it.

- [ ] **Step 7: Run the full people test suite + lint**

Run: `pytest tests/kathai_chithiram/people/ -v && ruff check tests/kathai_chithiram/people/`
Expected: all PASS, no lint errors.

- [ ] **Step 8: Commit**

```bash
git add tests/kathai_chithiram/people/mock_personas.py tests/kathai_chithiram/people/test_mock_personas.py tests/kathai_chithiram/people/personas.local.example.json .gitignore
git commit -m "test: persona handle resolver with git-ignored local override

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the implementer

- Import convention is confirmed: sibling tests use absolute `from tests.kathai_chithiram.people import ...` (e.g. `tests/kathai_chithiram/rendering/test_sfx.py` imports `from tests.kathai_chithiram.scene_script.mock_scripts import ...`). There is no `__init__.py` in the package — do not add one.
- Do not create or commit `personas.local.json`. Only the `.example.json` template is committed.
- The child persona keeps a handle deliberately — it addresses the guardian inbox for delivery E2E; the child does not log in.
