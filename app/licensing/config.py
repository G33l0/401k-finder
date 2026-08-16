"""
Which store issues licences, and how strictly they are enforced.

**Set these before building a release.** Until a provider is configured the
application runs unlicensed, which is what you want while developing and is
never what you want in a build you sell — ``is_configured`` exists so the build
can refuse to ship a release that would give itself away.

The values are compiled into the executable rather than read from a settings
file, because a settings file is one a customer could point at a server of
their own. That is deterrence, not security: see ``docs/SELLING.md`` for an
honest account of what this does and does not prevent.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum


class Provider(StrEnum):
    """The store whose licence API is in use."""

    #: No licensing. Every check passes. Development default.
    NONE = "none"
    LEMON_SQUEEZY = "lemonsqueezy"
    GUMROAD = "gumroad"


@dataclass(frozen=True, slots=True)
class LicenseConfig:
    provider: Provider = Provider.NONE

    #: Identifies the product within the store, so a key for a different
    #: product of yours cannot activate this one.
    #: Lemon Squeezy: the numeric store product id. Gumroad: the product's
    #: permalink.
    product_id: str = ""

    #: Where buyers go. Shown on the activation dialog.
    purchase_url: str = "https://example.com/buy"

    #: Where customers manage their activations, if the store offers it.
    account_url: str = ""

    #: Shown when someone needs help with a key.
    support_email: str = "support@example.com"

    #: Days the application keeps working when the licence server cannot be
    #: reached. Generous on purpose: an outage on your side, a flight, or a
    #: corporate proxy must not stop someone who has paid.
    grace_days: int = 30

    #: How often to re-confirm with the store while online.
    revalidate_days: int = 7

    #: Seconds before a licence request is abandoned. Short: this runs at
    #: start-up, and a hanging request would look like a frozen application.
    timeout: float = 10.0

    @property
    def is_configured(self) -> bool:
        return self.provider is not Provider.NONE and bool(self.product_id)

    @property
    def enforced(self) -> bool:
        """Whether the application should gate on a licence at all."""

        return self.is_configured


#: ---------------------------------------------------------------------------
#: Edit this before a release build.
#: ---------------------------------------------------------------------------
LICENSE_CONFIG = LicenseConfig(
    provider=Provider.NONE,
    product_id="",
    purchase_url="https://example.com/buy",
    account_url="",
    support_email="support@example.com",
)


#: Environment overrides, for testing an activation flow without rebuilding.
#: Deliberately read only when the compiled config leaves licensing off, so a
#: released build cannot have its licensing switched off by an environment
#: variable.
_ENV_PROVIDER = "FINDER_401K_LICENSE_PROVIDER"
_ENV_PRODUCT = "FINDER_401K_LICENSE_PRODUCT"


def get_config() -> LicenseConfig:
    """Return the active licence configuration."""

    if LICENSE_CONFIG.is_configured:
        return LICENSE_CONFIG

    raw_provider = os.environ.get(_ENV_PROVIDER, "").strip().lower()
    product = os.environ.get(_ENV_PRODUCT, "").strip()

    if not raw_provider or not product:
        return LICENSE_CONFIG

    try:
        provider = Provider(raw_provider)
    except ValueError:
        return LICENSE_CONFIG

    return LicenseConfig(
        provider=provider,
        product_id=product,
        purchase_url=LICENSE_CONFIG.purchase_url,
        account_url=LICENSE_CONFIG.account_url,
        support_email=LICENSE_CONFIG.support_email,
    )
