# =============================================================================
# JOB MODIFY-ALL-IF (giá chạm vùng → sửa SL/TP)
# =============================================================================
#
# Đọc/ghi xml/modify_if.xml. Watcher poll tick; file đổi thường xuyên nên
# api.py loại khỏi extra_files reloader (cùng kiểu timer.xml).
#
# =============================================================================

from pathlib import Path
import threading
import time
import xml.etree.ElementTree as ET

XML_DIR = Path(__file__).with_name("xml")
JOBS_FILE = XML_DIR / "modify_if.xml"
JOBS_EXAMPLE_FILE = XML_DIR / "modify_if.example.xml"

_file_lock = threading.Lock()


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


def resolve_zone(price=None, zone_low=None, zone_high=None):
    low = zone_low if zone_low is not None else price
    high = zone_high if zone_high is not None else price
    if low is None and high is None:
        raise RuntimeError("modify-all-if cần giá kích hoạt (--price hoặc vùng từ/đến)")
    if low is None:
        low = high
    if high is None:
        high = low
    low = float(low)
    high = float(high)
    if low <= 0 or high <= 0:
        raise RuntimeError("Vùng kích hoạt phải > 0")
    return min(low, high), max(low, high)


def normalize_job(raw):
    if not isinstance(raw, dict):
        return None

    job_id = str(_pick(raw, "id") or "").strip()
    account = str(_pick(raw, "account") or "").strip()
    symbol = str(_pick(raw, "symbol") or "").strip().upper()
    sl_price = _to_float_or_none(_pick(raw, "slPrice", "sl_price", default=None))
    if not job_id or not account or not symbol or sl_price is None or sl_price <= 0:
        return None

    try:
        zone_low, zone_high = resolve_zone(
            _to_float_or_none(_pick(raw, "price", default=None)),
            _to_float_or_none(_pick(raw, "zoneLow", "zone_low", default=None)),
            _to_float_or_none(_pick(raw, "zoneHigh", "zone_high", default=None)),
        )
    except RuntimeError:
        return None

    enabled = raw.get("enabled")
    if enabled is None:
        enabled = True

    tp_price = _to_float_or_none(_pick(raw, "tpPrice", "tp_price", default=None))
    if tp_price is not None and tp_price <= 0:
        tp_price = None

    return {
        "id": job_id,
        "account": account,
        "symbol": symbol,
        "zoneLow": zone_low,
        "zoneHigh": zone_high,
        "slPrice": sl_price,
        "tpPrice": tp_price,
        "enabled": bool(enabled),
        "fired": bool(raw.get("fired")),
        "primed": bool(raw.get("primed")),
        "firedAt": _to_int_or_none(_pick(raw, "firedAt", "fired_at", default=None)),
        "lastBid": _to_float_or_none(_pick(raw, "lastBid", "last_bid", default=None)),
        "lastAsk": _to_float_or_none(_pick(raw, "lastAsk", "last_ask", default=None)),
        "lastAt": _to_int_or_none(_pick(raw, "lastAt", "last_at", default=None)),
        "lastError": str(_pick(raw, "lastError", "last_error") or ""),
        "lastSymbol": str(_pick(raw, "lastSymbol", "last_symbol") or ""),
    }


def new_job_id():
    return f"m{int(time.time() * 1000)}"


def load_jobs():
    XML_DIR.mkdir(parents=True, exist_ok=True)
    if not JOBS_FILE.exists():
        if JOBS_EXAMPLE_FILE.exists():
            JOBS_FILE.write_text(JOBS_EXAMPLE_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            save_jobs([])

    try:
        root = ET.parse(JOBS_FILE).getroot()
    except ET.ParseError as exc:
        raise RuntimeError(f"File modify_if.xml bị lỗi định dạng: {exc}")

    jobs = []
    for node in root.findall("job"):
        last_node = node.find("last")
        raw = {
            "id": node.get("id", ""),
            "account": node.get("account", ""),
            "symbol": node.get("symbol", ""),
            "zone_low": node.get("zone_low", ""),
            "zone_high": node.get("zone_high", ""),
            "sl_price": node.get("sl_price", ""),
            "tp_price": node.get("tp_price", ""),
            "enabled": _xml_bool_attr(node, "enabled", True),
            "fired": _xml_bool_attr(node, "fired", False),
            "primed": _xml_bool_attr(node, "primed", False),
            "fired_at": _xml_int_attr(node, "fired_at"),
            "last_at": _xml_int_attr(node, "last_at"),
            "last_bid": _xml_float(last_node, "bid"),
            "last_ask": _xml_float(last_node, "ask"),
            "last_symbol": (last_node.get("symbol") or "") if last_node is not None else "",
            "last_error": (last_node.get("error") or "") if last_node is not None else "",
        }
        job = normalize_job(raw)
        if job:
            jobs.append(job)
    return jobs


def save_jobs(jobs):
    XML_DIR.mkdir(parents=True, exist_ok=True)
    root = ET.Element("modify_if_jobs")
    for raw in jobs or []:
        job = normalize_job(raw)
        if not job:
            continue
        node = ET.SubElement(root, "job", {
            "id": job["id"],
            "account": job["account"],
            "symbol": job["symbol"],
            "zone_low": _fmt_num(job["zoneLow"]),
            "zone_high": _fmt_num(job["zoneHigh"]),
            "sl_price": _fmt_num(job["slPrice"]),
            "tp_price": _fmt_num(job["tpPrice"]),
            "enabled": "true" if job["enabled"] else "false",
            "fired": "true" if job["fired"] else "false",
            "primed": "true" if job["primed"] else "false",
            "fired_at": _fmt_num(job["firedAt"]),
            "last_at": _fmt_num(job["lastAt"]),
        })
        ET.SubElement(node, "last", {
            "bid": _fmt_num(job["lastBid"]),
            "ask": _fmt_num(job["lastAsk"]),
            "symbol": job["lastSymbol"],
            "error": job["lastError"],
        })

    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")
    tree.write(JOBS_FILE, encoding="UTF-8", xml_declaration=True)


def waiting_jobs(account=None):
    jobs = []
    for job in load_jobs():
        if not job.get("enabled") or job.get("fired"):
            continue
        if account and job["account"] != account:
            continue
        jobs.append(job)
    return jobs


def upsert_waiting_job(job):
    """Một job chờ / account+symbol. Job mới thay job chờ cũ cùng cặp."""
    with _file_lock:
        jobs = load_jobs()
        next_jobs = []
        replaced = False
        for existing in jobs:
            same = (
                existing["account"] == job["account"]
                and existing["symbol"] == job["symbol"]
                and existing.get("enabled")
                and not existing.get("fired")
            )
            if same and not replaced:
                next_jobs.append(job)
                replaced = True
            elif not same:
                next_jobs.append(existing)
        if not replaced:
            next_jobs.insert(0, job)
        save_jobs(next_jobs)
        return replaced


def cancel_waiting_jobs(account):
    with _file_lock:
        jobs = load_jobs()
        kept = []
        cancelled = []
        for job in jobs:
            waiting = job["account"] == account and job.get("enabled") and not job.get("fired")
            if waiting:
                cancelled.append(job)
            else:
                kept.append(job)
        save_jobs(kept)
        return cancelled


def save_jobs_locked(jobs):
    with _file_lock:
        save_jobs(jobs)


def tick_hits_zone(job, bid, ask, prev_bid=None, prev_ask=None):
    """Chạm vùng: tick hiện tại nằm trong vùng, hoặc giá đã cắt qua giữa 2 lần poll."""
    low = float(job["zoneLow"])
    high = float(job["zoneHigh"])
    bid = float(bid)
    ask = float(ask)
    now_in = low <= bid <= high or low <= ask <= high
    if prev_bid is None or prev_ask is None:
        return now_in
    prev_in = low <= float(prev_bid) <= high or low <= float(prev_ask) <= high
    if now_in and not prev_in:
        return True
    if prev_in:
        return False
    path_lo = min(float(prev_bid), float(prev_ask), bid, ask)
    path_hi = max(float(prev_bid), float(prev_ask), bid, ask)
    return not (path_hi < low or path_lo > high)
