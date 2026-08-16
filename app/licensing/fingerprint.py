"""
A stable identifier for the machine an installation is running on.

Two properties matter, and they pull against each other:

* **Stable** across reboots, updates and ordinary hardware changes. A customer
  who adds RAM and is locked out will ask for a refund, and be right to.
* **Distinct** between machines, so one licence key cannot be used everywhere.

The identifiers are hashed before they ever leave the machine. The activation
server sees an opaque digest, never a hardware serial — that keeps a licence
check from turning into hardware inventory collection, which matters both for
privacy law and for what the privacy policy has to promise.
"""

from __future__ import annotations

import hashlib
import platform
import subprocess
import uuid
from functools import lru_cache
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

#: Mixed into the digest so the same machine yields a different value for a
#: different application. Not a secret.
_NAMESPACE = "401k-finder-pro/machine/v1"

#: Length of the printed fingerprint. 32 hex characters is far beyond what is
#: needed to avoid collisions and stays readable in a support email.
_LENGTH = 32


def _windows_machine_guid() -> str | None:
    """
    Read the installation GUID Windows generates when it is installed.

    This is the single most stable identifier available: it survives hardware
    changes and only differs after a reinstall of Windows itself.
    """

    try:
        import winreg
    except ImportError:
        return None

    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        ) as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return str(value) or None
    except OSError:
        return None


def _windows_volume_serial() -> str | None:
    """Return the serial of the system volume."""

    try:
        import ctypes

        serial = ctypes.c_ulong(0)
        ok = ctypes.windll.kernel32.GetVolumeInformationW(  # type: ignore[attr-defined]
            ctypes.c_wchar_p("C:\\"),
            None,
            0,
            ctypes.byref(serial),
            None,
            None,
            None,
            0,
        )
        return f"{serial.value:08X}" if ok else None
    except Exception:  # noqa: BLE001 - any failure just drops this component
        return None


def _linux_machine_id() -> str | None:
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            value = Path(path).read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if value:
            return value
    return None


def _macos_platform_uuid() -> str | None:
    try:
        output = subprocess.run(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None

    for line in output.splitlines():
        if "IOPlatformUUID" in line:
            _, _, value = line.partition("=")
            return value.strip().strip('"') or None

    return None


def _components() -> list[str]:
    """
    Collect the identifiers available on this platform.

    Every source is optional. A machine that yields only one is still
    identified; the digest simply rests on fewer inputs.
    """

    system = platform.system()
    found: list[str] = []

    sources = {
        "Windows": (_windows_machine_guid, _windows_volume_serial),
        "Linux": (_linux_machine_id,),
        "Darwin": (_macos_platform_uuid,),
    }.get(system, ())

    for source in sources:
        if value := source():
            found.append(value)

    if not found:
        # A MAC address is a poor identifier — virtual adapters and VPNs change
        # it — but an unstable fingerprint beats no fingerprint at all, and this
        # only applies to platforms none of the above matched.
        logger.warning(
            "No stable machine identifier was available; falling back to the "
            "network address, which may change."
        )
        found.append(f"{uuid.getnode():012x}")

    return found


@lru_cache(maxsize=1)
def machine_fingerprint() -> str:
    """Return this machine's opaque fingerprint."""

    payload = "|".join([_NAMESPACE, *_components()])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:_LENGTH]


def machine_label() -> str:
    """
    A human-readable name for the activation, shown in the customer's account.

    The hostname makes an activation list meaningful — "which of my machines is
    this?" — without revealing anything the customer does not already know.
    """

    try:
        host = platform.node() or "Unknown"
    except Exception:  # noqa: BLE001
        host = "Unknown"

    return f"{host} ({platform.system() or 'Unknown'})"


def describe() -> dict[str, str]:
    """Report the fingerprint and its inputs, for support diagnostics."""

    return {
        "fingerprint": machine_fingerprint(),
        "label": machine_label(),
        "platform": platform.platform(),
        "component_count": str(len(_components())),
    }
