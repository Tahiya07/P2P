"""Length-prefixed JSON framing for the P2P application protocol."""

import json
import struct


HEADER_SIZE = 4
MAX_MESSAGE_SIZE = 1024 * 1024


def encode_message(message):
    payload = json.dumps(message, ensure_ascii=False).encode("utf-8")
    if len(payload) > MAX_MESSAGE_SIZE:
        raise ValueError("Message is too large")
    return struct.pack("!I", len(payload)) + payload


def send_message(connection, message):
    connection.sendall(encode_message(message))


def receive_exactly(connection, size):
    chunks = bytearray()
    while len(chunks) < size:
        chunk = connection.recv(size - len(chunks))
        if not chunk:
            raise ConnectionError("Peer disconnected")
        chunks.extend(chunk)
    return bytes(chunks)


def receive_message(connection):
    header = receive_exactly(connection, HEADER_SIZE)
    size = struct.unpack("!I", header)[0]
    if size == 0 or size > MAX_MESSAGE_SIZE:
        raise ValueError("Invalid message size")
    payload = receive_exactly(connection, size)
    message = json.loads(payload.decode("utf-8"))
    if not isinstance(message, dict) or not isinstance(message.get("type"), str):
        raise ValueError("Invalid message")
    return message
