"""TCP peer networking, text messaging, and binary file transfer."""

import os
import socket
import threading
import uuid

import protocol

CHUNK_SIZE = 64 * 1024
HANDSHAKE_TIMEOUT = 5


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
        self._event(f"Listening on port {server.getsockname()[1]}")

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
                args=(connection, address),
                daemon=True,
            ).start()

    def connect(self, host, port):
        if not self.running.is_set():
            raise RuntimeError("Start the peer before connecting")

        connection_id = uuid.uuid4().hex
        connection = socket.create_connection((host, port), timeout=HANDSHAKE_TIMEOUT)
        connection.settimeout(HANDSHAKE_TIMEOUT)
        try:
            hello = self._hello(connection_id)
            protocol.send_message(connection, hello)
            self._event(f"HELLO sent to {host}:{port} [{self.peer_id}]")

            response = protocol.receive_message(connection)
            self._validate_identity(response, "hello_ack")
            if response.get("connection_id") != connection_id:
                raise ValueError("HELLO_ACK connection ID did not match the request")
            if response["peer_id"] == self.peer_id:
                raise ValueError("Cannot connect a peer to itself")
            self._event(
                f"HELLO_ACK received from {response['peer_name']} [{response['peer_id']}]"
            )

            # Do not register the accepted socket until the initiator confirms
            # that it actually received HELLO_ACK. This prevents a duplicate
            # connection from closing the socket while its initiator is waiting.
            protocol.send_message(connection, {
                "type": "hello_confirm",
                "connection_id": connection_id,
            })
            result = protocol.receive_message(connection)
            if result.get("connection_id") != connection_id:
                raise ValueError("Handshake response connection ID did not match")
            if result.get("type") == "hello_rejected":
                connection.close()
                self._event(
                    f"Duplicate connection ignored for {response['peer_name']} "
                    f"[{response['peer_id']}]"
                )
                return
            if result.get("type") != "hello_ready":
                raise ValueError(
                    "Expected HELLO_READY after HELLO_ACK, received "
                    f"{result.get('type')!r}"
                )

            connection.settimeout(None)
            peer_info = dict(response)
            peer_info["connection_id"] = connection_id
            accepted = self._register_peer(
                connection,
                peer_info,
                (host, port),
                initiator_id=self.peer_id,
                connection_id=connection_id,
            )
            if not accepted:
                connection.close()
                self._event(
                    f"Duplicate connection ignored for {response['peer_name']} "
                    f"[{response['peer_id']}]"
                )
                return

            threading.Thread(
                target=self._receive_loop,
                args=(connection, response["peer_id"]),
                daemon=True,
            ).start()
            self._event(f"Connected to {response['peer_name']} [{response['peer_id']}]")
        except Exception:
            try:
                connection.close()
            except OSError:
                pass
            raise

    def _hello(self, connection_id=None):
        address = self.server_socket.getsockname() if self.server_socket else ("0.0.0.0", 0)
        message = {
            "type": "hello",
            "peer_id": self.peer_id,
            "peer_name": self.peer_name,
            "port": address[1],
        }
        if connection_id is not None:
            message["connection_id"] = connection_id
        return message

    @staticmethod
    def _validate_identity(message, expected_type):
        if message.get("type") != expected_type:
            raise ValueError(
                f"Expected {expected_type}, received {message.get('type')!r}. "
                "Ensure both peers are running the same updated project version."
            )
        peer_id = message.get("peer_id")
        peer_name = message.get("peer_name")
        port = message.get("port")
        if not isinstance(peer_id, str) or not peer_id:
            raise ValueError("Invalid peer identity in handshake")
        if not isinstance(peer_name, str) or not peer_name.strip():
            raise ValueError("Invalid peer name in handshake")
        if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
            raise ValueError("Invalid peer port in handshake")

    def _handle_connection(self, connection, address):
        connection.settimeout(HANDSHAKE_TIMEOUT)
        try:
            hello = protocol.receive_message(connection)
            self._validate_identity(hello, "hello")
            peer_id = hello["peer_id"]
            connection_id = hello.get("connection_id")
            if not isinstance(connection_id, str) or not connection_id:
                raise ValueError("Missing connection ID in HELLO")
            if peer_id == self.peer_id:
                protocol.send_message(connection, {
                    "type": "hello_rejected",
                    "connection_id": connection_id,
                    "reason": "self_connection",
                })
                return

            self._event(f"HELLO received from {hello['peer_name']} [{peer_id}]")
            acknowledgement = self._hello(connection_id)
            # Set the type after constructing identity metadata. If **self._hello()
            # were unpacked after type='hello_ack', its type='hello' would override it.
            acknowledgement["type"] = "hello_ack"
            protocol.send_message(connection, acknowledgement)
            self._event(f"HELLO_ACK sent to {hello['peer_name']} [{peer_id}]")

            confirmation = protocol.receive_message(connection)
            if confirmation.get("type") != "hello_confirm":
                if confirmation.get("type") == "hello_reject":
                    return
                raise ValueError("Expected HELLO_CONFIRM after HELLO_ACK")
            if confirmation.get("connection_id") != connection_id:
                raise ValueError("HELLO_CONFIRM connection ID did not match")

            accepted = self._register_peer(
                connection,
                hello,
                address,
                initiator_id=peer_id,
                connection_id=connection_id,
            )
            if not accepted:
                protocol.send_message(connection, {
                    "type": "hello_rejected",
                    "connection_id": connection_id,
                    "reason": "duplicate_connection",
                })
                self._event(
                    f"Duplicate connection ignored for {hello['peer_name']} [{peer_id}]"
                )
                return

            protocol.send_message(connection, {
                "type": "hello_ready",
                "connection_id": connection_id,
            })
            connection.settimeout(None)
            self._event(f"{hello['peer_name']} [{peer_id}] connected")
            self._receive_loop(connection, peer_id)
        except (OSError, ValueError, ConnectionError, UnicodeError) as exc:
            if self.running.is_set():
                self._event(f"[ERROR] Connection from {address[0]} failed: {exc}")
        finally:
            try:
                connection.close()
            except OSError:
                pass

    def _register_peer(self, connection, hello, address, initiator_id, connection_id):
        """Register one live connection and deterministically resolve duplicates.

        If both peers initiate connections concurrently, both ends prefer the same
        connection: the one with the lexicographically smaller (initiator peer ID,
        connection ID) pair. A single connection is accepted regardless of direction.
        """
        peer_id = hello["peer_id"]
        candidate_rank = (initiator_id, connection_id)
        old_socket = None
        with self.peers_lock:
            old_peer = self.peers.get(peer_id)
            if old_peer is not None:
                if old_peer["socket"] is connection:
                    return True
                old_rank = (old_peer["initiator_id"], old_peer["connection_id"])
                if old_rank <= candidate_rank:
                    return False
                old_socket = old_peer["socket"]

            self.peers[peer_id] = {
                "socket": connection,
                "name": hello.get("peer_name", "Peer"),
                "address": address,
                "send_lock": threading.Lock(),
                "initiator_id": initiator_id,
                "connection_id": connection_id,
            }

        if old_socket is not None:
            try:
                old_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                old_socket.close()
            except OSError:
                pass
        return True

    def _receive_loop(self, connection, peer_id):
        while self.running.is_set():
            try:
                message = protocol.receive_message(connection)
                kind = message.get("type")
                if kind == "text":
                    self._event(
                        f"{message.get('sender_name', 'Peer')} -> You: "
                        f"{message.get('message', '')}"
                    )
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
            try:
                peer["socket"].close()
            except OSError:
                pass
            self._event(f"{peer['name']} [{peer_id}] disconnected")
        self._event("Peer stopped")
