import json


def send_json(sock, packet):
    data = (json.dumps(packet, ensure_ascii=False) + "\n").encode("utf-8")
    sock.sendall(data)


def read_json_lines(sock, on_packet):
    buffer = b""
    while True:
        chunk = sock.recv(65536)
        if not chunk:
            break
        buffer += chunk
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            if not line.strip():
                continue
            try:
                packet = json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                continue
            on_packet(packet)
