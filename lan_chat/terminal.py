import os
import sys
import threading

from .config import DEFAULT_PROMPT


io_lock = threading.RLock()
input_active = False
input_buffer = []
input_prompt = DEFAULT_PROMPT
ui_style = "plain"

RESET = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
RED = "\033[31m"
BLUE = "\033[34m"

STYLE_NAMES = {"plain", "fancy"}


def set_ui_style(style):
    global ui_style
    if style not in STYLE_NAMES:
        raise ValueError(f"unknown UI style: {style}")
    ui_style = style


def get_ui_style():
    return ui_style


def toggle_ui_style():
    set_ui_style("fancy" if ui_style == "plain" else "plain")
    return ui_style


def color(text, ansi):
    if ui_style == "plain":
        return text
    return f"{ansi}{text}{RESET}"


def format_prompt(prompt):
    if ui_style == "plain":
        return prompt
    if prompt.startswith("["):
        end = prompt.find("]")
        if end != -1:
            return f"{BOLD}{CYAN}{prompt[:end + 1]}{RESET}{BOLD} > {RESET}"
    return f"{BOLD}{BLUE}> {RESET}"


def format_line(line):
    if ui_style == "plain" or not line:
        return line

    if line.startswith("[绯荤粺]") or line.startswith("[系统]"):
        return color(line, DIM)
    if line.startswith("[閿欒") or line.startswith("[错误]"):
        return color(line, RED)
    if "->" in line:
        return color(line, GREEN)
    if line.startswith("[") and "][" in line:
        return color(line, CYAN)
    if line.startswith("  /") or line.startswith("  \\"):
        return color(line, YELLOW)
    if line.startswith("鍛戒护") or line.startswith("命令"):
        return color(line, BOLD + MAGENTA)
    if line.startswith("─") or line.startswith("-"):
        return color(line, DIM)
    return line


def clear_current_line():
    print("\r\033[2K", end="", flush=True)


def clear_screen():
    with io_lock:
        print("\033[2J\033[H", end="", flush=True)


def redraw_input_line():
    print(f"{format_prompt(input_prompt)}{''.join(input_buffer)}", end="", flush=True)


def print_line(line=""):
    line = format_line(line)
    with io_lock:
        if input_active:
            clear_current_line()
            print(line)
            redraw_input_line()
        else:
            print(line)


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


def read_chat_line(prompt=DEFAULT_PROMPT):
    if not sys.platform.startswith("win"):
        return input(prompt)

    import msvcrt

    global input_active, input_buffer, input_prompt
    with io_lock:
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
                clear_current_line()
            return line

        if ch == "\003":
            with io_lock:
                input_active = False
                input_buffer = []
                clear_current_line()
            raise KeyboardInterrupt

        if ch == "\b":
            with io_lock:
                if input_buffer:
                    input_buffer.pop()
                    clear_current_line()
                    redraw_input_line()
            continue

        if ch in ("\x00", "\xe0"):
            msvcrt.getwch()
            continue

        with io_lock:
            input_buffer.append(ch)
            print(ch, end="", flush=True)
