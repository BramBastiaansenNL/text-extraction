"""Dependency-free runtime smoke check for the offline guard."""

import os
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ocrpipe.offline import offline_guard


def blocked(call):
    try:
        call()
    except OSError as error:
        assert "Offline guard blocked" in str(error)
    else:
        raise AssertionError("External connection was permitted")


original = socket.socket.connect
with offline_guard():
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"
    assert os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] == "True"
    blocked(lambda: socket.create_connection(("8.8.8.8", 443)))
    blocked(lambda: socket.getaddrinfo("example.com", 443))
    with socket.socket() as sock:
        blocked(lambda: sock.connect(("8.8.8.8", 443)))
        blocked(lambda: sock.connect_ex(("8.8.8.8", 443)))
assert socket.socket.connect is original
print("Offline guard smoke check passed")
