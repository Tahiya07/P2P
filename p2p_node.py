"""TCP peer networking, text messaging, and binary file transfer."""

import os
import socket
import threading
import uuid

import protocol


CHUNK_SIZE = 64 * 1024


class P2PNode:
    def __init__(self, peer_name, event_callback, download_dir="downloads"):
        self.peer_name = peer_name.strip()
        self.peer_id = uuid.uuid4().hex[:8]
        self.event_callback = event_callback
        self.download_dir = download_dir
        self.server_socket = None
        self.running = threading.Event()
        self.peers = {}
        self.peers_lock = threading.Lock()
        os.makedirs(self.download_dir, exist_ok=True)

    def _event(self, text):
        self.event_callback(text)

    def start(self, port):
        if self.running.is_set():
            raise RuntimeError("Peer is already running")
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind(("0.0.0.0", port))
            server.listen()
            server.settimeout(1.0)
        except Exception:
            server.close()
            raise
        self.server_socket = server
        self.running.set()
        threading.Thread(target=self._accept_loop, daemon=True).start()
        self._event(f"Listening on port {port}")

    def _accept_loop(self):
        while self.running.is_set():
            try:
                connection, address = self.server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(
                target=self._handle_connection,
                args=(connection, address, False),
                daemon=True,
            ).start()

    def connect(self, host, port):
        if not self.running.is_set():
            raise RuntimeError("Start the peer before connecting")
        connection = socket.create_connection((host, port), timeout=5)
        connection.settimeout(None)
        try:
            hello = self._hello()
            protocol.send_message(connection, hello)
            self._event(
                f"HELLO sent to {host}:{port} as {self.peer_name} [{self.peer_id}]"
            )

            response = protocol.receive_message(connection)
            self._validate_identity(response, "hello_ack")
            self._event(
                f"HELLO_ACK received from {response['peer_name']} "
                f"[{response['peer_id']}]"
            )
        except Exception:
            connection.close()
            raise
        self._register_peer(connection, response, (host, port))
        threading.Thread(
            target=self._receive_loop,
            args=(connection, response["peer_id"]),
            daemon=True,
        ).start()
        self._event(f"Connected to {response.get('peer_name', host)} [{response['peer_id']}]")

    def _hello(self):
        address = self.server_socket.getsockname() if self.server_socket else ("0.0.0.0", 0)
        return {
            "type": "hello",
            "peer_id": self.peer_id,
            "peer_name": self.peer_name,
            "port": address[1],
        }

    def _handle_connection(self, connection, address, outgoing):
        try:
            hello = protocol.receive_message(connection)
            self._validate_identity(hello, "hello")
            peer_id = hello["peer_id"]

            self._event(
                f"HELLO received from {hello['peer_name']} [{peer_id}]"
            )

            acknowledgement = {**self._hello(), "type": "hello_ack"}
            protocol.send_message(connection, acknowledgement)
            self._event(
                f"HELLO_ACK sent to {hello['peer_name']} [{peer_id}]"
            )
            self._register_peer(connection, hello, address)
            self._event(f"{hello.get('peer_name', 'Peer')} [{peer_id}] connected")
            self._receive_loop(connection, peer_id)
        except (OSError, ValueError, ConnectionError, UnicodeError) as exc:
            if self.running.is_set():
                self._event(f"[ERROR] Connection from {address[0]} failed: {exc}")
            try:
                connection.close()
            except OSError:
                pass

    @staticmethod
    def _validate_identity(message, expected_type):
        if message.get("type") != expected_type:
            raise ValueError(f"Expected {expected_type} message")

        peer_id = message.get("peer_id")
        peer_name = message.get("peer_name")
        port = message.get("port")

        if not isinstance(peer_id, str) or not peer_id:
            raise ValueError("Invalid peer identity")
        if not isinstance(peer_name, str) or not peer_name.strip():
            raise ValueError("Invalid peer name")
        if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
            raise ValueError("Invalid peer port")

    def _register_peer(self, connection, hello, address):
        peer_id = hello["peer_id"]
        with self.peers_lock:
            old_peer = self.peers.get(peer_id)
            self.peers[peer_id] = {
                "socket": connection,
                "name": hello.get("peer_name", "Peer"),
                "address": address,
                "send_lock": threading.Lock(),
            }
        if old_peer and old_peer["socket"] is not connection:
            try:
                old_peer["socket"].shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            old_peer["socket"].close()

    def _receive_loop(self, connection, peer_id):
        while self.running.is_set():
            try:
                message = protocol.receive_message(connection)
                kind = message.get("type")
                if kind == "text":
                    self._event(f"{message.get('sender_name', 'Peer')} -> You: {message.get('message', '')}")
                elif kind == "file":
                    self._receive_file(connection, message)
                else:
                    raise ValueError(f"Unknown message type: {kind}")
            except (OSError, ValueError, ConnectionError, UnicodeError) as exc:
                if self.running.is_set():
                    self._event(f"[ERROR] Peer disconnected or sent invalid data: {exc}")
                break
        self._remove_peer(peer_id, connection)

    def _receive_file(self, connection, metadata):
        filename = os.path.basename(metadata.get("filename", ""))
        size = metadata.get("filesize")
        if not filename or not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ValueError("Invalid file metadata")
        destination = os.path.join(self.download_dir, filename)
        base, extension = os.path.splitext(filename)
        suffix = 1
        while os.path.exists(destination):
            destination = os.path.join(self.download_dir, f"{base} ({suffix}){extension}")
            suffix += 1
        remaining = size
        with open(destination, "wb") as output:
            while remaining:
                chunk = connection.recv(min(CHUNK_SIZE, remaining))
                if not chunk:
                    raise ConnectionError("Peer disconnected during file transfer")
                output.write(chunk)
                remaining -= len(chunk)
        self._event(f"File received: {os.path.basename(destination)} ({size} bytes)")

    def send_text(self, peer_id, text):
        peer = self._get_peer(peer_id)
        message = {
            "type": "text",
            "sender_id": self.peer_id,
            "sender_name": self.peer_name,
            "message": text,
        }
        with peer["send_lock"]:
            protocol.send_message(peer["socket"], message)
        self._event(f"You -> {peer['name']}: {text}")

    def send_file(self, peer_id, path):
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        peer = self._get_peer(peer_id)
        size = os.path.getsize(path)
        metadata = {
            "type": "file",
            "sender_id": self.peer_id,
            "sender_name": self.peer_name,
            "filename": os.path.basename(path),
            "filesize": size,
        }
        with peer["send_lock"]:
            protocol.send_message(peer["socket"], metadata)
            with open(path, "rb") as source:
                while True:
                    chunk = source.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    peer["socket"].sendall(chunk)
        self._event(f"File sent to {peer['name']}: {metadata['filename']} ({size} bytes)")

    def _get_peer(self, peer_id):
        with self.peers_lock:
            peer = self.peers.get(peer_id)
        if not peer:
            raise ValueError("Select a connected peer first")
        return peer

    def _remove_peer(self, peer_id, connection):
        with self.peers_lock:
            peer = self.peers.get(peer_id)
            if peer and peer["socket"] is connection:
                del self.peers[peer_id]
                self._event(f"{peer['name']} [{peer_id}] disconnected")
        try:
            connection.close()
        except OSError:
            pass

    def connected_peers(self):
        with self.peers_lock:
            return [(peer_id, peer["name"]) for peer_id, peer in self.peers.items()]

    def stop(self):
        if not self.running.is_set():
            return
        self.running.clear()
        try:
            self.server_socket.close()
        except OSError:
            pass
        with self.peers_lock:
            peers = list(self.peers.items())
            self.peers.clear()
        for peer_id, peer in peers:
            try:
                peer["socket"].shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            peer["socket"].close()
            self._event(f"{peer['name']} [{peer_id}] disconnected")
        self._event("Peer stopped")
