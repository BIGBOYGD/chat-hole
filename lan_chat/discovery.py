import json
import socket
import threading
import time

from .config import DEFAULT_DISCOVERY_INTERVAL, DEFAULT_DISCOVERY_TIMEOUT, DEFAULT_PORT
from .utils import is_private_lan_ip, local_ips


DISCOVERY_MAGIC = "chat-hole-discovery-v1"


class DiscoveryBroadcast:
    def __init__(self, stop_event, thread):
        self._stop_event = stop_event
        self._thread = thread

    def set(self):
        self._stop_event.set()

    def is_set(self):
        return self._stop_event.is_set()

    def join(self, timeout=None):
        self._thread.join(timeout)


def _broadcast_addresses():
    addresses = {"255.255.255.255"}
    for ip in local_ips():
        parts = ip.split(".")
        if len(parts) == 4:
            addresses.add(".".join(parts[:3] + ["255"]))
    return sorted(addresses)


def _announcement_payload(port):
    return json.dumps(
        {
            "magic": DISCOVERY_MAGIC,
            "name": socket.gethostname(),
            "port": port,
        },
        ensure_ascii=False,
    ).encode("utf-8")


def start_discovery_broadcast(port=DEFAULT_PORT, interval=DEFAULT_DISCOVERY_INTERVAL):
    stop_event = threading.Event()

    def loop():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            payload = _announcement_payload(port)
            addresses = _broadcast_addresses()
            while not stop_event.is_set():
                for address in addresses:
                    try:
                        sock.sendto(payload, (address, port))
                    except OSError:
                        pass
                stop_event.wait(interval)
        finally:
            sock.close()

    thread = threading.Thread(target=loop, name="lan-chat-discovery", daemon=True)
    thread.start()
    return DiscoveryBroadcast(stop_event, thread)


def discover_servers(port=DEFAULT_PORT, timeout=DEFAULT_DISCOVERY_TIMEOUT):
    servers = {}
    deadline = time.monotonic() + timeout
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", port))
        sock.settimeout(0.2)
        while time.monotonic() < deadline:
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break

            try:
                packet = json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue

            if packet.get("magic") != DISCOVERY_MAGIC:
                continue

            try:
                server_port = int(packet.get("port") or port)
            except (TypeError, ValueError):
                continue
            host = addr[0]
            if not is_private_lan_ip(host):
                continue
            servers[(host, server_port)] = {
                "host": host,
                "port": server_port,
                "name": str(packet.get("name") or host),
                "last_seen": time.monotonic(),
            }
    finally:
        sock.close()

    return sorted(servers.values(), key=lambda item: (item["name"].lower(), item["host"], item["port"]))
