"""
Adapters for the licence APIs that storefronts expose.

Every supported store offers the same three operations — activate a key against
a machine, re-check an existing activation, release it — so they sit behind one
protocol and the rest of the application never learns which store issued a key.
That also means switching stores later costs one adapter rather than a rewrite.

A note on failure handling that matters more than it looks: an unreachable
server raises :class:`LicenseNetworkError`, never "invalid". Conflating the two
would lock out paying customers whenever the store had an outage.
"""

from __future__ import annotations

from typing import Protocol

import httpx

from app.core.constants import USER_AGENT
from app.core.logging import get_logger
from app.licensing.config import LicenseConfig, Provider
from app.licensing.models import ActivationResult, LicenseNetworkError, LicenseState

logger = get_logger(__name__)


class LicenseProvider(Protocol):
    """The operations a storefront licence API must support."""

    def activate(self, key: str, fingerprint: str, label: str) -> ActivationResult: ...

    def validate(self, key: str, instance_id: str | None) -> ActivationResult: ...

    def deactivate(self, key: str, instance_id: str) -> ActivationResult: ...


def _post(url: str, payload: dict, timeout: float, headers: dict | None = None) -> dict:
    """POST form data and return the decoded JSON body."""

    try:
        response = httpx.post(
            url,
            data=payload,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})},
        )
    except httpx.HTTPError as exc:
        raise LicenseNetworkError(str(exc)) from exc

    # 4xx bodies carry the reason a key was rejected, so they are parsed rather
    # than raised on. Only a 5xx is treated as the server being unavailable.
    if response.status_code >= 500:
        raise LicenseNetworkError(f"Licence server returned {response.status_code}.")

    try:
        return response.json()
    except ValueError as exc:
        raise LicenseNetworkError("Licence server returned an unreadable response.") from exc


class LemonSqueezyProvider:
    """
    Lemon Squeezy licence keys.

    The API records one "instance" per activated machine and enforces the
    activation limit set on the product, which is exactly the seat counting a
    shareable key needs.
    """

    BASE = "https://api.lemonsqueezy.com/v1/licenses"

    def __init__(self, config: LicenseConfig) -> None:
        self.config = config

    def _result(self, body: dict, activated: bool) -> ActivationResult:
        licence = body.get("license_key") or {}
        meta = body.get("meta") or {}
        instance = body.get("instance") or {}

        status = str(licence.get("status", "")).lower()
        error = body.get("error")

        if activated and not error:
            state = LicenseState.ACTIVE
            message = "Licence activated."
        elif status in {"expired", "disabled"}:
            state = LicenseState.REVOKED
            message = f"This licence key is {status}."
        elif error and "activation limit" in str(error).lower():
            state = LicenseState.SEAT_LIMIT
            message = str(error)
        elif error:
            state = LicenseState.UNLICENSED
            message = str(error)
        else:
            state = LicenseState.UNLICENSED
            message = "The licence key was not accepted."

        # Reject a key that belongs to a different product of the same seller.
        expected = self.config.product_id
        actual = str(meta.get("product_id") or licence.get("product_id") or "")
        if state is LicenseState.ACTIVE and expected and actual and actual != expected:
            state = LicenseState.UNLICENSED
            message = "That key is for a different product."

        return ActivationResult(
            ok=state is LicenseState.ACTIVE,
            state=state,
            message=message,
            instance_id=str(instance.get("id")) if instance.get("id") else None,
            customer_email=meta.get("customer_email"),
            activation_limit=licence.get("activation_limit"),
            activation_count=licence.get("activation_usage"),
            raw=body,
        )

    def activate(self, key: str, fingerprint: str, label: str) -> ActivationResult:
        body = _post(
            f"{self.BASE}/activate",
            # The instance name is what the customer sees in their account, so
            # it carries the hostname; the fingerprint keeps it unique.
            {"license_key": key, "instance_name": f"{label} [{fingerprint[:8]}]"},
            self.config.timeout,
        )
        return self._result(body, activated=bool(body.get("activated")))

    def validate(self, key: str, instance_id: str | None) -> ActivationResult:
        payload = {"license_key": key}
        if instance_id:
            payload["instance_id"] = instance_id

        body = _post(f"{self.BASE}/validate", payload, self.config.timeout)
        return self._result(body, activated=bool(body.get("valid")))

    def deactivate(self, key: str, instance_id: str) -> ActivationResult:
        body = _post(
            f"{self.BASE}/deactivate",
            {"license_key": key, "instance_id": instance_id},
            self.config.timeout,
        )
        deactivated = bool(body.get("deactivated"))
        return ActivationResult(
            ok=deactivated,
            state=LicenseState.UNLICENSED,
            message="Licence released from this machine." if deactivated else "Could not release the licence.",
            raw=body,
        )


class GumroadProvider:
    """
    Gumroad licence keys.

    Gumroad counts uses rather than tracking named instances, so it cannot
    release a seat and it cannot tell two machines apart. The count is still
    enough to stop a key being handed round indefinitely, but a customer moving
    machines needs help from you. Prefer Lemon Squeezy where seat management
    matters.
    """

    BASE = "https://api.gumroad.com/v2/licenses"

    def __init__(self, config: LicenseConfig) -> None:
        self.config = config

    def _result(self, body: dict, *, increment: bool) -> ActivationResult:
        success = bool(body.get("success"))
        purchase = body.get("purchase") or {}
        uses = body.get("uses")

        if not success:
            return ActivationResult(
                ok=False,
                state=LicenseState.UNLICENSED,
                message=str(body.get("message") or "The licence key was not accepted."),
                raw=body,
            )

        if purchase.get("refunded") or purchase.get("chargebacked") or purchase.get("disputed"):
            return ActivationResult(
                ok=False,
                state=LicenseState.REVOKED,
                message="This purchase was refunded or disputed.",
                raw=body,
            )

        return ActivationResult(
            ok=True,
            state=LicenseState.ACTIVE,
            message="Licence activated." if increment else "Licence confirmed.",
            customer_email=purchase.get("email"),
            activation_count=uses,
            raw=body,
        )

    def activate(self, key: str, fingerprint: str, label: str) -> ActivationResult:
        body = _post(
            f"{self.BASE}/verify",
            {
                "product_permalink": self.config.product_id,
                "license_key": key,
                "increment_uses_count": "true",
            },
            self.config.timeout,
        )
        return self._result(body, increment=True)

    def validate(self, key: str, instance_id: str | None) -> ActivationResult:
        body = _post(
            f"{self.BASE}/verify",
            {
                "product_permalink": self.config.product_id,
                "license_key": key,
                # Re-checking must not consume another use, or a customer would
                # burn through their activations simply by opening the app.
                "increment_uses_count": "false",
            },
            self.config.timeout,
        )
        return self._result(body, increment=False)

    def deactivate(self, key: str, instance_id: str) -> ActivationResult:
        return ActivationResult(
            ok=True,
            state=LicenseState.UNLICENSED,
            message=(
                "Removed from this machine. Gumroad cannot release the seat "
                "automatically — contact support to reset the activation count."
            ),
        )


class NullProvider:
    """Used when no store is configured. Every check succeeds."""

    def __init__(self, config: LicenseConfig) -> None:
        self.config = config

    def activate(self, key: str, fingerprint: str, label: str) -> ActivationResult:
        return ActivationResult(True, LicenseState.ACTIVE, "Licensing is not enabled in this build.")

    def validate(self, key: str, instance_id: str | None) -> ActivationResult:
        return ActivationResult(True, LicenseState.ACTIVE, "Licensing is not enabled in this build.")

    def deactivate(self, key: str, instance_id: str) -> ActivationResult:
        return ActivationResult(True, LicenseState.UNLICENSED, "Licensing is not enabled in this build.")


_PROVIDERS: dict[Provider, type] = {
    Provider.LEMON_SQUEEZY: LemonSqueezyProvider,
    Provider.GUMROAD: GumroadProvider,
    Provider.NONE: NullProvider,
}


def build_provider(config: LicenseConfig) -> LicenseProvider:
    """Return the adapter for the configured store."""

    provider_class = _PROVIDERS.get(config.provider, NullProvider)
    return provider_class(config)
