from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable

import httpx

from app.core.config import get_download_dir
from app.core.exceptions import DownloadError


ProgressCallback = Callable[[int, int], None]


class DOLDownloader:
    """
    Downloader for publicly available DOL datasets.

    The downloader itself does not assume a particular DOL filename.
    Dataset URLs are supplied explicitly by the dataset catalog.
    """

    def __init__(
        self,
        timeout: float = 60.0,
    ) -> None:
        self.timeout = timeout

    @staticmethod
    def _filename_from_url(url: str) -> str:
        filename = url.rstrip("/").split("/")[-1]

        if not filename:
            raise DownloadError(
                "Unable to determine a filename from URL."
            )

        return filename

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()

        with path.open("rb") as file:
            while chunk := file.read(1024 * 1024):
                digest.update(chunk)

        return digest.hexdigest()

    def download(
        self,
        url: str,
        destination: Path | None = None,
        expected_sha256: str | None = None,
        progress: ProgressCallback | None = None,
    ) -> Path:
        """
        Download a dataset using streaming I/O.

        Existing files are not silently overwritten.
        """

        if not url.startswith(("http://", "https://")):
            raise DownloadError(
                "Dataset URL must use HTTP or HTTPS."
            )

        if destination is None:
            destination = (
                get_download_dir()
                / self._filename_from_url(url)
            )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = destination.with_suffix(
            destination.suffix + ".part"
        )

        try:
            with httpx.stream(
                "GET",
                url,
                timeout=self.timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "401K-Finder-Pro/1.0 "
                        "(DOL public-data client)"
                    )
                },
            ) as response:

                response.raise_for_status()

                total = int(
                    response.headers.get(
                        "Content-Length",
                        "0",
                    )
                )

                downloaded = 0

                with temporary.open("wb") as file:
                    for chunk in response.iter_bytes(
                        chunk_size=1024 * 1024
                    ):
                        if not chunk:
                            continue

                        file.write(chunk)
                        downloaded += len(chunk)

                        if progress:
                            progress(
                                downloaded,
                                total,
                            )

            if expected_sha256:
                actual = self._sha256(temporary)

                if actual.lower() != expected_sha256.lower():
                    temporary.unlink(missing_ok=True)

                    raise DownloadError(
                        "SHA-256 checksum verification failed."
                    )

            temporary.replace(destination)

            return destination

        except httpx.HTTPError as exc:
            temporary.unlink(missing_ok=True)

            raise DownloadError(
                f"Unable to download dataset: {url}"
            ) from exc

        except OSError as exc:
            temporary.unlink(missing_ok=True)

            raise DownloadError(
                f"Unable to save downloaded dataset: "
                f"{destination}"
            ) from exc