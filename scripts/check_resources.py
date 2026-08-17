#!/usr/bin/env python3
"""
Check that the registry links still work. **Run before every release.**

    python -m scripts.check_resources

``app/trace/resources.py`` points people at government and third-party sites to
search for a lost account by Social Security number. Those addresses drift, and
a dead link in a paid product is worse than no link — someone chasing money they
are owed hits a 404 and concludes the tool is abandoned.

This makes one request per resource and reports what came back. It is not part
of the test suite: the tests must pass offline, and a government site being slow
is not a reason to fail a build.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.constants import USER_AGENT  # noqa: E402
from app.trace.resources import RESOURCES  # noqa: E402

TIMEOUT = 20.0


def main() -> int:
    try:
        import httpx
    except ImportError:
        raise SystemExit("httpx is required: pip install -r requirements.txt") from None

    failures = 0

    print(f"Checking {len(RESOURCES)} links.\n")

    with httpx.Client(
        timeout=TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for resource in RESOURCES:
            try:
                # HEAD first: several of these serve large pages, and some
                # government hosts reject it, so fall back to GET.
                response = client.head(resource.url)
                if response.status_code >= 400:
                    response = client.get(resource.url)
            except httpx.HTTPError as exc:
                print(f"  FAIL  {resource.url}\n        {type(exc).__name__}: {exc}")
                failures += 1
                continue

            landed = str(response.url)
            moved = "" if landed.rstrip("/") == resource.url.rstrip("/") else f" -> {landed}"

            # 401/403 from a government site almost always means "no scripts",
            # not "no page". Reporting those as failures would train the reader
            # to ignore the whole report, so they are called out separately and
            # do not fail the run.
            if response.status_code in {401, 403, 405, 429}:
                print(
                    f"  ?     {resource.url}  HTTP {response.status_code}{moved}"
                    f"\n        blocks automated requests -- open it in a browser to confirm"
                )
            elif response.status_code >= 400:
                print(f"  FAIL  {resource.url}  HTTP {response.status_code}{moved}")
                failures += 1
            else:
                print(f"  ok    {resource.url}  HTTP {response.status_code}{moved}")

    print()

    if failures:
        print(
            f"{failures} link(s) are broken. Fix them in app/trace/resources.py before\n"
            f"releasing — these are what someone follows to find their money."
        )
        return 1

    print(
        "No broken links. Open any marked '?' in a browser, and check any '->'\n"
        "redirect — a redirect today is a dead link in a year."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
