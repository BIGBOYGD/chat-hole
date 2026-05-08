import json
import unittest

from lan_chat.server import ChatServer


class FakeSocket:
    def __init__(self):
        self.packets = []

    def sendall(self, data):
        for line in data.splitlines():
            self.packets.append(json.loads(line.decode("utf-8")))


class ServerContactTests(unittest.TestCase):
    def test_join_broadcasts_updated_users_before_system_message(self):
        server = ChatServer()
        first_sock = FakeSocket()
        second_sock = FakeSocket()

        server.add_client(first_sock, ("192.168.1.2", 10001), "Alice")
        server.add_client(second_sock, ("192.168.1.3", 10002), "Bob")

        bob_join_index = next(
            index
            for index, packet in enumerate(first_sock.packets)
            if packet.get("type") == "system" and "Bob" in packet.get("text", "")
        )
        list_before_join = [
            packet
            for packet in first_sock.packets[:bob_join_index]
            if packet.get("type") == "list"
            and {user["name"] for user in packet.get("users", [])} == {"Alice", "Bob"}
        ]

        self.assertTrue(list_before_join)

    def test_dm_target_can_be_client_id_after_reconnect(self):
        server = ChatServer()
        alice_sock = FakeSocket()
        old_bob_sock = FakeSocket()
        new_bob_sock = FakeSocket()

        alice = server.add_client(alice_sock, ("192.168.1.2", 10001), "Alice")
        old_bob = server.add_client(old_bob_sock, ("192.168.1.3", 10002), "Bob")
        server.remove_client(old_bob)
        new_bob = server.add_client(new_bob_sock, ("192.168.1.3", 10003), "Bob")

        payload = server.users_payload()
        bob_user = next(user for user in payload["users"] if user["name"] == "Bob")
        self.assertEqual(2, bob_user["no"])
        self.assertEqual(3, bob_user["id"])

        server.forward_dm(alice, {"to": str(new_bob.id), "text": "hello"})

        self.assertIn(
            {"type": "message", "scope": "dm", "from_id": alice.id, "from_name": "Alice", "text": "hello", "file": None},
            new_bob_sock.packets,
        )


if __name__ == "__main__":
    unittest.main()
