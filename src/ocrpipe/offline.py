"""Runtime network restrictions. Activate before importing inference libraries."""

import os
import socket
from contextlib import contextmanager
from functools import wraps


def set_offline_environment() -> None:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
    os.environ["DO_NOT_TRACK"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"


def _local(address: object) -> bool:
    if isinstance(address, tuple) and address:
        return address[0] in ("127.0.0.1", "localhost", "::1")
    return False


@contextmanager
def offline_guard():
    """Deny outbound socket connections while allowing loopback services."""
    set_offline_environment()
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create_connection = socket.create_connection
    original_getaddrinfo = socket.getaddrinfo

    @wraps(original_connect)
    def connect(sock, address):
        if not _local(address):
            raise OSError("Offline guard blocked a non-local connection")
        return original_connect(sock, address)

    @wraps(original_connect_ex)
    def connect_ex(sock, address):
        if not _local(address):
            raise OSError("Offline guard blocked a non-local connection")
        return original_connect_ex(sock, address)

    @wraps(original_create_connection)
    def create_connection(address, *args, **kwargs):
        if not _local(address):
            raise OSError("Offline guard blocked a non-local connection")
        return original_create_connection(address, *args, **kwargs)

    @wraps(original_getaddrinfo)
    def getaddrinfo(host, *args, **kwargs):
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise OSError("Offline guard blocked a non-local DNS lookup")
        return original_getaddrinfo(host, *args, **kwargs)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.create_connection = create_connection
    socket.getaddrinfo = getaddrinfo
    try:
        yield
    finally:
        socket.socket.connect = original_connect
        socket.socket.connect_ex = original_connect_ex
        socket.create_connection = original_create_connection
        socket.getaddrinfo = original_getaddrinfo
