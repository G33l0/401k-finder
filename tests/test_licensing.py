"""
Licensing behaviour, tested against a fake store rather than a live API.

The cases that matter most are the ones that decide whether a paying customer
gets locked out, so they are covered explicitly: an unreachable server, a
revoked key, a full seat allocation, and a licence file copied between machines.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.licensing import storage
from app.licensing.config import LicenseConfig, Provider
from app.licensing.gate import LicenseGate
from app.licensing.models import (
    ActivationResult,
    LicenseNetworkError,
    LicenseState,
    utcnow,
)


class FakeStore:
    """A store that hands out one key with a fixed number of machine slots."""

    def __init__(self, limit: int = 2) -> None:
        self.valid_key = "GOOD-KEY-0001-0002"
        self.limit = limit
        self.instances: dict[str, str] = {}
        self.revoked = False
        self.offline = False
        self.validate_calls = 0

    def _check(self) -> None:
        if self.offline:
            raise LicenseNetworkError("Simulated outage.")

    def activate(self, key: str, fingerprint: str, label: str) -> ActivationResult:
        self._check()

        if key != self.valid_key:
            return ActivationResult(False, LicenseState.UNLICENSED, "Unknown licence key.")

        if self.revoked:
            return ActivationResult(False, LicenseState.REVOKED, "This key was refunded.")

        if fingerprint not in self.instances and len(self.instances) >= self.limit:
            return ActivationResult(
                False, LicenseState.SEAT_LIMIT, "Activation limit reached for this key."
            )

        self.instances[fingerprint] = f"instance-{fingerprint[:8]}"

        return ActivationResult(
            True,
            LicenseState.ACTIVE,
            "Licence activated.",
            instance_id=self.instances[fingerprint],
            customer_email="buyer@example.com",
            activation_limit=self.limit,
            activation_count=len(self.instances),
        )

    def validate(self, key: str, instance_id: str | None) -> ActivationResult:
        self._check()
        self.validate_calls += 1

        if self.revoked:
            return ActivationResult(False, LicenseState.REVOKED, "This key was refunded.")

        if key != self.valid_key:
            return ActivationResult(False, LicenseState.UNLICENSED, "Unknown licence key.")

        return ActivationResult(
            True,
            LicenseState.ACTIVE,
            "Licence confirmed.",
            instance_id=instance_id,
            customer_email="buyer@example.com",
            activation_limit=self.limit,
            activation_count=len(self.instances),
        )

    def deactivate(self, key: str, instance_id: str) -> ActivationResult:
        self._check()
        for fingerprint, existing in list(self.instances.items()):
            if existing == instance_id:
                del self.instances[fingerprint]
        return ActivationResult(True, LicenseState.UNLICENSED, "Released.")


@pytest.fixture()
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture()
def gate(store, monkeypatch, tmp_path, isolated_data_dir) -> LicenseGate:
    """A gate wired to the fake store, with its own licence file."""

    monkeypatch.setattr(storage, "license_path", lambda: tmp_path / "license.json")

    config = LicenseConfig(
        provider=Provider.LEMON_SQUEEZY,
        product_id="test-product",
        grace_days=30,
        revalidate_days=7,
    )

    built = LicenseGate(config)
    built.provider = store
    return built


# ----------------------------------------------------------------------


def test_unlicensed_by_default(gate):
    status = gate.status()
    assert status.state is LicenseState.UNLICENSED
    assert not status.allows_use


def test_activation_succeeds_and_persists(gate, store):
    result = gate.activate(store.valid_key)

    assert result.ok
    assert gate.status().allows_use
    assert gate.status().customer_email == "buyer@example.com"


def test_unknown_key_is_rejected(gate):
    result = gate.activate("WRONG-KEY-0000-0000")

    assert not result.ok
    assert not gate.status().allows_use


def test_blank_key_is_rejected_without_calling_the_store(gate, store):
    result = gate.activate("   ")

    assert not result.ok
    assert store.validate_calls == 0


def test_seat_limit_blocks_a_third_machine(store, monkeypatch, tmp_path, isolated_data_dir):
    """The point of the whole exercise: one key cannot be used everywhere."""

    config = LicenseConfig(provider=Provider.LEMON_SQUEEZY, product_id="test-product")

    for index in range(3):
        monkeypatch.setattr(storage, "license_path", lambda i=index: tmp_path / f"m{i}.json")
        monkeypatch.setattr(
            "app.licensing.gate.machine_fingerprint", lambda i=index: f"machine{i}" * 4
        )

        gate = LicenseGate(config)
        gate.provider = store
        result = gate.activate(store.valid_key)

        if index < 2:
            assert result.ok, f"machine {index} should have activated"
        else:
            assert not result.ok
            assert result.state is LicenseState.SEAT_LIMIT


def test_deactivation_frees_a_seat(gate, store):
    gate.activate(store.valid_key)
    assert len(store.instances) == 1

    result = gate.deactivate()

    assert result.ok
    assert store.instances == {}
    assert not gate.status().allows_use


# ----------------------------------------------------------------------
# The paths that decide whether a paying customer is locked out
# ----------------------------------------------------------------------


def test_offline_keeps_working_on_the_grace_period(gate, store):
    """An outage on the seller's side must never stop someone who has paid."""

    gate.activate(store.valid_key)

    # Age the record past the revalidation window, then take the store away.
    record = storage.load()
    record.last_validated = (utcnow() - timedelta(days=10)).isoformat()
    storage.save(record)

    store.offline = True
    status = gate.status()

    assert status.state is LicenseState.GRACE
    assert status.allows_use
    assert status.grace_days_remaining is not None


def test_offline_beyond_the_grace_period_stops(gate, store):
    gate.activate(store.valid_key)

    record = storage.load()
    record.last_validated = (utcnow() - timedelta(days=45)).isoformat()
    storage.save(record)

    store.offline = True
    status = gate.status()

    assert status.state is LicenseState.EXPIRED_GRACE
    assert not status.allows_use


def test_recent_activation_does_not_call_the_store(gate, store):
    """Ordinary start-ups must be free and must work offline."""

    gate.activate(store.valid_key)
    store.validate_calls = 0

    gate.status()

    assert store.validate_calls == 0


def test_stale_activation_revalidates(gate, store):
    gate.activate(store.valid_key)

    record = storage.load()
    record.last_validated = (utcnow() - timedelta(days=10)).isoformat()
    storage.save(record)

    gate.status()

    assert store.validate_calls == 1


def test_revoked_key_stops_use(gate, store):
    """A refund or chargeback must actually end access."""

    gate.activate(store.valid_key)

    record = storage.load()
    record.last_validated = (utcnow() - timedelta(days=10)).isoformat()
    storage.save(record)

    store.revoked = True
    status = gate.status()

    assert status.state is LicenseState.REVOKED
    assert not status.allows_use


def test_activation_failure_while_offline_is_reported_as_a_network_problem(gate, store):
    """Blaming the key for the seller's outage would send users to support."""

    store.offline = True
    result = gate.activate(store.valid_key)

    assert not result.ok
    assert "reach the licence server" in result.message.lower()


# ----------------------------------------------------------------------
# The licence file itself
# ----------------------------------------------------------------------


def test_licence_file_does_not_work_on_another_machine(gate, store, monkeypatch):
    """Copying the file is the obvious way to share a purchase."""

    gate.activate(store.valid_key)
    assert storage.load() is not None

    monkeypatch.setattr(
        "app.licensing.storage.machine_fingerprint", lambda: "a-completely-different-machine"
    )

    assert storage.load() is None


def test_tampered_licence_file_is_rejected(gate, store, tmp_path):
    gate.activate(store.valid_key)

    path = storage.license_path()
    contents = path.read_text(encoding="utf-8")
    path.write_text(contents.replace("buyer@example.com", "someone@else.com"), encoding="utf-8")

    assert storage.load() is None


def test_unreadable_licence_file_is_treated_as_absent(gate, tmp_path):
    storage.license_path().write_text("not json at all", encoding="utf-8")

    assert storage.load() is None


def test_key_is_not_written_in_full_to_status(gate, store):
    gate.activate(store.valid_key)
    status = gate.status()

    assert status.key_suffix is not None
    assert status.key_suffix in store.valid_key
    assert len(status.key_suffix) <= 4


# ----------------------------------------------------------------------
# Builds with no store configured
# ----------------------------------------------------------------------


def test_unconfigured_build_never_gates():
    """Development and self-hosted builds must not require a key."""

    gate = LicenseGate(LicenseConfig(provider=Provider.NONE))

    assert gate.status().allows_use
    assert gate.activate("anything").ok


def test_config_reports_whether_it_is_enforced():
    assert not LicenseConfig(provider=Provider.NONE).enforced
    assert not LicenseConfig(provider=Provider.LEMON_SQUEEZY, product_id="").enforced
    assert LicenseConfig(provider=Provider.LEMON_SQUEEZY, product_id="123").enforced


def test_fingerprint_is_stable_and_opaque():
    from app.licensing.fingerprint import machine_fingerprint

    first = machine_fingerprint()
    assert first == machine_fingerprint()
    assert len(first) == 32
    assert all(character in "0123456789abcdef" for character in first)
