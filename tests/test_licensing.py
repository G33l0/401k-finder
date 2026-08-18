"""Licensing: signed keys, issued by the owner and checked offline."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.licensing import ed25519, keys, storage
from app.licensing.config import LicenseConfig
from app.licensing.gate import LicenseGate
from app.licensing.models import LicenseState

MACHINE = "2580db0d3f7e83ff3759d14a76731aa2"
OTHER_MACHINE = "ffeeddccbbaa99887766554433221100"


@pytest.fixture(scope="module")
def seed() -> bytes:
    return ed25519.generate_seed()


@pytest.fixture(scope="module")
def public_key(seed) -> str:
    return ed25519.public_key(seed).hex()


@pytest.fixture()
def gate(public_key, monkeypatch, tmp_path, isolated_data_dir) -> LicenseGate:
    """A gate for this machine, with its own licence file."""

    monkeypatch.setattr(storage, "license_path", lambda: tmp_path / "license.json")
    monkeypatch.setattr("app.licensing.gate.machine_fingerprint", lambda: MACHINE)

    return LicenseGate(LicenseConfig(public_key=public_key))


RFC_8032_KEYS = [
    (
        "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
        "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
    ),
    (
        "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
        "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
    ),
]

RFC_8032_SIGNATURE = (
    "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
    "72",
    "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da"
    "085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00",
)


@pytest.mark.parametrize("secret,public", RFC_8032_KEYS)
def test_public_keys_match_rfc_8032(secret, public):
    assert ed25519.public_key(bytes.fromhex(secret)).hex() == public


def test_signature_matches_rfc_8032():
    secret, message, expected = RFC_8032_SIGNATURE

    assert ed25519.sign(bytes.fromhex(message), bytes.fromhex(secret)).hex() == expected


def test_rfc_8032_signature_verifies():
    secret, message, expected = RFC_8032_SIGNATURE
    public = ed25519.public_key(bytes.fromhex(secret))

    assert ed25519.verify(bytes.fromhex(message), bytes.fromhex(expected), public)


def test_signatures_round_trip(seed, public_key):
    message = b"the quick brown fox"
    signature = ed25519.sign(message, seed)

    assert ed25519.verify(message, signature, bytes.fromhex(public_key))
    assert not ed25519.verify(b"a different message", signature, bytes.fromhex(public_key))


def test_verification_rejects_malformed_input_rather_than_raising(public_key):
    """Signatures here come from a text box, so nothing may raise."""

    key = bytes.fromhex(public_key)

    for signature in (b"", b"\x00" * 63, b"\xff" * 64, b"short"):
        assert ed25519.verify(b"message", signature, key) is False

    assert ed25519.verify(b"message", b"\x00" * 64, b"") is False
    assert ed25519.verify(b"message", b"\x00" * 64, b"\xff" * 31) is False


def test_a_signature_cannot_be_reshaped_into_another(seed, public_key):
    """Non-canonical S values must be refused, or one signature becomes many."""

    message = b"licence payload"
    signature = ed25519.sign(message, seed)

    scalar = int.from_bytes(signature[32:], "little") + ed25519.L
    malleable = signature[:32] + scalar.to_bytes(32, "little")

    assert not ed25519.verify(message, malleable, bytes.fromhex(public_key))


def test_a_seed_must_be_the_right_size():
    for bad in (b"", b"\x00" * 31, b"\x00" * 33):
        with pytest.raises(ValueError):
            ed25519.public_key(bad)


def test_a_key_round_trips(seed, public_key):
    key = keys.issue(MACHINE, seed, label="Acme Corp")
    outcome = keys.check(key, public_key, MACHINE)

    assert outcome.ok
    assert outcome.key is not None
    assert outcome.key.label == "Acme Corp"
    assert outcome.key.perpetual


def test_a_key_is_bound_to_one_machine(seed, public_key):
    """The whole point: a key cannot be passed to a colleague."""

    key = keys.issue(MACHINE, seed, label="Acme Corp")

    assert keys.check(key, public_key, OTHER_MACHINE).state is LicenseState.WRONG_MACHINE


def test_a_key_signed_by_anyone_else_is_refused(public_key):
    """A keygen built from the shipped binary is what this prevents."""

    rogue = ed25519.generate_seed()
    key = keys.issue(MACHINE, rogue, label="Pirate")

    assert keys.check(key, public_key, MACHINE).state is LicenseState.INVALID


@pytest.mark.parametrize("at", [3, 20, 90, 140])
def test_altering_any_part_of_a_key_invalidates_it(seed, public_key, at):
    clean = keys.normalise(keys.issue(MACHINE, seed, label="Acme Corp"))
    swapped = "B" if clean[at] != "B" else "C"
    tampered = clean[:at] + swapped + clean[at + 1 :]

    assert keys.check(tampered, public_key, MACHINE).state is not LicenseState.ACTIVE


def test_a_truncated_key_is_refused(seed, public_key):
    key = keys.normalise(keys.issue(MACHINE, seed))

    assert keys.check(key[:-24], public_key, MACHINE).state is LicenseState.INVALID


@pytest.mark.parametrize(
    "text", ["", "   ", "hello there", "not-a-key-at-all", "1234567890", "=" * 40]
)
def test_nonsense_is_refused_without_raising(text, public_key):
    assert keys.check(text, public_key, MACHINE).state is LicenseState.INVALID


def test_expiry_is_honoured(seed, public_key):
    yesterday = date.today() - timedelta(days=1)
    key = keys.issue(MACHINE, seed, expires=yesterday)

    outcome = keys.check(key, public_key, MACHINE)

    assert outcome.state is LicenseState.EXPIRED
    assert f"{yesterday:%Y}" in outcome.message


def test_a_key_works_on_its_final_day(seed, public_key):
    """An off-by-one here cuts a customer's last day short."""

    today = date.today()
    key = keys.issue(MACHINE, seed, expires=today)

    assert keys.check(key, public_key, MACHINE, today=today).ok
    assert not keys.check(key, public_key, MACHINE, today=today + timedelta(days=1)).ok


def test_a_key_survives_an_email_client(seed, public_key):
    """
    Keys arrive wrapped, indented and with the odd stray character. Refusing
    one because a mail client reflowed it would be its own support problem.
    """

    key = keys.issue(MACHINE, seed, label="Acme Corp")

    mangled = "  \n".join(key[at : at + 30] for at in range(0, len(key), 30))
    mangled = f'"{mangled.lower()}"\r\n\t'

    assert keys.check(mangled, public_key, MACHINE).ok


def test_a_long_label_is_truncated_not_rejected(seed, public_key):
    outcome = keys.check(keys.issue(MACHINE, seed, label="Q" * 200), public_key, MACHINE)

    assert outcome.ok
    assert outcome.key is not None
    assert len(outcome.key.label) <= keys.MAX_LABEL


def test_an_empty_public_key_accepts_nothing(seed):
    """Belt and braces: an unconfigured build must not fall open here."""

    key = keys.issue(MACHINE, seed)

    assert keys.check(key, "", MACHINE).state is LicenseState.INVALID
    assert keys.check(key, "not hex at all", MACHINE).state is LicenseState.INVALID


def test_days_remaining_counts_down(seed, public_key):
    key = keys.issue(MACHINE, seed, expires=date.today() + timedelta(days=30))
    parsed = keys.decode(key)

    assert parsed is not None
    assert parsed.days_remaining() == 30


def test_unlicensed_by_default(gate):
    status = gate.status()

    assert status.state is LicenseState.UNLICENSED
    assert not status.allows_use


def test_activation_persists(gate, seed):
    key = keys.issue(MACHINE, seed, label="Acme Corp")

    assert gate.activate(key).ok

    status = gate.status()
    assert status.allows_use
    assert status.label == "Acme Corp"
    assert status.activated_at is not None


def test_a_blank_key_is_refused(gate):
    assert not gate.activate("   ").ok


def test_a_rejected_key_does_not_displace_a_working_one(gate, seed):
    """
    A bad paste must not be able to lock someone out of software they own.
    """

    gate.activate(keys.issue(MACHINE, seed, label="Acme Corp"))

    for bad in ("rubbish", keys.issue(OTHER_MACHINE, seed), "?" * 200):
        assert not gate.activate(bad).ok

    assert gate.status().allows_use
    assert gate.status().label == "Acme Corp"


def test_expiry_ends_access_at_the_gate(gate, seed):
    key = keys.issue(MACHINE, seed, expires=date.today() + timedelta(days=5))
    gate.activate(key)

    assert gate.status().allows_use
    assert gate.status(today=date.today() + timedelta(days=10)).state is LicenseState.EXPIRED


def test_deactivation_removes_the_key(gate, seed):
    gate.activate(keys.issue(MACHINE, seed))
    assert gate.status().allows_use

    assert gate.deactivate().ok
    assert not gate.status().allows_use


def test_deactivating_nothing_is_not_an_error(gate):
    assert gate.deactivate().ok


def test_a_copied_licence_file_does_not_work(gate, seed, monkeypatch):
    """Copying license.json is the obvious way to try to share a purchase."""

    gate.activate(keys.issue(MACHINE, seed, label="Acme Corp"))
    assert gate.status().allows_use

    monkeypatch.setattr("app.licensing.gate.machine_fingerprint", lambda: OTHER_MACHINE)

    status = gate.status()
    assert status.state is LicenseState.WRONG_MACHINE
    assert not status.allows_use


def test_an_unreadable_licence_file_asks_for_the_key_again(gate):
    storage.license_path().write_text("not json at all", encoding="utf-8")

    assert gate.status().state is LicenseState.UNLICENSED


def test_an_unconfigured_build_never_gates():
    """Development and self-hosted builds must not require a key."""

    gate = LicenseGate(LicenseConfig(public_key=""))

    assert gate.status().allows_use
    assert gate.activate("anything").ok


def test_config_reports_whether_it_is_enforced():
    assert not LicenseConfig(public_key="").enforced
    assert not LicenseConfig(public_key="   ").enforced
    assert LicenseConfig(public_key="ab" * 32).enforced


def test_the_support_address_is_the_one_customers_are_given():
    """
    The address appears in the activation window, the CLI and the docs. It is
    pinned here because a typo in it is a customer who cannot buy anything and
    has no way to tell anyone.
    """

    from app.licensing.config import SUPPORT_EMAIL
    from app.licensing.config import LicenseConfig as Config

    assert SUPPORT_EMAIL == "aliennyx@aol.com"
    assert Config().support_email == SUPPORT_EMAIL


def test_fingerprint_is_stable_and_opaque():
    from app.licensing.fingerprint import machine_fingerprint

    first = machine_fingerprint()

    assert first == machine_fingerprint()
    assert len(first) == 32
    assert all(character in "0123456789abcdef" for character in first)


def test_no_payment_provider_remains_in_the_source():
    """
    The store integrations were removed outright. A stray import or a leftover URL would
    be a live code path nobody is testing.
    """

    import re
    from pathlib import Path

    import app

    banned = re.compile(
        r"lemon\s?squeezy|lemonsqueezy|gumroad|fastspring"
        r"|stripe\.com|api\.stripe|paddle\.com|checkout\.",
        re.IGNORECASE,
    )

    for source in Path(app.__file__).parent.rglob("*.py"):
        found = banned.search(source.read_text(encoding="utf-8"))
        assert found is None, f"{source.name} still references {found.group(0)!r}"


def test_the_provider_module_is_gone():
    """It held the HTTP adapters. Importing it must fail, not half-work."""

    from pathlib import Path

    import app

    assert not (Path(app.__file__).parent / "licensing" / "providers.py").exists()

    with pytest.raises(ImportError):
        __import__("app.licensing.providers")


def test_licensing_makes_no_network_calls():
    """
    A key is checked against a public key compiled into the build. If an HTTP
    client ever appears in this package again, something is phoning home.
    """

    from pathlib import Path

    import app.licensing

    for source in Path(app.licensing.__file__).parent.rglob("*.py"):
        text = source.read_text(encoding="utf-8")
        for module in ("httpx", "requests", "urllib.request", "http.client", "socket"):
            assert f"import {module}" not in text, f"{source.name} imports {module}"
