import os
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(
    os.environ.get(
        "CHAT_HOLE_DATA_DIR",
        os.environ.get("LAN_CHAT_DATA_DIR", Path.home() / ".chat-hole"),
    )
)
DEFAULT_PORT = 9000
DEFAULT_DISCOVERY_INTERVAL = 2.0
DEFAULT_DISCOVERY_TIMEOUT = 3.0
RECEIVED_DIR = DATA_DIR / "received_files"
DEFAULT_PROMPT = "> "
FILE_CHUNK_SIZE = 48 * 1024
