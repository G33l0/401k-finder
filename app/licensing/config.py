"""Whether this build requires a licence, and who to contact for one."""

from __future__ import annotations

import os
from dataclasses import dataclass

SUPPORT_EMAIL = "aliennyx@aol.com"


@dataclass(frozen=True, slots=True)
class LicenseConfig:
    public_key: str = ""

    support_email: str = SUPPORT_EMAIL

    product_name: str = "401K Finder Pro"

    @property
    def enforced(self) -> bool:
        """Whether the application should require a licence at all."""

        return bool(self.public_key.strip())


LICENSE_CONFIG = LicenseConfig(
    public_key="",
    support_email=SUPPORT_EMAIL,
)


_ENV_PUBLIC_KEY = "FINDER_401K_LICENSE_PUBKEY"


def get_config() -> LicenseConfig:
    """Return the active licence configuration."""

    if LICENSE_CONFIG.enforced:
        return LICENSE_CONFIG

    override = os.environ.get(_ENV_PUBLIC_KEY, "").strip()

    if not override:
        return LICENSE_CONFIG

    return LicenseConfig(
        public_key=override,
        support_email=LICENSE_CONFIG.support_email,
        product_name=LICENSE_CONFIG.product_name,
    )
