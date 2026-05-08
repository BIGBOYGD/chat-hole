import argparse
import socket
import sys

from .client import run_client
from .config import DEFAULT_DISCOVERY_TIMEOUT, DEFAULT_PORT
from .discovery import discover_servers
from .server import run_server
from .utils import local_ips


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    parser = argparse.ArgumentParser(description="局域网终端聊天")
    parser.add_argument("host", nargs="?", help="服务器 IP；开服时不用填")
    parser.add_argument("--server", action="store_true", help="启动聊天服务器")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="端口，默认 9000")
    parser.add_argument("--name", default=socket.gethostname(), help="你的名字")
    parser.add_argument(
        "--discover-timeout",
        type=float,
        default=DEFAULT_DISCOVERY_TIMEOUT,
        help="自动发现服务器的等待秒数，默认 3",
    )
    args = parser.parse_args()

    if args.server:
        try:
            run_server(args.port)
        except KeyboardInterrupt:
            print("\n服务器已关闭。")
        return

    host = args.host
    if not host:
        ips = local_ips()
        print(f"我的IP: {ips[0]}")
        print(f"正在自动发现局域网服务器，等待 {args.discover_timeout:g} 秒...")
        servers = discover_servers(args.port, args.discover_timeout)
        if len(servers) == 1:
            server = servers[0]
            host = server["host"]
            args.port = server["port"]
            print(f"已发现服务器: {server['name']} ({host}:{args.port})")
        elif len(servers) > 1:
            print("发现以下服务器:")
            for index, server in enumerate(servers, start=1):
                print(f"{index}. {server['name']}  {server['host']}:{server['port']}")
            choice = input("选择服务器编号，或直接回车取消: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(servers):
                server = servers[int(choice) - 1]
                host = server["host"]
                args.port = server["port"]
        else:
            print("没有发现服务器。先在一台电脑上运行: python .\\lan_chat.py --server")
            host = input("服务器IP(可直接回车退出): ").strip()
    if not host:
        print("没有服务器 IP，已退出。")
        return

    try:
        run_client(host, args.port, args.name)
    except OSError as exc:
        print(f"连接失败: {exc}")


if __name__ == "__main__":
    main()
