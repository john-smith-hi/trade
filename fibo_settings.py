# =============================================================================
# FIBO — đỉnh / đáy trang setup/fibo/
# =============================================================================
#
# Đọc/ghi xml/fibo.xml — không giao dịch, không MT5.
#
# =============================================================================

from datetime import datetime, timezone, timedelta
from math import isfinite
from pathlib import Path
import xml.etree.ElementTree as ET

XML_DIR = Path(__file__).with_name("xml")
SETTINGS_FILE = XML_DIR / "fibo.xml"
SETTINGS_EXAMPLE_FILE = XML_DIR / "fibo.example.xml"
VN_TZ = timezone(timedelta(hours=7))


def _now_iso():
    return datetime.now(VN_TZ).isoformat(timespec="seconds")


def _to_float_or_none(value):
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(number):
        return None
    return number


def _fmt_num(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def normalize_settings(raw):
    if not isinstance(raw, dict):
        raw = {}
    side = str(raw.get("side") or "sell").strip().lower()
    if side not in ("buy", "sell"):
        side = "sell"
    high = _to_float_or_none(raw.get("high"))
    low = _to_float_or_none(raw.get("low"))
    updated = str(raw.get("updatedAt") or raw.get("updated_at") or "").strip()
    return {
        "high": high,
        "low": low,
        "side": side,
        "updatedAt": updated or None,
    }


def load_settings():
    """Đọc đỉnh/đáy từ fibo.xml. Chưa có thì tạo từ example."""
    XML_DIR.mkdir(parents=True, exist_ok=True)
    if not SETTINGS_FILE.exists():
        if SETTINGS_EXAMPLE_FILE.exists():
            SETTINGS_FILE.write_text(
                SETTINGS_EXAMPLE_FILE.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        else:
            save_settings({"side": "sell"})

    try:
        root = ET.parse(SETTINGS_FILE).getroot()
    except ET.ParseError as exc:
        raise RuntimeError(f"File fibo.xml bị lỗi định dạng: {exc}")

    return normalize_settings({
        "high": root.get("high", ""),
        "low": root.get("low", ""),
        "side": root.get("side", "sell"),
        "updated_at": root.get("updated_at", ""),
    })


def save_settings(raw):
    """Ghi đỉnh/đáy ra fibo.xml. Trả dict đã chuẩn hoá."""
    XML_DIR.mkdir(parents=True, exist_ok=True)
    settings = normalize_settings(raw)
    updated_at = _now_iso()
    root = ET.Element("fibo_settings", {
        "high": _fmt_num(settings["high"]),
        "low": _fmt_num(settings["low"]),
        "side": settings["side"],
        "updated_at": updated_at,
    })
    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")
    tree.write(SETTINGS_FILE, encoding="UTF-8", xml_declaration=True)
    return {
        "high": settings["high"],
        "low": settings["low"],
        "side": settings["side"],
        "updatedAt": updated_at,
    }


def replace_settings(raw):
    """Thay toàn bộ cài đặt Fibo từ JSON web."""
    if raw is not None and not isinstance(raw, dict):
        raise ValueError("Body phải là object JSON")
    return save_settings(raw or {})
