"""At-rest encryption for the people registry (opt-in, master cipher)."""

from __future__ import annotations

import base64
import json

import pytest

from kathai_chithiram.errors import PeopleError
from kathai_chithiram.people.models import AgeBand, Child, Family
from kathai_chithiram.people.registry import PeopleRegistry
from kathai_chithiram.storage import STORAGE_KEY_ENV
from kathai_chithiram.storage.crypto import AesGcmCipher, generate_key


def _cipher() -> AesGcmCipher:
    return AesGcmCipher(base64.urlsafe_b64decode(generate_key()))


def _sample() -> PeopleRegistry:
    reg = PeopleRegistry()
    reg.add_family(Family(family_id="fam-1", owner_id="par-1", member_ids=frozenset({"par-1"})))
    reg.add_child(Child(child_id="kid-1", family_id="fam-1", age_band=AgeBand.AGE_6_8))
    return reg


def test_encrypted_round_trip(tmp_path):
    path = tmp_path / "people.json"
    cipher = _cipher()
    _sample().save(path, cipher=cipher)
    raw = path.read_bytes()
    # Real encryption: not JSON-parseable and the age-band token is absent on disk.
    # (AES-GCM ciphertext is not valid UTF-8, so json.loads on bytes fails at the
    # decode step with UnicodeDecodeError before it can even attempt to parse JSON.)
    with pytest.raises((UnicodeDecodeError, json.JSONDecodeError)):
        json.loads(raw)
    assert b"6-8" not in raw
    loaded = PeopleRegistry.load(path, cipher=cipher)
    assert loaded.get_child("kid-1").age_band is AgeBand.AGE_6_8


def test_plaintext_round_trip_unchanged(tmp_path):
    path = tmp_path / "people.json"
    _sample().save(path)  # cipher=None
    raw = path.read_bytes()
    json.loads(raw)  # valid JSON, as before
    loaded = PeopleRegistry.load(path)
    assert loaded.get_child("kid-1").age_band is AgeBand.AGE_6_8


def test_legacy_plaintext_loads_under_a_cipher_then_migrates(tmp_path):
    path = tmp_path / "people.json"
    _sample().save(path)  # legacy plaintext on disk
    cipher = _cipher()
    loaded = PeopleRegistry.load(path, cipher=cipher)  # decrypt-first fails → plaintext fallback
    assert loaded.get_child("kid-1").age_band is AgeBand.AGE_6_8
    loaded.save(path, cipher=cipher)  # migrate
    with pytest.raises((UnicodeDecodeError, json.JSONDecodeError)):
        json.loads(path.read_bytes())


def test_encrypted_file_fails_closed_without_key(tmp_path):
    path = tmp_path / "people.json"
    _sample().save(path, cipher=_cipher())
    with pytest.raises(PeopleError):
        PeopleRegistry.load(path)  # no key → cannot read → fails closed


def test_wrong_key_fails_closed(tmp_path):
    path = tmp_path / "people.json"
    _sample().save(path, cipher=_cipher())
    with pytest.raises(PeopleError):
        PeopleRegistry.load(path, cipher=_cipher())  # different random key


def test_absent_file_is_empty_registry(tmp_path):
    reg = PeopleRegistry.load(tmp_path / "missing.json", cipher=_cipher())
    assert list(reg.children_of("fam-1")) == []


def test_cli_helpers_round_trip_encrypted(tmp_path, monkeypatch):
    from kathai_chithiram import cli
    monkeypatch.setenv(STORAGE_KEY_ENV, generate_key())
    path = tmp_path / "people.json"
    cli._save_people(_sample(), path)
    with pytest.raises((UnicodeDecodeError, json.JSONDecodeError)):
        json.loads(path.read_bytes())  # CLI wrote it encrypted
    loaded = cli._load_people(path)
    assert loaded.get_child("kid-1").age_band is AgeBand.AGE_6_8


def test_cli_helpers_plaintext_without_key(tmp_path, monkeypatch):
    from kathai_chithiram import cli
    monkeypatch.delenv(STORAGE_KEY_ENV, raising=False)
    path = tmp_path / "people.json"
    cli._save_people(_sample(), path)
    json.loads(path.read_bytes())  # no key → plaintext
    assert cli._load_people(path).get_child("kid-1").age_band is AgeBand.AGE_6_8


def test_open_guarded_store_reads_encrypted_registry(tmp_path, monkeypatch):
    """Regression test: _open_guarded_store must thread cipher into registry load."""
    from kathai_chithiram import cli
    monkeypatch.setenv(STORAGE_KEY_ENV, generate_key())
    monkeypatch.setenv("KC_PRINCIPAL", "par-1")
    people = tmp_path / "people.json"
    cli._save_people(_sample(), people)  # encrypted on disk
    guarded = cli._open_guarded_store(tmp_path / "store", people_file=people)
    assert guarded is not None  # registry loaded despite encryption; would be None if load failed


def test_non_dict_json_fails_closed(tmp_path):
    path = tmp_path / "people.json"
    path.write_text("123", encoding="utf-8")  # valid JSON, not a dict
    with pytest.raises(PeopleError):
        PeopleRegistry.load(path)


def test_non_dict_json_fails_closed_encrypted(tmp_path):
    path = tmp_path / "people.json"
    cipher = _cipher()
    path.write_bytes(cipher.encrypt(b"123"))  # decrypts to valid-but-non-dict JSON
    with pytest.raises(PeopleError):
        PeopleRegistry.load(path, cipher=cipher)
