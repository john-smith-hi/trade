# =============================================================================
# GỬI CẢNH BÁO TELEGRAM (chỉ sendMessage, không nhận lệnh)
# =============================================================================
#
# Đọc xml/telegram.xml. Lỗi mạng / chưa cấu hình → nuốt, không làm fail lệnh MT5.
# Không in bot_token ra log hay nội dung tin.
#
# =============================================================================

from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json
import xml.etree.ElementTree as ET

XML_DIR = Path(__file__).with_name("xml")
CONFIG_FILE = XML_DIR / "telegram.xml"
CONFIG_EXAMPLE_FILE = XML_DIR / "telegram.example.xml"

_cached = None
_cached_mtime = None
_last_error = ""
SEND_TIMEOUT_SEC = 20


def _xml_text(root, tag):
    node = root.find(tag)
    if node is None or node.text is None:
        return ""
    return str(node.text).strip()


def _load_config():
    """Đọc telegram.xml; cache theo mtime để sửa file không cần restart process."""
    global _cached, _cached_mtime
    XML_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        if CONFIG_EXAMPLE_FILE.exists():
            CONFIG_FILE.write_text(CONFIG_EXAMPLE_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            return {"enabled": False, "bot_token": "", "chat_id": ""}

    try:
        mtime = CONFIG_FILE.stat().st_mtime
    except OSError:
        mtime = None
    if _cached is not None and mtime == _cached_mtime:
        return _cached

    try:
        root = ET.parse(CONFIG_FILE).getroot()
    except ET.ParseError:
        _cached = {"enabled": False, "bot_token": "", "chat_id": ""}
        _cached_mtime = mtime
        return _cached

    enabled_text = _xml_text(root, "enabled").lower()
    token = _xml_text(root, "bot_token")
    chat_id = _xml_text(root, "chat_id")
    enabled = enabled_text in ("1", "true", "yes", "on")
    if token in ("", "CHANGE_ME") or chat_id in ("", "CHANGE_ME"):
        enabled = False

    _cached = {"enabled": enabled, "bot_token": token, "chat_id": chat_id}
    _cached_mtime = mtime
    return _cached


def last_send_error():
    return _last_error


def config_status():
    """Trạng thái an toàn cho API test (không trả token)."""
    cfg = _load_config()
    token = cfg.get("bot_token") or ""
    return {
        "enabled": bool(cfg.get("enabled")),
        "configured": bool(token) and token != "CHANGE_ME" and bool(cfg.get("chat_id")) and cfg.get("chat_id") != "CHANGE_ME",
        "file": str(CONFIG_FILE),
    }


def format_pnl(value):
    if value is None:
        return ""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return ""
    if num > 0:
        return f"LÃI {num:.2f}"
    if num < 0:
        return f"LỖ {abs(num):.2f}"
    return "HÒA"


def format_now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def build_message(title, lines):
    parts = [str(title).strip()]
    for line in lines or []:
        text = str(line).strip()
        if text:
            parts.append(text)
    parts.append(format_now())
    return "\n".join(parts)


def _set_error(message):
    global _last_error
    _last_error = str(message or "").strip()


def _parse_telegram_error(raw):
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return (raw or "").strip()[:300]
    desc = str(data.get("description") or "").strip()
    code = data.get("error_code")
    if desc and code:
        return f"{code}: {desc}"
    return desc or (raw or "").strip()[:300]


def send_alert(text):
    """Gửi 1 tin. Trả True nếu Telegram nhận. Mọi lỗi → False, không raise."""
    global _last_error
    _last_error = ""
    body = str(text or "").strip()
    if not body:
        _set_error("Tin rỗng.")
        return False
    try:
        cfg = _load_config()
    except Exception as exc:
        _set_error(exc)
        return False
    if not cfg.get("enabled"):
        _set_error("Telegram đang tắt (enabled=false).")
        return False
    token = cfg.get("bot_token") or ""
    chat_id = cfg.get("chat_id") or ""
    if not token or token == "CHANGE_ME" or not chat_id or chat_id == "CHANGE_ME":
        _set_error("Thiếu bot_token hoặc chat_id.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urlencode({
        "chat_id": chat_id,
        "text": body[:4000],
        "disable_web_page_preview": "true",
    }).encode("utf-8")
    req = Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urlopen(req, timeout=SEND_TIMEOUT_SEC) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw) if raw else {}
        if data.get("ok"):
            return True
        _set_error(_parse_telegram_error(raw) or "Telegram trả ok=false.")
        return False
    except HTTPError as exc:
        raw = ""
        try:
            raw = exc.read().decode("utf-8", errors="replace")
        except Exception:
            raw = ""
        hint = _parse_telegram_error(raw) or f"HTTP {exc.code}"
        if "chat not found" in hint.lower():
            hint += (
                " — mở bot trên Telegram, bấm Start, gửi 1 tin, rồi lấy lại chat.id từ getUpdates."
            )
        _set_error(hint)
        return False
    except (URLError, TimeoutError, OSError) as exc:
        _set_error(f"Không gọi được api.telegram.org ({type(exc).__name__}: {exc})")
        return False
    except Exception as extra:
        _set_error(f"{type(extra).__name__}: {extra}")
        return False
