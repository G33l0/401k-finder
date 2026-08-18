#!/usr/bin/env python3
"""Issue licence keys. Owner's tool: never ship this to a customer."""

from __future__ import annotations

import argparse
import contextlib
import os
import stat
import sys
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.licensing import ed25519, keys  # noqa: E402
from app.licensing.config import SUPPORT_EMAIL  # noqa: E402

DEFAULT_SEED_FILE = Path.home() / ".401k-finder" / "signing-key.hex"

SEED_ENV_VAR = "FINDER_401K_LICENSE_SEED"


def load_seed(path: Path) -> bytes:
    """Read the private seed, from the environment or a file."""

    from_env = os.environ.get(SEED_ENV_VAR, "").strip()
    source = f"${SEED_ENV_VAR}" if from_env else str(path)

    if not from_env:
        if not path.is_file():
            raise SystemExit(
                f"No signing key at {path}.\n"
                f"Create one with:  python -m scripts.issue_license --new-keypair"
            )
        from_env = path.read_text(encoding="utf-8").strip()

    try:
        seed = bytes.fromhex(from_env)
    except ValueError:
        raise SystemExit(f"The signing key in {source} is not valid hex.") from None

    if len(seed) != 32:
        raise SystemExit(f"The signing key in {source} must be 32 bytes (64 hex characters).")

    return seed


def create_keypair(path: Path) -> int:
    if path.exists():
        raise SystemExit(
            f"A signing key already exists at {path}.\n"
            f"Refusing to overwrite it. Every licence you have issued was signed with it.\n"
            f"To deliberately start over, move that file somewhere safe first."
        )

    seed = ed25519.generate_seed()
    public = ed25519.public_key(seed).hex()

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(seed.hex() + "\n", encoding="utf-8")

    with contextlib.suppress(OSError):
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600

    print(f"Private signing key written to {path}")
    print("  Back it up somewhere safe, and never commit it.\n")
    print("Paste this public key into app/licensing/config.py:\n")
    print(f'    public_key="{public}",\n')
    print("Then rebuild. Until you do, the build requires no licence.")

    return 0


def issue(args: argparse.Namespace) -> int:
    seed = load_seed(args.seed_file)

    machine = "".join(c for c in args.machine.strip().lower() if c in "0123456789abcdef")

    if len(machine) < 32:
        raise SystemExit(
            f"'{args.machine}' does not look like a Machine ID.\n"
            f"It is 32 hexadecimal characters, shown in the activation window and by\n"
            f"'401k-finder.exe license status'."
        )

    expires: date | None = None
    if args.days is not None:
        expires = date.today() + timedelta(days=args.days)
    elif args.expires:
        try:
            expires = date.fromisoformat(args.expires)
        except ValueError:
            raise SystemExit("--expires must be a date like 2027-03-31.") from None

    key = keys.issue(machine, seed, expires=expires, label=args.label)

    if not args.email:
        print(key)
        return 0

    term = "does not expire" if expires is None else f"is valid until {expires:%d %B %Y}"

    groups = key.split("-")
    wrapped = "\n".join(
        "-".join(groups[at : at + 5]) for at in range(0, len(groups), 5)
    )

    print(f"Subject: Your {args.product} licence key\n")
    print("Thank you for your purchase. Your licence key is below.\n")
    print(wrapped)
    print()
    print("To activate: open the application, paste the whole key into the box,")
    print("and click Activate.\n")
    print(f"This key is tied to the computer with Machine ID {machine},")
    print(f"and {term}. If you change computer, email us the new Machine ID and")
    print("we will issue a replacement.\n")
    print(f"-- {args.support}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Issue licence keys for 401K Finder Pro.",
        epilog="The private signing key is the business. Guard it.",
    )
    parser.add_argument(
        "--new-keypair",
        action="store_true",
        help="Create a signing keypair. Run this once, before your first release.",
    )
    parser.add_argument("--machine", help="The customer's Machine ID (32 hex characters).")
    parser.add_argument("--label", default="", help="Customer name, shown in their About box.")

    expiry = parser.add_mutually_exclusive_group()
    expiry.add_argument("--days", type=int, help="Expire this many days from today.")
    expiry.add_argument("--expires", help="Expire on a date, as 2027-03-31.")

    parser.add_argument(
        "--email",
        action="store_true",
        help="Print a ready-to-send reply rather than the bare key.",
    )
    parser.add_argument("--product", default="401K Finder Pro")
    parser.add_argument("--support", default=SUPPORT_EMAIL)
    parser.add_argument("--seed-file", type=Path, default=DEFAULT_SEED_FILE)

    args = parser.parse_args()

    if args.new_keypair:
        return create_keypair(args.seed_file)

    if not args.machine:
        parser.error("--machine is required (or use --new-keypair)")

    return issue(args)


if __name__ == "__main__":
    raise SystemExit(main())
