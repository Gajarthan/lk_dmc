import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from dmc.client import Client


@pytest.fixture
def server():
    class Handler(BaseHTTPRequestHandler):
        attempts = 0

        def do_GET(self):
            if self.path == "/retry" and Handler.attempts == 0:
                Handler.attempts += 1
                self.send_response(503)
                self.send_header("Retry-After", "86400")
                self.end_headers()
                return
            self.send_response(200)
            self.end_headers()
            if self.path == "/slow":
                try:
                    for _ in range(20):
                        self.wfile.write(b"x")
                        self.wfile.flush()
                        time.sleep(0.02)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return
            self.wfile.write(b"%PDF-1.4\nhello" if self.path == "/pdf" else b"hello")

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    httpd.server_close()
    thread.join()


def test_transient_http_failure_is_retried(server):
    with Client(delay=0) as client:
        assert client.get_text(server + "/retry") == "hello"


def test_server_retry_after_cannot_force_hours_of_waiting(server, monkeypatch):
    pauses = []
    monkeypatch.setattr("dmc.client.time.sleep", pauses.append)
    with Client(delay=0) as client:
        assert client.get_text(server + "/retry") == "hello"
    assert max(pauses) <= 4


def test_slow_stream_obeys_deadline(server):
    with Client(delay=0) as client:
        client.deadline = time.monotonic() + 0.06
        with pytest.raises(TimeoutError):
            client.get_text(server + "/slow")


def test_pdf_download_is_validated(server, tmp_path):
    destination = tmp_path / "doc.pdf"
    with Client(delay=0) as client:
        client.download_pdf(server + "/pdf", destination)
        assert destination.read_bytes().startswith(b"%PDF-")
        with pytest.raises(ValueError, match="PDF"):
            client.download_pdf(server + "/html", destination)
    assert destination.read_bytes().startswith(b"%PDF-")
    assert not list(tmp_path.glob("*.tmp"))


def test_download_limit_keeps_existing_file(server, tmp_path):
    destination = tmp_path / "doc.pdf"
    destination.write_bytes(b"existing")
    with Client(delay=0, max_bytes=4) as client:
        with pytest.raises(ValueError, match="limit"):
            client.download_pdf(server + "/pdf", destination)
    assert destination.read_bytes() == b"existing"
