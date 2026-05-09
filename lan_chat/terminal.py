import os
import re
import shutil
import sys
import threading

from .config import DEFAULT_PROMPT

try:
    from rich import box
    from rich.align import Align
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except ImportError:
    box = None
    Align = None
    Console = None
    Panel = None
    Table = None
    Text = None

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.patch_stdout import patch_stdout
    from prompt_toolkit.styles import Style
except ImportError:
    PromptSession = None
    WordCompleter = None
    InMemoryHistory = None
    Style = None
    patch_stdout = None


io_lock = threading.RLock()
input_active = False
input_area_active = False
input_buffer = []
input_prompt = DEFAULT_PROMPT
output_row = 1
ui_style = "plain"
prompt_session = None
command_completer = None

RESET = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
RED = "\033[31m"
BLUE = "\033[34m"

STYLE_NAMES = {"plain", "fancy", "cyber"}
ANSI_PATTERN = re.compile(r"\033\[[0-9;]*[A-Za-z]")
rich_console = Console(force_terminal=True, color_system="truecolor", width=120, record=True) if Console else None


def terminal_size():
    size = shutil.get_terminal_size(fallback=(80, 24))
    return max(20, size.columns), max(3, size.lines)


def strip_ansi(text):
    return ANSI_PATTERN.sub("", text)


def set_ui_style(style):
    global ui_style
    if style not in STYLE_NAMES:
        raise ValueError(f"unknown UI style: {style}")
    ui_style = style


def get_ui_style():
    return ui_style


def toggle_ui_style():
    set_ui_style("cyber" if ui_style == "plain" else "plain")
    return ui_style


def rich_available():
    return rich_console is not None and Text is not None


def prompt_toolkit_available():
    return PromptSession is not None


def use_prompt_toolkit_input():
    return ui_style != "plain" and prompt_toolkit_available() and not sys.platform.startswith("win")


def rich_to_ansi(renderable):
    columns, _ = terminal_size()
    console = Console(force_terminal=True, color_system="truecolor", width=max(60, columns), record=True)
    console.begin_capture()
    console.print(renderable, end="")
    return console.end_capture()


def render_panel(title, body, border_style="bright_cyan", body_style="white", subtitle=""):
    if not rich_available() or Panel is None:
        return body
    columns, _ = terminal_size()
    width = min(max(54, columns - 4), 116)
    content = Text(str(body), style=body_style)
    return rich_to_ansi(
        Panel(
            content,
            title=title,
            subtitle=subtitle,
            border_style=border_style,
            box=box.DOUBLE_EDGE if box else None,
            width=width,
            padding=(0, 2),
        )
    ).rstrip()


def render_badge_line(label, body, badge_style, body_style="white"):
    if not rich_available():
        return body
    return rich_to_ansi(
        Text.assemble(
            (f" {label} ", badge_style),
            (" ", ""),
            (str(body), body_style),
        )
    ).rstrip()


def render_command_help_line(line):
    if not rich_available():
        return line

    stripped = line.strip()
    parts = re.split(r"\s{2,}", stripped, maxsplit=1)
    body = Text()
    if len(parts) == 2:
        command, description = parts
        body.append(command, style="bold #ffe66d")
        body.append("  ")
        body.append(description, style="#d7afff")
    else:
        body.append(stripped, style="bold #ffe66d")

    text = Text()
    text.append(" CMD ", style="bold black on #6cff8d")
    text.append(" ")
    text.append(body)
    return rich_to_ansi(text).rstrip()


def render_cyber_banner():
    if not rich_available() or Panel is None or Table is None or Align is None:
        return "\n".join(
            [
                "CHAT-HOLE // CYBERLINK",
                "Rich: on | prompt_toolkit: on",
                "Commands: /ui plain  /clear  /l  /p  /g  /img  /q",
            ]
        )

    grid = Table.grid(expand=True)
    grid.add_column(justify="center")
    grid.add_row(Text("CHAT-HOLE", style="bold #ff4fd8"))
    grid.add_row(Text("CYBERLINK TERMINAL", style="bold #34e8ff"))
    grid.add_row(Text("LAN MESSAGE CONSOLE // NEON PACKET STREAM", style="#6cff8d"))
    grid.add_row(Text(""))
    grid.add_row(
        Text.assemble(
            (" RICH ", "bold black on #34e8ff"),
            (" "),
            ("ON" if rich_available() else "OFF", "bold #34e8ff"),
            ("   "),
            (" PROMPT ", "bold black on #ff4fd8"),
            (" "),
            ("ON" if prompt_toolkit_available() else "OFF", "bold #ff4fd8"),
            ("   "),
            (" MODE ", "bold black on #6cff8d"),
            (" CYBER", "bold #6cff8d"),
        )
    )
    grid.add_row(Text("/ui plain  /clear  /l  /p <name>  /g <group>  /img <path>  /q", style="dim #d7afff"))

    return rich_to_ansi(
        Panel(
            Align.center(grid),
            border_style="#ff4fd8",
            box=box.HEAVY if box else None,
            padding=(1, 2),
        )
    ).rstrip()


def color(text, ansi):
    if ui_style == "plain":
        return text
    return f"{ansi}{text}{RESET}"


def format_prompt(prompt):
    if ui_style == "plain":
        return prompt
    if rich_available():
        label = prompt
        if prompt.startswith("["):
            end = prompt.find("]")
            if end != -1:
                label = prompt[: end + 1]
        return rich_to_ansi(
            Text.assemble(
                (" INJECT ", "bold black on #ff4fd8"),
                (" "),
                (label, "bold #34e8ff"),
                ("  >> ", "bold #6cff8d"),
            )
        )
    if prompt.startswith("["):
        end = prompt.find("]")
        if end != -1:
            return f"{BOLD}{CYAN}{prompt[:end + 1]}{RESET}{BOLD} > {RESET}"
    return f"{BOLD}{BLUE}> {RESET}"


def format_line(line):
    if ui_style == "plain" or not line:
        return line

    if rich_available():
        return format_rich_line(line)

    if line.startswith("[系统]"):
        return color(line, DIM)
    if line.startswith("[错误]"):
        return color(line, RED)
    if "->" in line:
        return color(line, GREEN)
    if line.startswith("["):
        return color(line, CYAN)
    if line.startswith("  /") or line.startswith("  \\"):
        return color(line, YELLOW)
    if line.startswith("命令"):
        return color(line, BOLD + MAGENTA)
    if line.startswith("*") or line.startswith("-"):
        return color(line, DIM)
    return line


def format_rich_line(line):
    if line.startswith("[系统]") or line.startswith("[SYS]"):
        return render_panel(" SYSTEM BROADCAST ", line, border_style="#34e8ff", body_style="#9ff7ff", subtitle="network state")
    if line.startswith("[错误]") or line.startswith("[ERR]"):
        return render_panel(" ERROR CHANNEL ", line, border_style="red", body_style="bold red", subtitle="attention required")
    if line.startswith("用法:"):
        return render_badge_line("USAGE", line, "bold black on #ffe66d", "bold #ffe66d")
    if line.startswith("  /") or line.startswith("  \\"):
        return render_command_help_line(line)
    if line.startswith("命令") or line.lower().startswith("commands"):
        return render_badge_line("HELP", line, "bold black on #ff4fd8", "bold #ffbaf2")
    if line.startswith("中文命令也可用"):
        return render_badge_line("ALIAS", line, "bold black on #d7afff", "#d7afff")
    if line.startswith("在线联系人"):
        return render_badge_line("CONTACTS", line, "bold black on #34e8ff", "bold #9ff7ff")
    if line.startswith("群聊"):
        return render_badge_line("GROUPS", line, "bold black on #ff4fd8", "bold #ffd6f6")
    if re.match(r"\s+\d+\.", line):
        return render_badge_line("USER", line.strip(), "bold black on #6cff8d", "bold #b8ffce")
    if line.startswith("  ") and "成员编号" in line:
        return render_badge_line("GROUP", line.strip(), "bold black on #ff4fd8", "#ffd6f6")
    if line.startswith("当前会话"):
        return render_badge_line("TARGET", line, "bold black on #34e8ff", "bold #9ff7ff")
    if line.startswith("终端界面样式") or line.startswith("Rich render") or line.startswith("prompt_toolkit input"):
        return render_badge_line("UI", line, "bold black on #ff4fd8", "#f7c7ff")
    if any(word in line for word in ("文件", "图片")):
        return render_badge_line("FILE", line, "bold black on #34e8ff", "#d6fbff")
    if any(word in line for word in ("还没有", "找不到", "不存在", "不是", "失败", "关闭", "错误")):
        return render_badge_line("WARN", line, "bold white on red", "bold #ffb3b3")
    if line.startswith("*") or line.startswith("-"):
        return rich_to_ansi(Text(line, style="bright_magenta dim"))
    if "->" in line:
        return render_badge_line("TX", line, "bold black on #6cff8d", "bold #b8ffce")
    if line.startswith("["):
        return render_badge_line("RX", line, "bold black on #34e8ff", "bold #d6fbff")
    return render_badge_line("LOG", line, "bold black on #2b2140", "#f5f3ff")


def clear_current_line():
    print("\r\033[2K", end="", flush=True)


def enable_input_area():
    global input_area_active, output_row
    _, rows = terminal_size()
    input_area_active = True
    output_row = min(output_row, rows - 1)
    print(f"\033[1;{rows - 1}r", end="", flush=True)


def restore_terminal_area():
    global input_area_active
    _, rows = terminal_size()
    input_area_active = False
    print(f"\033[r\033[{rows};1H\033[2K", end="", flush=True)


def restore_windows_console_input_mode():
    if not sys.platform.startswith("win"):
        return

    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return

    kernel32 = ctypes.windll.kernel32
    stdin_handle = kernel32.GetStdHandle(-10)
    invalid_handle = ctypes.c_void_p(-1).value
    if not stdin_handle or stdin_handle == invalid_handle:
        return

    mode = wintypes.DWORD()
    if not kernel32.GetConsoleMode(stdin_handle, ctypes.byref(mode)):
        return

    enable_processed_input = 0x0001
    enable_line_input = 0x0002
    enable_echo_input = 0x0004
    enable_virtual_terminal_input = 0x0200

    fixed_mode = mode.value
    fixed_mode |= enable_processed_input | enable_line_input | enable_echo_input
    fixed_mode &= ~enable_virtual_terminal_input
    kernel32.SetConsoleMode(stdin_handle, fixed_mode)


def clear_windows_console_screen_buffer():
    if not sys.platform.startswith("win"):
        return False

    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return False

    class Coord(ctypes.Structure):
        _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

    class SmallRect(ctypes.Structure):
        _fields_ = [
            ("Left", ctypes.c_short),
            ("Top", ctypes.c_short),
            ("Right", ctypes.c_short),
            ("Bottom", ctypes.c_short),
        ]

    class ConsoleScreenBufferInfo(ctypes.Structure):
        _fields_ = [
            ("dwSize", Coord),
            ("dwCursorPosition", Coord),
            ("wAttributes", wintypes.WORD),
            ("srWindow", SmallRect),
            ("dwMaximumWindowSize", Coord),
        ]

    kernel32 = ctypes.windll.kernel32
    stdout_handle = kernel32.GetStdHandle(-11)
    invalid_handle = ctypes.c_void_p(-1).value
    if not stdout_handle or stdout_handle == invalid_handle:
        return False

    info = ConsoleScreenBufferInfo()
    if not kernel32.GetConsoleScreenBufferInfo(stdout_handle, ctypes.byref(info)):
        return False

    cell_count = int(info.dwSize.X) * int(info.dwSize.Y)
    if cell_count <= 0:
        return False

    top_left = Coord(0, 0)
    written = wintypes.DWORD()
    if not kernel32.FillConsoleOutputCharacterW(stdout_handle, " ", cell_count, top_left, ctypes.byref(written)):
        return False
    if not kernel32.FillConsoleOutputAttribute(stdout_handle, info.wAttributes, cell_count, top_left, ctypes.byref(written)):
        return False
    kernel32.SetConsoleCursorPosition(stdout_handle, top_left)
    return True


def reset_terminal_for_exit():
    global input_active, input_area_active, input_buffer
    with io_lock:
        input_active = False
        input_area_active = False
        input_buffer = []
        _, rows = terminal_size()
        print(f"\033[0m\033[?25h\033[?2004l\033[r\033[{rows};1H\033[2K", end="", flush=True)
    restore_windows_console_input_mode()


def move_to_input_line():
    _, rows = terminal_size()
    print(f"\033[{rows};1H", end="", flush=True)


def move_to_bottom_prompt_line():
    _, rows = terminal_size()
    print(f"\033[r\033[{rows};1H\033[2K", end="", flush=True)


def clear_input_line():
    move_to_input_line()
    print("\033[2K", end="", flush=True)


def print_output_line(line):
    global output_row
    lines = str(line).splitlines() or [""]
    for output_line in lines:
        _, rows = terminal_size()
        output_bottom = rows - 1
        output_row = min(output_row, output_bottom)
        print(f"\033[1;{output_bottom}r", end="")
        print(f"\033[{output_row};1H\033[2K{output_line}", end="")
        if output_row < output_bottom:
            output_row += 1
        else:
            print("\n", end="")
    print("", end="", flush=True)


def clear_screen():
    global output_row
    with io_lock:
        clear_windows_console_screen_buffer()
        if input_area_active:
            _, rows = terminal_size()
            output_row = 1
            print(f"\033[r\033[H\033[2J\033[3J\033[H\033[1;{rows - 1}r\033[{rows};1H", end="", flush=True)
            redraw_input_line()
        else:
            output_row = 1
            print("\033[r\033[H\033[2J\033[3J\033[H", end="", flush=True)


def redraw_input_line():
    prompt = format_prompt(input_prompt)
    columns, _ = terminal_size()
    prompt_width = len(strip_ansi(prompt))
    max_text_width = max(1, columns - prompt_width - 1)
    text = "".join(input_buffer)[-max_text_width:]

    if input_area_active:
        clear_input_line()
    print(f"{prompt}{text}", end="", flush=True)


def refresh_input_prompt(prompt):
    global input_prompt
    with io_lock:
        if input_prompt == prompt:
            return False
        input_prompt = prompt
        if input_active:
            redraw_input_line()
            return True
    return False


def print_line(line=""):
    line = format_line(line)
    with io_lock:
        if input_area_active:
            print_output_line(line)
            redraw_input_line()
            return
        print(line)


def print_raw(block=""):
    with io_lock:
        if input_area_active:
            print_output_line(block)
            redraw_input_line()
            return
        print(block)


def print_cyber_banner():
    print_raw(render_cyber_banner())


def clear_terminal_alert():
    with io_lock:
        print("\033]9;4;0;0\a", end="", flush=True)


def notify():
    with io_lock:
        print("\a", end="", flush=True)
        print("\033]9;4;2;100\a", end="", flush=True)

    if not sys.platform.startswith("win"):
        return

    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return

    def ancestor_process_ids():
        class PROCESSENTRY32(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_void_p),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_char * 260),
            ]

        kernel32 = ctypes.windll.kernel32
        snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
        invalid_handle = ctypes.c_void_p(-1).value
        if snapshot == invalid_handle:
            return {os.getpid()}

        parent_by_pid = {}
        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)

        try:
            ok = kernel32.Process32First(snapshot, ctypes.byref(entry))
            while ok:
                parent_by_pid[int(entry.th32ProcessID)] = int(entry.th32ParentProcessID)
                ok = kernel32.Process32Next(snapshot, ctypes.byref(entry))
        finally:
            kernel32.CloseHandle(snapshot)

        pid = os.getpid()
        ancestors = {pid}
        while pid in parent_by_pid:
            pid = parent_by_pid[pid]
            if pid == 0 or pid in ancestors:
                break
            ancestors.add(pid)
        return ancestors

    def visible_windows_for_processes(process_ids):
        user32 = ctypes.windll.user32
        windows = []
        enum_proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def enum_proc(hwnd, _):
            if not user32.IsWindowVisible(hwnd):
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if int(pid.value) in process_ids:
                windows.append(hwnd)
            return True

        user32.EnumWindows(enum_proc_type(enum_proc), 0)
        return windows

    class FLASHWINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_uint),
            ("hwnd", ctypes.c_void_p),
            ("dwFlags", ctypes.c_uint),
            ("uCount", ctypes.c_uint),
            ("dwTimeout", ctypes.c_uint),
        ]

    windows = visible_windows_for_processes(ancestor_process_ids())
    console_hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if console_hwnd:
        windows.append(console_hwnd)

    seen = set()
    for hwnd in windows:
        if not hwnd or hwnd in seen:
            continue
        seen.add(hwnd)
        info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, 0x00000002 | 0x0000000C, 3, 0)
        ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))


def read_prompt_toolkit_line(prompt=DEFAULT_PROMPT):
    global prompt_session, command_completer
    if prompt_session is None:
        history = InMemoryHistory() if InMemoryHistory else None
        prompt_session = PromptSession(history=history)
    if command_completer is None and WordCompleter is not None:
        command_completer = WordCompleter(
            [
                "/ui",
                "/ui cyber",
                "/ui plain",
                "/clear",
                "/cls",
                "/l",
                "/p",
                "/g",
                "/c",
                "/img",
                "/n",
                "/h",
                "/q",
                "/美化",
                "/界面",
                "/清屏",
                "/联系人",
                "/私聊",
                "/群聊",
                "/图片",
            ],
            ignore_case=True,
        )

    style = Style.from_dict(
        {
            "prompt.brand": "bg:#ff4fd8 #05000a bold",
            "prompt.context": "#34e8ff bold",
            "prompt.arrow": "#6cff8d bold",
            "completion-menu.completion": "bg:#1b102f #d7afff",
            "completion-menu.completion.current": "bg:#34e8ff #05000a bold",
        }
    )

    label = prompt
    if prompt.startswith("["):
        end = prompt.find("]")
        if end != -1:
            label = prompt[: end + 1]
    message = [
        ("class:prompt.brand", " INJECT "),
        ("", " "),
        ("class:prompt.context", label),
        ("class:prompt.arrow", "  >> "),
    ]
    move_to_bottom_prompt_line()
    with patch_stdout(raw=True):
        return prompt_session.prompt(
            message,
            style=style,
            completer=command_completer,
            complete_while_typing=False,
        )


def read_chat_line(prompt=DEFAULT_PROMPT):
    if use_prompt_toolkit_input():
        return read_prompt_toolkit_line(prompt)

    if not sys.platform.startswith("win"):
        return input(prompt)

    import msvcrt

    global input_active, input_buffer, input_prompt
    with io_lock:
        enable_input_area()
        input_active = True
        input_buffer = []
        input_prompt = prompt
        redraw_input_line()

    while True:
        ch = msvcrt.getwch()
        clear_terminal_alert()

        if ch in ("\r", "\n"):
            with io_lock:
                line = "".join(input_buffer)
                input_active = False
                input_buffer = []
                clear_input_line()
            return line

        if ch == "\003":
            with io_lock:
                input_active = False
                input_buffer = []
                restore_terminal_area()
            raise KeyboardInterrupt

        if ch == "\b":
            with io_lock:
                if input_buffer:
                    input_buffer.pop()
                    redraw_input_line()
            continue

        if ch in ("\x00", "\xe0"):
            msvcrt.getwch()
            continue

        with io_lock:
            input_buffer.append(ch)
            redraw_input_line()
