"""Bounded HTTP access shared by collection and downloads."""

import json
import os
import tempfile
import time
from pathlib import Path

import requests


class DeadlineExceeded(TimeoutError):
    """A configured stage budget was reached, rather than an upstream failure."""


class Client:
    def __init__(self, timeout: float = 30, delay: float = 0.25, max_bytes: int = 50 * 1024 * 1024):
        if timeout <= 0 or delay < 0 or max_bytes <= 0:
            raise ValueError("Invalid HTTP limits")
        self.timeout, self.delay, self.max_bytes = timeout, delay, max_bytes
        self.deadline: float | None = None
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "DMC-Report-Collector/2.0"
        self.session.max_redirects = 5

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.session.close()

    def _remaining(self):
        remaining = self.timeout if self.deadline is None else self.deadline - time.monotonic()
        if remaining <= 0:
            raise DeadlineExceeded("HTTP stage deadline reached")
        return min(self.timeout, remaining)

    def _pause(self, seconds):
        time.sleep(min(seconds, self._remaining()))
        self._remaining()

    def _get(self, url):
        self._pause(self.delay)
        for attempt in range(4):
            try:
                response = self.session.get(url, timeout=self._remaining(), stream=True)
            except (requests.ConnectionError, requests.Timeout):
                self._remaining()
                if attempt == 3:
                    raise
            else:
                if response.status_code not in {429, 500, 502, 503, 504} or attempt == 3:
                    try:
                        response.raise_for_status()
                        self._remaining()
                        return response
                    except Exception:
                        response.close()
                        raise
                response.close()
            # Keep retries bounded independently of untrusted Retry-After values.
            self._pause(0.5 * 2**attempt)
        raise RuntimeError("HTTP retry loop exhausted")

    def _chunks(self, response):
        while True:
            self._remaining()
            # read1 returns available bytes, allowing deadline checks on slow streams.
            try:
                chunk = response.raw.read1(65536, decode_content=True)
            except Exception:
                self._remaining()
                raise
            self._remaining()
            if not chunk:
                break
            yield chunk

    def get_text(self, url: str) -> str:
        with self._get(url) as response:
            content = bytearray()
            for chunk in self._chunks(response):
                content.extend(chunk)
                if len(content) > self.max_bytes:
                    raise ValueError("Response exceeds byte limit")
            encoding = response.encoding
            if not encoding or encoding.lower() == "iso-8859-1":
                encoding = "utf-8"
            return content.decode(encoding, errors="replace")

    def get_json(self, url: str):
        return json.loads(self.get_text(url))

    def download_pdf(self, url: str, destination: Path) -> None:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(suffix=".tmp", dir=destination.parent)
        try:
            with os.fdopen(fd, "wb") as stream, self._get(url) as response:
                size = 0
                for chunk in self._chunks(response):
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise ValueError("PDF exceeds download byte limit")
                    stream.write(chunk)
            with open(temporary, "rb") as stream:
                if b"%PDF-" not in stream.read(1024):
                    raise ValueError(f"Response is not a PDF: {url}")
            os.replace(temporary, destination)
        finally:
            Path(temporary).unlink(missing_ok=True)
