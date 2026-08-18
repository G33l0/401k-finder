from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

import httpx

from app.core.config import get_download_dir
from app.core.constants import USER_AGENT
from app.core.exceptions import DownloadError, ImportCancelled
from app.core.logging import get_logger

logger = get_logger(__name__)

ProgressCallback = Callable[[int, int], None]
CancelCallback = Callable[[], bool]

CHUNK_SIZE = 1 << 20


class DOLDownloader:
    """Streams DOL dataset archives to disk."""

    def __init__(self, timeout: float = 120.0, max_retries: int = 3) -> None:
        self.timeout = timeout
        self.max_retries = max(max_retries, 1)

    @staticmethod
    def _filename_from_url(url: str) -> str:
        filename = url.rstrip("/").split("/")[-1]

        if not filename:
            raise DownloadError(f"Unable to determine a filename from URL: {url}")

        return filename

    @staticmethod
    def sha256(path: Path) -> str:
        digest = hashlib.sha256()

        with path.open("rb") as handle:
            while chunk := handle.read(CHUNK_SIZE):
                digest.update(chunk)

        return digest.hexdigest()

    def head(self, url: str) -> tuple[int, bool]:
        """Return ``(content_length, supports_range)`` for a dataset URL."""

        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.head(url, headers={"User-Agent": USER_AGENT})
                response.raise_for_status()
                length = int(response.headers.get("Content-Length", "0"))
                accepts = response.headers.get("Accept-Ranges", "").lower() == "bytes"
                return length, accepts
        except (httpx.HTTPError, ValueError):
            return 0, False

    def download(
        self,
        url: str,
        destination: Path | None = None,
        expected_sha256: str | None = None,
        progress: ProgressCallback | None = None,
        should_cancel: CancelCallback | None = None,
        resume: bool = True,
    ) -> Path:
        """Download a dataset, returning the path it was written to."""

        if not url.startswith(("http://", "https://")):
            raise DownloadError("Dataset URL must use HTTP or HTTPS.")

        if destination is None:
            destination = get_download_dir() / self._filename_from_url(url)

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".part")

        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                self._stream(
                    url=url,
                    temporary=temporary,
                    progress=progress,
                    should_cancel=should_cancel,
                    resume=resume,
                )
                break
            except ImportCancelled:
                raise
            except (httpx.HTTPError, OSError) as exc:
                last_error = exc
                logger.warning(
                    "Download attempt %s of %s failed for %s: %s",
                    attempt,
                    self.max_retries,
                    url,
                    exc,
                )
                if attempt == self.max_retries:
                    temporary.unlink(missing_ok=True)
                    raise DownloadError(f"Unable to download {url}: {exc}") from exc

        if last_error is not None and not temporary.exists():
            raise DownloadError(f"Unable to download {url}: {last_error}")

        if expected_sha256:
            actual = self.sha256(temporary)
            if actual.lower() != expected_sha256.lower():
                temporary.unlink(missing_ok=True)
                raise DownloadError(
                    f"Checksum mismatch for {destination.name}: "
                    f"expected {expected_sha256}, got {actual}"
                )

        temporary.replace(destination)
        logger.info("Downloaded %s (%s bytes)", destination.name, destination.stat().st_size)

        return destination

    def _stream(
        self,
        url: str,
        temporary: Path,
        progress: ProgressCallback | None,
        should_cancel: CancelCallback | None,
        resume: bool,
    ) -> None:
        headers = {"User-Agent": USER_AGENT}
        already = 0

        if resume and temporary.exists():
            already = temporary.stat().st_size
            if already > 0:
                headers["Range"] = f"bytes={already}-"

        with httpx.stream(
            "GET",
            url,
            timeout=self.timeout,
            follow_redirects=True,
            headers=headers,
        ) as response:
            if already and response.status_code == 200:
                already = 0

            response.raise_for_status()

            total = int(response.headers.get("Content-Length", "0")) + already
            downloaded = already
            mode = "ab" if already else "wb"

            with temporary.open(mode) as handle:
                for chunk in response.iter_bytes(chunk_size=CHUNK_SIZE):
                    if should_cancel and should_cancel():
                        raise ImportCancelled("Download cancelled.")

                    if not chunk:
                        continue

                    handle.write(chunk)
                    downloaded += len(chunk)

                    if progress:
                        progress(downloaded, total)

    def download_layout(self, url: str, destination: Path | None = None) -> Path:
        """Fetch a dataset's published layout file."""

        return self.download(url, destination=destination, resume=False)

    def fetch_text(self, url: str) -> str:
        """Fetch a small text resource, such as a layout file, into memory."""

        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(url, headers={"User-Agent": USER_AGENT})
                response.raise_for_status()
                return response.text
        except httpx.HTTPError as exc:
            raise DownloadError(f"Unable to fetch {url}: {exc}") from exc
