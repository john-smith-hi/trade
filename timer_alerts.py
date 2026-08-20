# =============================================================================
# BÁO THỨC VÙNG GIÁ (trang setup/timer/)
# =============================================================================
#
# Đọc/ghi xml/timer.xml — danh sách báo thức đặt trên web, không giao dịch thật.
# File đổi thường xuyên khi poll giá nên api.py loại khỏi extra_files reloader
# (cùng kiểu day_trade_week.xml).
#
# =============================================================================

from pathlib import Path
import xml.etree.ElementTree as ET

XML_DIR = Path(__file__).with_name("xml")
ALERTS_FILE = XML_DIR / "timer.xml"
ALERTS_EXAMPLE_FILE = XML_DIR / "timer.example.xml"


def _xml_float(node, attr):
    text = (node.get(attr) or "").strip() if node is not None else ""
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _xml_bool_attr(node, attr, default=False):
    text = (node.get(attr) or "").strip().lower() if node is not None else ""
    if not text:
        return default
    return text in ("1", "true", "yes", "on")


def _xml_int_attr(node, attr):
    text = (node.get(attr) or "").strip() if node is not None else ""
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _fmt_num(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _to_float_or_none(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int_or_none(value):
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _pick(raw, *keys, default=""):
    for key in keys:
        if key in raw and raw[key] not in (None, ""):
            return raw[key]
    return default


def normalize_alert(raw):
    """Chuẩn hoá 1 báo thức từ JSON web (camelCase) hoặc từ XML (snake_case)."""
    if not isinstance(raw, dict):
        return None

    alert_id = str(_pick(raw, "id") or "").strip()
    account = str(_pick(raw, "account") or "").strip()
    symbol = str(_pick(raw, "symbol") or "").strip().upper()
    if not alert_id or not account or not symbol:
        return None

    zone_low = _to_float_or_none(_pick(raw, "zoneLow", "zone_low", default=None))
    zone_high = _to_float_or_none(_pick(raw, "zoneHigh", "zone_high", default=None))
    if zone_low is None and zone_high is None:
        return None
    if zone_low is None:
        zone_low = zone_high
    if zone_high is None:
        zone_high = zone_low

    enabled = raw.get("enabled")
    if enabled is None:
        enabled = True
    fired = bool(raw.get("fired"))
    primed = bool(raw.get("primed"))
    inside = bool(raw.get("inside"))

    return {
        "id": alert_id,
        "account": account,
        "symbol": symbol,
        "zoneLow": min(zone_low, zone_high),
        "zoneHigh": max(zone_low, zone_high),
        "note": str(_pick(raw, "note") or "").strip(),
        "enabled": bool(enabled),
        "fired": fired,
        "primed": primed,
        "inside": inside,
        "firedAt": _to_int_or_none(_pick(raw, "firedAt", "fired_at", default=None)),
        "lastBid": _to_float_or_none(_pick(raw, "lastBid", "last_bid", default=None)),
        "lastAsk": _to_float_or_none(_pick(raw, "lastAsk", "last_ask", default=None)),
        "lastOpen": _to_float_or_none(_pick(raw, "lastOpen", "last_open", default=None)),
        "lastHigh": _to_float_or_none(_pick(raw, "lastHigh", "last_high", default=None)),
        "lastLow": _to_float_or_none(_pick(raw, "lastLow", "last_low", default=None)),
        "lastClose": _to_float_or_none(_pick(raw, "lastClose", "last_close", default=None)),
        "lastCandleTime": str(_pick(raw, "lastCandleTime", "last_candle_time") or ""),
        "lastSymbol": str(_pick(raw, "lastSymbol", "last_symbol") or ""),
        "lastAt": _to_int_or_none(_pick(raw, "lastAt", "last_at", default=None)),
        "lastError": str(_pick(raw, "lastError", "last_error") or ""),
    }


def load_alerts():
    """Đọc danh sách báo thức từ timer.xml. Chưa có thì tạo từ example."""
    XML_DIR.mkdir(parents=True, exist_ok=True)
    if not ALERTS_FILE.exists():
        if ALERTS_EXAMPLE_FILE.exists():
            ALERTS_FILE.write_text(ALERTS_EXAMPLE_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            save_alerts([])

    try:
        root = ET.parse(ALERTS_FILE).getroot()
    except ET.ParseError as exc:
        raise RuntimeError(f"File timer.xml bị lỗi định dạng: {exc}")

    alerts = []
    for node in root.findall("alert"):
        last_node = node.find("last")
        raw = {
            "id": node.get("id", ""),
            "account": node.get("account", ""),
            "symbol": node.get("symbol", ""),
            "zone_low": node.get("zone_low", ""),
            "zone_high": node.get("zone_high", ""),
            "enabled": _xml_bool_attr(node, "enabled", True),
            "fired": _xml_bool_attr(node, "fired", False),
            "primed": _xml_bool_attr(node, "primed", False),
            "inside": _xml_bool_attr(node, "inside", False),
            "fired_at": _xml_int_attr(node, "fired_at"),
            "last_at": _xml_int_attr(node, "last_at"),
            "note": (node.findtext("note") or "").strip(),
            "last_bid": _xml_float(last_node, "bid"),
            "last_ask": _xml_float(last_node, "ask"),
            "last_open": _xml_float(last_node, "open"),
            "last_high": _xml_float(last_node, "high"),
            "last_low": _xml_float(last_node, "low"),
            "last_close": _xml_float(last_node, "close"),
            "last_candle_time": (last_node.get("candle_time") or "") if last_node is not None else "",
            "last_symbol": (last_node.get("symbol") or "") if last_node is not None else "",
            "last_error": (last_node.get("error") or "") if last_node is not None else "",
        }
        alert = normalize_alert(raw)
        if alert:
            alerts.append(alert)
    return alerts


def save_alerts(alerts):
    """Ghi danh sách báo thức ra timer.xml (camelCase như web)."""
    XML_DIR.mkdir(parents=True, exist_ok=True)
    root = ET.Element("timer_alerts")
    for raw in alerts or []:
        alert = normalize_alert(raw)
        if not alert:
            continue
        node = ET.SubElement(root, "alert", {
            "id": alert["id"],
            "account": alert["account"],
            "symbol": alert["symbol"],
            "zone_low": _fmt_num(alert["zoneLow"]),
            "zone_high": _fmt_num(alert["zoneHigh"]),
            "enabled": "true" if alert["enabled"] else "false",
            "fired": "true" if alert["fired"] else "false",
            "primed": "true" if alert["primed"] else "false",
            "inside": "true" if alert["inside"] else "false",
            "fired_at": _fmt_num(alert["firedAt"]),
            "last_at": _fmt_num(alert["lastAt"]),
        })
        ET.SubElement(node, "note").text = alert["note"]
        ET.SubElement(node, "last", {
            "bid": _fmt_num(alert["lastBid"]),
            "ask": _fmt_num(alert["lastAsk"]),
            "open": _fmt_num(alert["lastOpen"]),
            "high": _fmt_num(alert["lastHigh"]),
            "low": _fmt_num(alert["lastLow"]),
            "close": _fmt_num(alert["lastClose"]),
            "candle_time": alert["lastCandleTime"],
            "symbol": alert["lastSymbol"],
            "error": alert["lastError"],
        })

    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")
    tree.write(ALERTS_FILE, encoding="UTF-8", xml_declaration=True)


def candle_hits_zone(candle, alert):
    """Nến M1 chạm vùng nếu high/low giao với [zoneLow, zoneHigh]."""
    if not candle or not alert:
        return False
    low = min(float(alert["zoneLow"]), float(alert["zoneHigh"]))
    high = max(float(alert["zoneLow"]), float(alert["zoneHigh"]))
    c_high = candle.get("high")
    c_low = candle.get("low")
    if c_high is None or c_low is None:
        close = candle.get("close")
        if close is None:
            return False
        return low <= float(close) <= high
    return not (float(c_high) < low or float(c_low) > high)


def replace_alerts(raw_list):
    """Thay toàn bộ danh sách, bỏ mục không hợp lệ. Trả list đã chuẩn hoá."""
    if raw_list is None:
        alerts = []
    elif not isinstance(raw_list, list):
        raise ValueError("'alerts' phải là mảng")
    else:
        alerts = [a for a in (normalize_alert(item) for item in raw_list) if a]
    save_alerts(alerts)
    return alerts
