from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import struct
from dataclasses import dataclass
from typing import Any


@dataclass
class RpfmWsClient:
    host: str = "127.0.0.1"
    port: int = 45127
    path: str = "/ws"
    timeout: int = 120

    def __post_init__(self) -> None:
        self._next_id = 1
        self._socket: socket.socket | None = None

    def connect(self) -> dict[str, Any]:
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        sock.sendall(request.encode("ascii"))
        response = _read_http_response(sock)
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise RuntimeError(response.decode("utf-8", errors="replace"))
        expected = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
        ).decode("ascii")
        if f"Sec-WebSocket-Accept: {expected}".lower() not in response.decode("ascii", errors="ignore").lower():
            raise RuntimeError("Invalid WebSocket accept key.")
        self._socket = sock
        return self.receive()

    def send(self, command: object | str) -> dict[str, Any]:
        if self._socket is None:
            raise RuntimeError("WebSocket is not connected.")
        message_id = self._next_id
        self._next_id += 1
        payload = json.dumps({"id": message_id, "data": command}, separators=(",", ":")).encode("utf-8")
        self._socket.sendall(_encode_client_frame(payload))
        while True:
            response = self.receive()
            if response.get("id") == message_id:
                return response

    def receive(self) -> dict[str, Any]:
        if self._socket is None:
            raise RuntimeError("WebSocket is not connected.")
        payload = _read_server_frame(self._socket)
        return json.loads(payload.decode("utf-8"))

    def close(self) -> None:
        if self._socket is not None:
            try:
                self.send("ClientDisconnecting")
            except Exception:
                pass
            self._socket.close()
            self._socket = None


def _read_http_response(sock: socket.socket) -> bytes:
    chunks = []
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        chunks.append(chunk)
        data = b"".join(chunks)
        if b"\r\n\r\n" in data:
            return data
    raise RuntimeError("WebSocket handshake failed.")


def _encode_client_frame(payload: bytes) -> bytes:
    first = 0x81
    mask = os.urandom(4)
    length = len(payload)
    if length < 126:
        header = bytes([first, 0x80 | length])
    elif length <= 0xFFFF:
        header = bytes([first, 0x80 | 126]) + struct.pack("!H", length)
    else:
        header = bytes([first, 0x80 | 127]) + struct.pack("!Q", length)
    masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return header + mask + masked


def _read_server_frame(sock: socket.socket) -> bytes:
    first_two = _recv_exact(sock, 2)
    opcode = first_two[0] & 0x0F
    if opcode == 0x8:
        raise RuntimeError("WebSocket closed by server.")
    if opcode != 0x1:
        raise RuntimeError(f"Unsupported WebSocket opcode: {opcode}")
    masked = bool(first_two[1] & 0x80)
    length = first_two[1] & 0x7F
    if length == 126:
        length = struct.unpack("!H", _recv_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _recv_exact(sock, 8))[0]
    mask = _recv_exact(sock, 4) if masked else b""
    payload = _recv_exact(sock, length)
    if masked:
        payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return payload


def _recv_exact(sock: socket.socket, length: int) -> bytes:
    chunks = []
    remaining = length
    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            raise RuntimeError("Unexpected EOF from WebSocket.")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)
