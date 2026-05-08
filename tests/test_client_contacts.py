import unittest

from lan_chat.client import ChatClient


class ClientContactTests(unittest.TestCase):
    def test_target_label_resolves_client_id_not_only_list_number(self):
        client = ChatClient(sock=None, name="yu")
        client.set_users(
            {
                "type": "list",
                "users": [
                    {"id": 1, "no": 1, "name": "yu", "ip": "192.168.19.14"},
                    {"id": 3, "no": 2, "name": "jsq", "ip": "192.168.19.14"},
                ],
            }
        )
        client.mode = "dm"
        client.target = "3"

        self.assertEqual("jsq", client.target_label())


if __name__ == "__main__":
    unittest.main()
