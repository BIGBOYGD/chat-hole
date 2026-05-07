import base64
import re
import socket
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from .config import FILE_CHUNK_SIZE, RECEIVED_DIR
from .protocol import read_json_lines, send_json
from .terminal import notify, print_line, read_chat_line
from .utils import command_arg, timestamp


class ChatClient:
    def __init__(self, sock, name):
        self.sock = sock
        self.name = name
        self.my_id = None
        self.users = {}
        self.groups = {}
        self.incoming_files = {}
        self.mode = None
        self.target = ""
        self.send_lock = threading.Lock()
        self.running = True

    def send(self, packet):
        with self.send_lock:
            send_json(self.sock, packet)

    def set_users(self, packet):
        self.users = {str(user["id"]): user for user in packet.get("users", [])}
        self.groups = {group["name"]: group.get("members", []) for group in packet.get("groups", [])}

    def find_user(self, target):
        target = str(target).strip()
        if target.isdigit():
            for user in self.users.values():
                if str(user.get("no")) == target or str(user.get("id")) == target:
                    return user
        lowered = target.lower()
        for user in self.users.values():
            if user["name"].lower() == lowered:
                return user
        return None

    def target_label(self):
        if self.mode == "dm":
            user = self.find_user(self.target)
            return user["name"] if user else self.target
        if self.mode == "group":
            return f"群聊 {self.target}"
        return "未选择"

    def prompt(self):
        if self.mode == "dm":
            return f"[私聊:{self.target_label()}] > "
        if self.mode == "group":
            return f"[群聊:{self.target}] > "
        return "[未选择会话] > "

    def file_prefix(self, packet):
        from_name = packet.get("from_name", "未知")
        if packet.get("scope") == "group":
            return f"[{timestamp()}][群:{packet.get('group')}] {from_name}"
        if packet.get("echo") or packet.get("from_id") == self.my_id:
            return f"[{timestamp()}][我 -> 私聊:{self.target_label()}]"
        return f"[{timestamp()}][私聊] {from_name}"

    def handle_file_chunk(self, packet):
        if packet.get("from_id") == self.my_id:
            return

        notify()
        file_id = str(packet.get("file_id") or "")
        if not file_id:
            return

        try:
            total = int(packet.get("total", 0))
            size = int(packet.get("size", 0))
            chunk = base64.b64decode(packet.get("data", ""))
        except (TypeError, ValueError):
            return

        original_name = Path(str(packet.get("name") or "file")).name
        safe_name = re.sub(r"[^A-Za-z0-9_.\-\u4e00-\u9fff]", "_", original_name)
        RECEIVED_DIR.mkdir(parents=True, exist_ok=True)

        state = self.incoming_files.get(file_id)
        if not state:
            saved_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_name}"
            final_path = RECEIVED_DIR / saved_name
            temp_path = RECEIVED_DIR / f".{saved_name}.part"
            state = {"path": final_path, "temp": temp_path, "received": 0, "total": total, "size": size}
            self.incoming_files[file_id] = state
            print_line(f"{self.file_prefix(packet)} 正在接收文件: {original_name}")

        try:
            with state["temp"].open("ab") as file:
                file.write(chunk)
            state["received"] += 1
        except OSError:
            print_line(f"{self.file_prefix(packet)} 文件接收失败: {original_name}")
            self.incoming_files.pop(file_id, None)
            return

        if state["received"] >= state["total"]:
            try:
                state["temp"].replace(state["path"])
                print_line(f"{self.file_prefix(packet)} 文件已保存: {state['path']}")
            except OSError:
                print_line(f"{self.file_prefix(packet)} 文件保存失败: {original_name}")
            self.incoming_files.pop(file_id, None)

    def handle_packet(self, packet):
        packet_type = packet.get("type")

        if packet_type == "welcome":
            self.my_id = packet.get("id")
            self.name = packet.get("name", self.name)
            print_line(f"已连接服务器。你的编号: {self.my_id}，名字: {self.name}")
            return

        if packet_type == "list":
            self.set_users(packet)
            return

        if packet_type == "system":
            print_line(f"[系统] {packet.get('text', '')}")
            return

        if packet_type == "error":
            print_line(f"[错误] {packet.get('text', '')}")
            return

        if packet_type == "file_chunk":
            self.handle_file_chunk(packet)
            return

        if packet_type != "message":
            return

        from_name = packet.get("from_name", "未知")
        text = str(packet.get("text", ""))
        echo = packet.get("echo", False)
        is_self = packet.get("from_id") == self.my_id

        if not echo and not is_self:
            notify()

        if packet.get("scope") == "group":
            if is_self:
                prefix = f"[{timestamp()}][我 -> 群:{packet.get('group')}]"
            else:
                prefix = f"[{timestamp()}][群:{packet.get('group')}] {from_name}"
        elif echo or is_self:
            prefix = f"[{timestamp()}][我 -> 私聊:{self.target_label()}]"
        else:
            prefix = f"[{timestamp()}][私聊] {from_name}"

        if text:
            print_line(f"{prefix}: {text}")

    def listen(self):
        try:
            read_json_lines(self.sock, self.handle_packet)
        except OSError:
            pass
        self.running = False
        print_line("已断开服务器连接。")

    def print_help(self):
        print_line("命令:")
        print_line("  /l                 查看在线联系人和群聊")
        print_line("  /p 名字或序号      私聊某个联系人")
        print_line("  /c 群名 成员1 成员2 创建群聊")
        print_line("  /g 群名            切换到群聊")
        print_line("  /img 文件路径      发送图片或文件")
        print_line("  /n 新名字          修改自己的名字")
        print_line("  /t                 测试提醒")
        print_line("  /q                 退出")
        print_line("中文命令也可用: /联系人 /私聊 /建群 /群聊 /图片 /改名 /退出")

    def print_contacts(self):
        print_line("在线联系人:")
        for user in sorted(self.users.values(), key=lambda item: item.get("no", item["id"])):
            mark = "（我）" if user["id"] == self.my_id else ""
            print_line(f"  {user.get('no', user['id'])}. {user['name']} {mark}  {user.get('ip', '')}")
        if self.groups:
            print_line("群聊:")
            for name, members in self.groups.items():
                print_line(f"  {name}  成员编号: {', '.join(str(member) for member in members)}")

    def send_current_text(self, text):
        if self.mode == "dm":
            self.send({"type": "dm", "to": self.target, "text": text})
            return
        if self.mode == "group":
            self.send({"type": "group_msg", "group": self.target, "text": text})
            return
        print_line("还没有选择会话。先用 /p 名字 或 /g 群名。")

    def send_current_file(self, path_text):
        if not self.mode:
            print_line("还没有选择会话。先用 /p 或 /g。")
            return

        path = Path(path_text.strip().strip('"').strip("'"))
        if not path.exists():
            print_line("文件不存在。")
            return
        if path.is_dir():
            print_line("这是文件夹，不是文件。当前只支持发送单个图片或文件。")
            return
        if not path.is_file():
            print_line("这个路径不是普通文件。")
            return

        thread = threading.Thread(target=self.send_file_worker, args=(path,), daemon=True)
        thread.start()

    def send_file_worker(self, path):
        try:
            file_size = path.stat().st_size
        except OSError as exc:
            print_line(f"读取文件失败: {exc}")
            return

        mode = self.mode
        target = self.target
        if not mode or not target:
            print_line("还没有选择会话。先用 /p 或 /g。")
            return

        file_id = uuid.uuid4().hex
        total = max(1, (file_size + FILE_CHUNK_SIZE - 1) // FILE_CHUNK_SIZE)
        print_line(f"开始发送文件: {path.name} ({file_size} 字节，共 {total} 片)")

        try:
            with path.open("rb") as file:
                for index in range(total):
                    chunk = file.read(FILE_CHUNK_SIZE)
                    packet = {
                        "type": "file_chunk",
                        "scope": mode,
                        "file_id": file_id,
                        "name": path.name,
                        "size": file_size,
                        "index": index,
                        "total": total,
                        "data": base64.b64encode(chunk).decode("ascii"),
                    }
                    if mode == "dm":
                        packet["to"] = target
                    else:
                        packet["group"] = target
                    self.send(packet)
        except OSError as exc:
            print_line(f"发送文件失败: {exc}")
            return

        print_line(f"已发送文件: {path.name}")

    def command_loop(self):
        self.print_help()
        while self.running:
            try:
                line = read_chat_line(self.prompt()).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not line:
                continue
            if line.startswith("\\"):
                line = "/" + line[1:]

            if line in {"/q", "/退出", "退出", "q", "quit", "exit"}:
                break
            if line in {"/h", "/帮助", "帮助", "help"}:
                self.print_help()
                continue
            if line in {"/l", "/联系人", "联系人", "ls"}:
                self.send({"type": "list"})
                time.sleep(0.1)
                self.print_contacts()
                continue

            target = command_arg(line, ["/p", "/私聊"])
            if target is not None:
                if not target:
                    print_line("用法: /p 名字或序号")
                    continue
                user = self.find_user(target)
                self.mode = "dm"
                self.target = str(user["id"]) if user else target
                print_line(f"当前会话: 私聊 {user['name'] if user else target}")
                continue

            group = command_arg(line, ["/g", "/群聊"])
            if group is not None:
                if not group:
                    print_line("用法: /g 群名")
                    continue
                self.mode = "group"
                self.target = group
                print_line(f"当前会话: 群聊 {group}")
                continue

            create_group_args = command_arg(line, ["/c", "/建群"])
            if create_group_args is not None:
                parts = create_group_args.split()
                if len(parts) < 2:
                    print_line("用法: /c 群名 成员1 成员2")
                    continue
                group = parts[0]
                members = parts[1:]
                self.send({"type": "group_create", "group": group, "members": members})
                self.mode = "group"
                self.target = group
                print_line(f"当前会话: 群聊 {group}")
                continue

            file_path = command_arg(line, ["/img", "/图片"])
            if file_path is not None:
                if not file_path:
                    print_line("用法: /img 文件路径")
                    continue
                self.send_current_file(file_path)
                continue

            new_name = command_arg(line, ["/n", "/改名"])
            if new_name is not None:
                if not new_name:
                    print_line("用法: /n 新名字")
                    continue
                self.send({"type": "rename", "name": new_name})
                continue

            if line in {"/t", "/提醒测试", "提醒测试"}:
                notify()
                print_line("已触发提醒测试。窗口在后台时效果更明显。")
                continue

            self.send_current_text(line)

        self.running = False
        try:
            self.sock.close()
        except OSError:
            pass


def run_client(host, port, name):
    sock = socket.create_connection((host, port), timeout=5)
    sock.settimeout(None)
    client = ChatClient(sock, name)
    send_json(sock, {"type": "hello", "name": name})
    thread = threading.Thread(target=client.listen, daemon=True)
    thread.start()
    client.command_loop()
