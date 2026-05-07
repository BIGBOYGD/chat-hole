import re
import socket
import subprocess
import sys
from datetime import datetime


def timestamp():
    return datetime.now().strftime("%H:%M:%S")


def is_ipv4(text):
    parts = text.split(".")
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(part) <= 255 for part in parts)
    except ValueError:
        return False


def is_private_lan_ip(ip):
    if not is_ipv4(ip):
        return False
    a, b, _, _ = [int(part) for part in ip.split(".")]
    return a == 10 or (a == 172 and 16 <= b <= 31) or (a == 192 and b == 168)


def local_ips():
    adapters = []
    try:
        ipconfig_encoding = "mbcs" if sys.platform.startswith("win") else "utf-8"
        output = subprocess.check_output(["ipconfig"], encoding=ipconfig_encoding, errors="ignore")

        current_adapter = ""
        current_ipv4 = None
        current_has_gateway = False

        def finish_adapter():
            if current_adapter and current_ipv4:
                adapters.append(
                    {
                        "name": current_adapter,
                        "ip": current_ipv4,
                        "has_gateway": current_has_gateway,
                    }
                )

        for line in output.splitlines():
            stripped = line.strip()
            if line == line.lstrip() and stripped.endswith(":") and "IPv4" not in stripped:
                finish_adapter()
                current_adapter = stripped[:-1]
                current_ipv4 = None
                current_has_gateway = False
                continue

            if "IPv4" in stripped:
                match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", stripped)
                if match:
                    current_ipv4 = match.group(0)
                continue

            if "Default Gateway" in stripped or "默认网关" in stripped:
                current_has_gateway = bool(re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", stripped))
                continue

            if current_ipv4 and re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", stripped):
                current_has_gateway = True

        finish_adapter()
    except (OSError, subprocess.SubprocessError):
        pass

    def adapter_score(adapter_info):
        adapter = adapter_info["name"].lower()
        ip = adapter_info["ip"]
        if is_private_lan_ip(ip) and adapter_info["has_gateway"]:
            return 0
        if any(word in adapter for word in ("wlan", "wi-fi", "wireless", "无线")):
            return 1
        if any(word in adapter for word in ("vmware", "virtual", "flclash", "vpn", "虚拟")):
            return 3
        return 2

    adapters.sort(key=adapter_score)
    ips = [adapter["ip"] for adapter in adapters]

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ips.append(info[4][0])
    except OSError:
        pass

    cleaned = []
    for ip in ips:
        if ip.startswith(("127.", "169.254.")):
            continue
        if ip not in cleaned:
            cleaned.append(ip)

    private_ips = [ip for ip in cleaned if is_private_lan_ip(ip)]
    return private_ips or cleaned or ["127.0.0.1"]


def command_arg(line, commands):
    if line.startswith("\\"):
        line = "/" + line[1:]

    for command in commands:
        if line == command:
            return ""
        prefix = command + " "
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return None
