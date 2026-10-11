"""Regression tests for one-way and simultaneous P2P connections."""

import queue
import tempfile
import threading
import time
import unittest

from p2p_node import P2PNode


def wait_until(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


class PeerConnectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.events_a = queue.Queue()
        self.events_b = queue.Queue()
        self.a = P2PNode("Alice", self.events_a.put, f"{self.tmp.name}/a")
        self.b = P2PNode("Bob", self.events_b.put, f"{self.tmp.name}/b")
        self.a.start(0)
        self.b.start(0)
        self.port_a = self.a.server_socket.getsockname()[1]
        self.port_b = self.b.server_socket.getsockname()[1]

    def tearDown(self):
        self.a.stop()
        self.b.stop()
        self.tmp.cleanup()

    def assert_connected_both_ways(self):
        self.assertTrue(wait_until(lambda: bool(self.a.connected_peers())))
        self.assertTrue(wait_until(lambda: bool(self.b.connected_peers())))
        self.assertEqual(len(self.a.connected_peers()), 1)
        self.assertEqual(len(self.b.connected_peers()), 1)

    @staticmethod
    def drain(event_queue):
        items = []
        while True:
            try:
                items.append(event_queue.get_nowait())
            except queue.Empty:
                return items

    def test_one_way_handshake_and_text(self):
        # Only Bob initiates the TCP connection, matching the assignment demo.
        self.b.connect("127.0.0.1", self.port_a)
        self.assert_connected_both_ways()

        peer_id_b, _ = self.a.connected_peers()[0]
        self.a.send_text(peer_id_b, "connection test")
        self.assertTrue(wait_until(lambda: any(
            "Alice -> You: connection test" in str(item)
            for item in self.drain(self.events_b)
        )))

    def test_simultaneous_connects_converge_to_one_connection(self):
        failures = []

        def connect(node, port):
            try:
                node.connect("127.0.0.1", port)
            except Exception as exc:
                failures.append(exc)

        threads = [
            threading.Thread(target=connect, args=(self.a, self.port_b)),
            threading.Thread(target=connect, args=(self.b, self.port_a)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=4)

        self.assertFalse(any(thread.is_alive() for thread in threads), "connect thread hung")
        self.assertEqual(failures, [])
        self.assertTrue(wait_until(lambda: (
            len(self.a.connected_peers()) == 1
            and len(self.b.connected_peers()) == 1
        )))
        self.assert_connected_both_ways()

        peer_id_b = self.a.connected_peers()[0][0]
        peer_id_a = self.b.connected_peers()[0][0]
        self.a.send_text(peer_id_b, "from Alice")
        self.b.send_text(peer_id_a, "from Bob")
        self.assertTrue(wait_until(lambda: any(
            "Bob -> You: from Bob" in str(item)
            for item in self.drain(self.events_a)
        )))
        self.assertTrue(wait_until(lambda: any(
            "Alice -> You: from Alice" in str(item)
            for item in self.drain(self.events_b)
        )))


if __name__ == "__main__":
    unittest.main()
