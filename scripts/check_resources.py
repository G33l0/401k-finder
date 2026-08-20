#!/usr/bin/env python3
"""Check that every link the application shows still works. Run before every release."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.constants import USER_AGENT  # noqa: E402
from app.providers.directory import CONTACTS  # noqa: E402
from app.trace.resources import RESOURCES  # noqa: E402

TIMEOUT = 20.0


def main() -> int:
    try:
        import httpx
    except ImportError:
        raise SystemExit("httpx is required: pip install -r requirements.txt") from None

    targets = [(resource.name, resource.url, "app/trace/resources.py") for resource in RESOURCES]
    targets += [
        (contact.canonical_name, contact.website, "app/providers/directory.py")
        for contact in CONTACTS
        if contact.website
    ]

    failures: list[str] = []

    print(f"Checking {len(targets)} links.\n")

    with httpx.Client(
        timeout=TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for name, url, origin in targets:
            try:
                response = client.head(url)
                if response.status_code >= 400:
                    response = client.get(url)
            except httpx.HTTPError as exc:
                print(f"  FAIL  {url}\n        {type(exc).__name__}: {exc}")
                failures.append(f"{name} ({origin})")
                continue

            landed = str(response.url)
            moved = "" if landed.rstrip("/") == url.rstrip("/") else f" -> {landed}"

            if response.status_code in {401, 403, 405, 429}:
                print(
                    f"  ?     {url}  HTTP {response.status_code}{moved}"
                    f"\n        blocks automated requests -- open it in a browser to confirm"
                )
            elif response.status_code >= 400:
                print(f"  FAIL  {url}  HTTP {response.status_code}{moved}")
                failures.append(f"{name} ({origin})")
            else:
                print(f"  ok    {url}  HTTP {response.status_code}{moved}")

    print()

    if failures:
        print(f"{len(failures)} link(s) are broken:")
        for item in failures:
            print(f"  {item}")
        print(
            "\nFix them before releasing. These are what someone follows to find\n"
            "their money, and a wrong number is worse than none."
        )
        return 1

    print(
        "No broken links. Open any marked '?' in a browser, and check any '->'\n"
        "redirect. A redirect today is a dead link in a year."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
