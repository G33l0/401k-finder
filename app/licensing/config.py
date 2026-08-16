"""
Whether this build requires a licence, and who to contact for one.

**Set these before building a release.** Until a public key is configured the
application runs unlicensed, which is what you want while developing and never
what you want in a build you sell — ``enforced`` exists so the build script can
refuse to ship a release that would give itself away.

There is no licence server and no payment provider. Keys are issued by the
owner, by hand, in reply to an email; see ``docs/SELLING.md``. The values are
compiled into the executable rather than read from a settings file, because a
settings file is one a customer could edit.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

#: Where customers write to buy a licence or get help. One address: the whole
#: purchase flow is a conversation, so splitting sales from support would only
#: create a wrong door to knock on.
SUPPORT_EMAIL = "aliennyx@aol.com"


@dataclass(frozen=True, slots=True)
class LicenseConfig:
    #: The Ed25519 public key, hex-encoded, whose private half signs keys.
    #: Empty means licensing is off.
    public_key: str = ""

    #: Shown wherever a customer needs to get in touch.
    support_email: str = SUPPORT_EMAIL

    #: Named in the activation dialog and the email it drafts.
    product_name: str = "401K Finder Pro"

    @property
    def enforced(self) -> bool:
        """Whether the application should require a licence at all."""

        return bool(self.public_key.strip())


#: ---------------------------------------------------------------------------
#: Edit this before a release build.
#:
#: Generate the pair with:
#:
#:     python -m scripts.issue_license --new-keypair
#:
#: Paste the *public* key here. Keep the private key off this machine and out
#: of this repository — anyone holding it can issue licences for your product.
#: ---------------------------------------------------------------------------
LICENSE_CONFIG = LicenseConfig(
    public_key="",
    support_email=SUPPORT_EMAIL,
)


#: Environment override, for exercising the activation flow without rebuilding.
#: Read only when the compiled configuration leaves licensing off, so a
#: released build cannot have its licensing switched off by setting a variable.
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
