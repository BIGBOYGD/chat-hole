import json
import socket
import threading
from dataclasses import dataclass, field

from .config import DEFAULT_PORT
from .discovery import start_discovery_broadcast
from .protocol import read_json_lines, send_json
from .utils import local_ips


@dataclass
class ClientConnection:
    id: int
    name: str
    conn: socket.socket
    addr: tuple
    lock: threading.Lock = field(default_factory=threading.Lock)


class ChatServer:
    def __init__(self):
        self.clients = {}
        self.groups = {}
        self.next_client_id = 1
        self.lock = threading.RLock()

    def send_to_client(self, client, packet):
        try:
            with client.lock:
                send_json(client.conn, packet)
            return True
        except OSError:
            return False

    def broadcast(self, packet, exclude_id=None):
        with self.lock:
            clients = list(self.clients.values())
        for client in clients:
            if client.id != exclude_id:
                self.send_to_client(client, packet)

    def system_to_all(self, text):
        self.broadcast({"type": "system", "text": text})

    def find_client(self, target):
        target = str(target).strip()
        with self.lock:
            if target.isdigit() and int(target) in self.clients:
                return self.clients[int(target)]
            if target.isdigit():
                online_clients = sorted(self.clients.values(), key=lambda item: item.id)
                index = int(target) - 1
                if 0 <= index < len(online_clients):
                    return online_clients[index]

            lowered = target.lower()
            for client in self.clients.values():
                if client.name.lower() == lowered:
                    return client
        return None

    def users_payload(self):
        with self.lock:
            online_clients = sorted(self.clients.values(), key=lambda item: item.id)
            user_no_by_id = {client.id: index for index, client in enumerate(online_clients, start=1)}
            users = [
                {"id": client.id, "no": user_no_by_id[client.id], "name": client.name, "ip": client.addr[0]}
                for client in online_clients
            ]
            groups = [
                {
                    "name": name,
                    "members": [user_no_by_id[member_id] for member_id in sorted(members) if member_id in user_no_by_id],
                }
                for name, members in self.groups.items()
            ]
        return {"type": "list", "users": users, "groups": groups}

    def add_client(self, conn, addr, name):
        with self.lock:
            client_id = self.next_client_id
            self.next_client_id += 1
            client = ClientConnection(client_id, name or f"用户{client_id}", conn, addr)
            self.clients[client_id] = client

        self.send_to_client(client, {"type": "welcome", "id": client.id, "name": client.name})
        self.send_to_client(client, self.users_payload())
        self.system_to_all(f"{client.name} 加入了聊天")
        return client

    def remove_client(self, client):
        with self.lock:
            self.clients.pop(client.id, None)
            for members in self.groups.values():
                members.discard(client.id)
        self.system_to_all(f"{client.name} 离开了聊天")

    def handle_packet(self, client, packet):
        packet_type = packet.get("type")

        if packet_type == "list":
            self.send_to_client(client, self.users_payload())
            return

        if packet_type == "rename":
            new_name = str(packet.get("name", "")).strip()
            if not new_name:
                self.send_to_client(client, {"type": "error", "text": "名字不能为空"})
                return
            old_name = client.name
            with self.lock:
                client.name = new_name
            self.system_to_all(f"{old_name} 改名为 {new_name}")
            self.broadcast(self.users_payload())
            return

        if packet_type == "dm":
            self.forward_dm(client, packet)
            return

        if packet_type == "file_chunk":
            self.forward_file_chunk(client, packet)
            return

        if packet_type == "group_create":
            self.create_group(client, packet)
            return

        if packet_type == "group_msg":
            self.forward_group_message(client, packet)

    def forward_dm(self, client, packet):
        target = self.find_client(packet.get("to", ""))
        if not target:
            self.send_to_client(client, {"type": "error", "text": "找不到这个联系人"})
            return

        message = {
            "type": "message",
            "scope": "dm",
            "from_id": client.id,
            "from_name": client.name,
            "text": packet.get("text", ""),
            "file": packet.get("file"),
        }
        self.send_to_client(target, message)
        if target.id != client.id:
            self.send_to_client(client, {**message, "echo": True})

    def forward_file_chunk(self, client, packet):
        scope = packet.get("scope")
        message = {
            "type": "file_chunk",
            "scope": scope,
            "from_id": client.id,
            "from_name": client.name,
            "file_id": packet.get("file_id"),
            "name": packet.get("name"),
            "size": packet.get("size"),
            "index": packet.get("index"),
            "total": packet.get("total"),
            "data": packet.get("data"),
        }

        if scope == "dm":
            target = self.find_client(packet.get("to", ""))
            if not target:
                self.send_to_client(client, {"type": "error", "text": "找不到这个联系人"})
                return
            self.send_to_client(target, message)
            if target.id != client.id:
                self.send_to_client(client, {**message, "echo": True})
            return

        if scope == "group":
            group_name = str(packet.get("group", "")).strip()
            with self.lock:
                member_ids = set(self.groups.get(group_name, set()))
            if not member_ids:
                self.send_to_client(client, {"type": "error", "text": "找不到这个群聊"})
                return
            if client.id not in member_ids:
                member_ids.add(client.id)

            message["group"] = group_name
            with self.lock:
                targets = [self.clients[member_id] for member_id in member_ids if member_id in self.clients]
            for target in targets:
                self.send_to_client(target, message)

    def create_group(self, client, packet):
        group_name = str(packet.get("group", "")).strip()
        members = [str(member).strip() for member in packet.get("members", []) if str(member).strip()]
        if not group_name:
            self.send_to_client(client, {"type": "error", "text": "群名不能为空"})
            return

        member_ids = {client.id}
        for member in members:
            found = self.find_client(member)
            if found:
                member_ids.add(found.id)

        with self.lock:
            self.groups[group_name] = member_ids
        self.system_to_all(f"{client.name} 创建了群聊 {group_name}")
        self.broadcast(self.users_payload())

    def forward_group_message(self, client, packet):
        group_name = str(packet.get("group", "")).strip()
        with self.lock:
            member_ids = set(self.groups.get(group_name, set()))
        if not member_ids:
            self.send_to_client(client, {"type": "error", "text": "找不到这个群聊"})
            return
        if client.id not in member_ids:
            member_ids.add(client.id)

        message = {
            "type": "message",
            "scope": "group",
            "group": group_name,
            "from_id": client.id,
            "from_name": client.name,
            "text": packet.get("text", ""),
            "file": packet.get("file"),
        }
        with self.lock:
            targets = [self.clients[member_id] for member_id in member_ids if member_id in self.clients]
        for target in targets:
            self.send_to_client(target, message)

    def handle_connection(self, conn, addr):
        client = None
        try:
            first_line = b""
            while b"\n" not in first_line:
                chunk = conn.recv(4096)
                if not chunk:
                    return
                first_line += chunk
            line, rest = first_line.split(b"\n", 1)
            hello = json.loads(line.decode("utf-8"))
            if hello.get("type") != "hello":
                return

            client = self.add_client(conn, addr, str(hello.get("name", "")).strip())
            if rest.strip():
                for raw in rest.split(b"\n"):
                    if raw.strip():
                        self.handle_packet(client, json.loads(raw.decode("utf-8")))

            read_json_lines(conn, lambda packet: self.handle_packet(client, packet))
        except (OSError, json.JSONDecodeError):
            pass
        finally:
            if client:
                self.remove_client(client)
            try:
                conn.close()
            except OSError:
                pass


def run_server(port=DEFAULT_PORT):
    server = ChatServer()
    discovery_stop = None
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    else:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", port))
    sock.listen()
    sock.settimeout(0.5)
    discovery_stop = start_discovery_broadcast(port)

    ips = local_ips()
    print(f"聊天服务器已启动。端口: {port}")
    print(f"本机IP: {ips[0]}")
    if len(ips) > 1:
        print(f"其他网卡IP: {', '.join(ips[1:])}")
    print("客户端现在可以直接运行: python .\\lan_chat.py")
    print("按 Ctrl+C 关闭服务器。")

    try:
        while True:
            try:
                conn, addr = sock.accept()
            except socket.timeout:
                continue
            thread = threading.Thread(target=server.handle_connection, args=(conn, addr), daemon=True)
            thread.start()
    except KeyboardInterrupt:
        print("\n服务器已关闭。")
    finally:
        if discovery_stop:
            discovery_stop.set()
        sock.close()
