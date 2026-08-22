# =============================================================================
# CHECKLIST VÀO LỆNH THEO TUẦN (day_trade_mindset.txt)
# =============================================================================
#
# Đọc/ghi xml/day_trade_week.xml — tách riêng khỏi mt5.py vì đây là công cụ
# chấm điểm setup thủ công (người dùng tự nhập), không giao dịch thật.
#
# Vòng đời tuần: Thứ 2 (week_start) -> Thứ 6 (week_end), giờ Việt Nam (UTC+7).
#   - Thứ 7 / CN              : tạo tuần T2–T6 kế tiếp (active) để nhập lịch trước
#                               (prev-week / D1 / H4). Chưa chấm điểm setup.
#   - Trong tuần (T2-T6)      : tuần "active", chấm điểm / giao dịch được cả Thứ 2.
#   - Monday High/Low         : chỉ nhập sau khi hết ngày Thứ 2.
#   - Đã qua Thứ 6            : tuần tự động "closed"; tuần mới đã mở từ Thứ 7.
#
# Quy tắc chấm điểm lấy từ day_trade_mindset.txt (các bước ①-⑩, bỏ qua ⑨ vì
# file gốc không có bước này). Bước ① không còn chặn giao dịch Thứ 2.
#
# =============================================================================

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

VN_TZ = timezone(timedelta(hours=7))

XML_DIR = Path(__file__).with_name("xml")
WEEK_FILE = XML_DIR / "day_trade_week.xml"
WEEK_EXAMPLE_FILE = XML_DIR / "day_trade_week.example.xml"

TRENDS = {"uptrend", "downtrend", "sideway"}
SIDES = {"buy", "sell"}
REACTIONS = {"rejection", "pinbar", "engulfing", "false_breakout"}

STEP_LABELS = {
    "1": "① Quan sát tuần — Monday High/Low chỉ nhập sau khi hết Thứ 2",
    "2": "② Xu hướng D1 chưa khớp hướng lệnh (hoặc sideway nhưng chưa chấp nhận trade biên)",
    "3": "③ Chưa xác định vùng giá quan trọng",
    "4": "④ Giá chưa về vùng quan trọng (đang đuổi giá / giữa sideway)",
    "5": "⑤ Chưa có phản ứng tại vùng giá (rejection/pin bar/engulfing/false breakout)",
    "7": "⑦ RR chưa đạt tối thiểu 1:2 (hoặc thiếu Entry/SL/TP hợp lệ)",
    "8": "⑧ Chưa xác nhận không có tin Tier-1 / có thể giữ lệnh qua tin mạnh",
    "10": "⑩ Chưa cam kết đặt đủ SL/TP và đóng lệnh trước cuối tuần nếu cần",
}


def now_vn():
    return datetime.now(VN_TZ)


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


def _fmt_num(value):
    if value is None:
        return ""
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


def week_bounds(day):
    """Trả (week_id, monday, friday, weekday) cho ngày `day`. weekday: 1=T2 .. 7=CN."""
    weekday = day.isoweekday()
    monday = day - timedelta(days=weekday - 1)
    friday = monday + timedelta(days=4)
    iso_year, iso_week, _ = day.isocalendar()
    week_id = f"{iso_year}-W{iso_week:02d}"
    return week_id, monday, friday, weekday


def planning_week_bounds(day):
    """Tuần đang lên lịch: T2–T6 chứa `day`; Thứ 7/CN → tuần T2–T6 kế tiếp."""
    weekday = day.isoweekday()
    if weekday >= 6:
        monday = day + timedelta(days=8 - weekday)
        friday = monday + timedelta(days=4)
        iso_year, iso_week, _ = monday.isocalendar()
        week_id = f"{iso_year}-W{iso_week:02d}"
        return week_id, monday, friday, weekday
    return week_bounds(day)


def week_session_started(week, now=None):
    """True khi đã tới ngày Thứ 2 của tuần đó (VN) — cho phép chấm điểm setup."""
    now = now or now_vn()
    try:
        monday = date.fromisoformat(week.get("week_start") or "")
    except ValueError:
        return False
    return now.date() >= monday


def monday_session_complete(week, now=None):
    """True khi đã qua ngày Thứ 2 của tuần đó (VN)."""
    now = now or now_vn()
    try:
        monday = date.fromisoformat(week.get("week_start") or "")
    except ValueError:
        return False
    return now.date() > monday


def _new_week(week_id, monday, friday):
    return {
        "id": week_id,
        "week_start": monday.isoformat(),
        "week_end": friday.isoformat(),
        "status": "active",
        "monday_high": None,
        "monday_low": None,
        "prev_week_high": None,
        "prev_week_low": None,
        "trend_d1": "",
        "trend_h4": "",
        "news_notes": "",
        "setups": [],
    }


def load_weeks():
    """Đọc danh sách tuần từ day_trade_week.xml.

    Nếu chưa tồn tại, tự tạo từ day_trade_week.example.xml (giống cách
    accounts.xml được tạo từ accounts.example.xml) để lần đầu chạy không lỗi.
    """
    XML_DIR.mkdir(parents=True, exist_ok=True)
    if not WEEK_FILE.exists():
        if WEEK_EXAMPLE_FILE.exists():
            WEEK_FILE.write_text(WEEK_EXAMPLE_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            save_weeks([])

    try:
        root = ET.parse(WEEK_FILE).getroot()
    except ET.ParseError as exc:
        raise RuntimeError(f"File day_trade_week.xml bị lỗi định dạng: {exc}")

    weeks = []
    for week_node in root.findall("week"):
        week_id = week_node.get("id", "")
        if not week_id:
            continue
        monday_node = week_node.find("monday_levels")
        prev_node = week_node.find("prev_week")
        week = {
            "id": week_id,
            "week_start": week_node.get("week_start", ""),
            "week_end": week_node.get("week_end", ""),
            "status": week_node.get("status", "active"),
            "monday_high": _xml_float(monday_node, "high"),
            "monday_low": _xml_float(monday_node, "low"),
            "prev_week_high": _xml_float(prev_node, "high"),
            "prev_week_low": _xml_float(prev_node, "low"),
            "trend_d1": (week_node.findtext("trend_d1") or "").strip(),
            "trend_h4": (week_node.findtext("trend_h4") or "").strip(),
            "news_notes": (week_node.findtext("news_notes") or "").strip(),
            "setups": [],
        }
        setups_node = week_node.find("setups")
        if setups_node is not None:
            for setup_node in setups_node.findall("setup"):
                prices_node = setup_node.find("prices")
                checklist_node = setup_node.find("checklist")
                checklist = {}
                if checklist_node is not None:
                    for step_node in checklist_node.findall("step"):
                        n = step_node.get("n", "")
                        if not n:
                            continue
                        checklist[n] = {
                            "ok": _xml_bool_attr(step_node, "ok"),
                            "rr": _xml_float(step_node, "rr"),
                        }
                fails_text = (setup_node.findtext("fails") or "").strip()
                week["setups"].append({
                    "id": setup_node.get("id", ""),
                    "created_at": setup_node.get("created_at", ""),
                    "symbol": setup_node.get("symbol", ""),
                    "side": setup_node.get("side", ""),
                    "trade_range": _xml_bool_attr(setup_node, "trade_range"),
                    "checklist": checklist,
                    "entry": _xml_float(prices_node, "entry"),
                    "sl": _xml_float(prices_node, "sl"),
                    "tp": _xml_float(prices_node, "tp"),
                    "rr": _xml_float(setup_node, "rr"),
                    "result": (setup_node.findtext("result") or "").strip(),
                    "fails": [f for f in fails_text.split("|") if f],
                })
        weeks.append(week)
    return weeks


def save_weeks(weeks):
    """Ghi danh sách tuần ra day_trade_week.xml."""
    XML_DIR.mkdir(parents=True, exist_ok=True)
    root = ET.Element("day_trade_weeks")
    for week in weeks:
        week_node = ET.SubElement(root, "week", {
            "id": str(week.get("id", "")),
            "week_start": str(week.get("week_start", "")),
            "week_end": str(week.get("week_end", "")),
            "status": str(week.get("status", "active")),
        })
        ET.SubElement(week_node, "monday_levels", {
            "high": _fmt_num(week.get("monday_high")),
            "low": _fmt_num(week.get("monday_low")),
        })
        ET.SubElement(week_node, "prev_week", {
            "high": _fmt_num(week.get("prev_week_high")),
            "low": _fmt_num(week.get("prev_week_low")),
        })
        ET.SubElement(week_node, "trend_d1").text = str(week.get("trend_d1", ""))
        ET.SubElement(week_node, "trend_h4").text = str(week.get("trend_h4", ""))
        ET.SubElement(week_node, "news_notes").text = str(week.get("news_notes", ""))

        setups_node = ET.SubElement(week_node, "setups")
        for setup in week.get("setups", []):
            setup_attrs = {
                "id": str(setup.get("id", "")),
                "created_at": str(setup.get("created_at", "")),
                "symbol": str(setup.get("symbol", "")),
                "side": str(setup.get("side", "")),
                "trade_range": "true" if setup.get("trade_range") else "false",
            }
            if setup.get("rr") is not None:
                setup_attrs["rr"] = _fmt_num(setup.get("rr"))
            setup_node = ET.SubElement(setups_node, "setup", setup_attrs)

            checklist_node = ET.SubElement(setup_node, "checklist")
            for n, info in sorted((setup.get("checklist") or {}).items(), key=lambda kv: int(kv[0])):
                step_attrs = {"n": str(n), "ok": "true" if info.get("ok") else "false"}
                if info.get("rr") is not None:
                    step_attrs["rr"] = _fmt_num(info.get("rr"))
                ET.SubElement(checklist_node, "step", step_attrs)

            ET.SubElement(setup_node, "prices", {
                "entry": _fmt_num(setup.get("entry")),
                "sl": _fmt_num(setup.get("sl")),
                "tp": _fmt_num(setup.get("tp")),
            })
            ET.SubElement(setup_node, "result").text = str(setup.get("result", ""))
            ET.SubElement(setup_node, "fails").text = "|".join(setup.get("fails") or [])

    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")
    tree.write(WEEK_FILE, encoding="UTF-8", xml_declaration=True)


def ensure_current_week(now=None):
    """Đóng tuần đã qua Thứ 6; từ Thứ 7 tạo tuần T2–T6 kế tiếp.

    Trả về (week, weekday 1..7, is_weekend).
    """
    now = now or now_vn()
    today = now.date()
    week_id, monday, friday, weekday = planning_week_bounds(today)
    is_weekend = weekday > 5

    weeks = load_weeks()
    changed = False
    for week in weeks:
        if week.get("status") == "active":
            try:
                w_end = date.fromisoformat(week.get("week_end", ""))
            except ValueError:
                continue
            if today > w_end:
                week["status"] = "closed"
                changed = True

    week = next((w for w in weeks if w["id"] == week_id), None)
    if week is None:
        week = _new_week(week_id, monday, friday)
        weeks.append(week)
        changed = True

    if changed:
        save_weeks(weeks)

    return week, weekday, is_weekend


def get_week(week_id):
    weeks = load_weeks()
    return next((w for w in weeks if w["id"] == week_id), None)


def update_week_observations(week_id, data):
    """Lưu quan sát ① (Monday/Previous-week H-L, ghi chú tin) + xu hướng ②."""
    weeks = load_weeks()
    week = next((w for w in weeks if w["id"] == week_id), None)
    if week is None:
        raise ValueError(f"Không tìm thấy tuần '{week_id}'")
    if week.get("status") != "active":
        raise ValueError("Tuần đã đóng, không thể sửa quan sát.")

    monday_ready = monday_session_complete(week)
    if monday_ready:
        if "monday_high" in data:
            week["monday_high"] = _to_float_or_none(data["monday_high"])
        if "monday_low" in data:
            week["monday_low"] = _to_float_or_none(data["monday_low"])
    elif data.get("monday_high") not in (None, "") or data.get("monday_low") not in (None, ""):
        raise ValueError("Chưa hết Thứ 2 — chưa nhập Monday High/Low. Previous Week vẫn lưu được.")
    if "prev_week_high" in data:
        week["prev_week_high"] = _to_float_or_none(data["prev_week_high"])
    if "prev_week_low" in data:
        week["prev_week_low"] = _to_float_or_none(data["prev_week_low"])
    if "trend_d1" in data:
        trend = (data["trend_d1"] or "").strip().lower()
        if trend and trend not in TRENDS:
            raise ValueError(f"trend_d1 phải là một trong {sorted(TRENDS)}")
        week["trend_d1"] = trend
    if "trend_h4" in data:
        trend = (data["trend_h4"] or "").strip().lower()
        if trend and trend not in TRENDS:
            raise ValueError(f"trend_h4 phải là một trong {sorted(TRENDS)}")
        week["trend_h4"] = trend
    if "news_notes" in data:
        week["news_notes"] = str(data["news_notes"] or "")

    save_weeks(weeks)
    return week


def evaluate_setup(week, payload, weekday):
    """Chấm điểm 1 setup theo checklist day_trade_mindset.txt (bước ①-⑩).

    Trả dict: side, checklist, entry, sl, tp, rr, result (pass/fail), fails[].
    """
    side = (payload.get("side") or "").strip().lower()
    if side not in SIDES:
        raise ValueError("side phải là buy hoặc sell")

    fails = []
    checklist = {}

    def mark(n, ok, rr=None, label=None):
        checklist[str(n)] = {"ok": bool(ok), "rr": rr}
        if not ok:
            fails.append(label or STEP_LABELS.get(str(n), f"Bước {n}"))

    # ① Quan sát tuần — không chặn giao dịch Thứ 2.
    mark(1, True)

    # ② Xu hướng D1 (lưu ở quan sát tuần) phải khớp hướng lệnh; sideway cần tick trade_range.
    trend = (week.get("trend_d1") or "").strip().lower()
    trade_range = bool(payload.get("trade_range"))
    if not trend:
        trend_ok = False
    elif trend == "uptrend":
        trend_ok = side == "buy"
    elif trend == "downtrend":
        trend_ok = side == "sell"
    else:  # sideway
        trend_ok = trade_range
    mark(2, trend_ok)

    mark(3, bool(payload.get("zone_confirmed")))
    mark(4, bool(payload.get("no_chase")))

    reactions = payload.get("reactions") or []
    if isinstance(reactions, str):
        reactions = [reactions]
    reactions = [r for r in reactions if r in REACTIONS]
    mark(5, len(reactions) > 0)

    expected_pattern = "HL (Higher Low)" if side == "buy" else "LH (Lower High)"
    mark(
        6,
        bool(payload.get("structure_break")),
        label=f"⑥ Chưa xác nhận break cấu trúc M15/H1 đúng chiều — cần {expected_pattern}",
    )

    entry = _to_float_or_none(payload.get("entry"))
    sl = _to_float_or_none(payload.get("sl"))
    tp = _to_float_or_none(payload.get("tp"))
    rr = None
    if entry is None or sl is None or tp is None:
        mark(7, False, label="⑦ Thiếu Entry/SL/TP để tính RR")
    else:
        if side == "buy":
            risk = entry - sl
            reward = tp - entry
        else:
            risk = sl - entry
            reward = entry - tp
        if risk <= 0 or reward <= 0:
            mark(
                7, False,
                label="⑦ SL/TP không hợp lệ theo hướng lệnh (BUY cần SL<Entry<TP, SELL cần TP<Entry<SL)",
            )
        else:
            rr = reward / risk
            mark(7, rr >= 2, rr=rr, label=f"⑦ RR={rr:.2f} chưa đạt tối thiểu 1:2")

    mark(8, bool(payload.get("news_ok")))
    mark(10, bool(payload.get("commit_sl_tp_close")))

    result = "pass" if not fails else "fail"
    return {
        "side": side,
        "checklist": checklist,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "rr": rr,
        "result": result,
        "fails": fails,
        "reactions": reactions,
    }


def _next_setup_id(week):
    existing = [int(s["id"]) for s in week.get("setups", []) if str(s.get("id", "")).isdigit()]
    return str(max(existing, default=0) + 1)


def add_setup(week_id, symbol, side, trade_range, evaluated, created_at=None):
    weeks = load_weeks()
    week = next((w for w in weeks if w["id"] == week_id), None)
    if week is None:
        raise ValueError(f"Không tìm thấy tuần '{week_id}'")
    if week.get("status") != "active":
        raise ValueError("Tuần đã đóng, không thể thêm setup mới.")
    if not week_session_started(week):
        raise ValueError("Chưa tới Thứ 2 — chưa chấm điểm setup. Previous Week / D1 / H4 vẫn nhập được.")

    setup = {
        "id": _next_setup_id(week),
        "created_at": created_at or now_vn().isoformat(timespec="seconds"),
        "symbol": str(symbol or "").strip().upper(),
        "side": side,
        "trade_range": bool(trade_range),
        "checklist": evaluated["checklist"],
        "entry": evaluated["entry"],
        "sl": evaluated["sl"],
        "tp": evaluated["tp"],
        "rr": evaluated["rr"],
        "result": evaluated["result"],
        "fails": evaluated["fails"],
    }
    week["setups"].append(setup)
    save_weeks(weeks)
    return week, setup


def update_setup(week_id, setup_id, symbol, side, trade_range, evaluated):
    weeks = load_weeks()
    week = next((w for w in weeks if w["id"] == week_id), None)
    if week is None:
        raise ValueError(f"Không tìm thấy tuần '{week_id}'")
    if week.get("status") != "active":
        raise ValueError("Tuần đã đóng, không thể sửa setup.")
    if not week_session_started(week):
        raise ValueError("Chưa tới Thứ 2 — chưa chấm điểm setup. Previous Week / D1 / H4 vẫn nhập được.")

    idx = next((i for i, s in enumerate(week["setups"]) if s["id"] == str(setup_id)), None)
    if idx is None:
        raise ValueError(f"Không tìm thấy setup '{setup_id}'")

    existing = week["setups"][idx]
    updated = {
        "id": existing["id"],
        "created_at": existing["created_at"],
        "symbol": str(symbol or "").strip().upper(),
        "side": side,
        "trade_range": bool(trade_range),
        "checklist": evaluated["checklist"],
        "entry": evaluated["entry"],
        "sl": evaluated["sl"],
        "tp": evaluated["tp"],
        "rr": evaluated["rr"],
        "result": evaluated["result"],
        "fails": evaluated["fails"],
    }
    week["setups"][idx] = updated
    save_weeks(weeks)
    return week, updated


def delete_setup(week_id, setup_id):
    weeks = load_weeks()
    week = next((w for w in weeks if w["id"] == week_id), None)
    if week is None:
        raise ValueError(f"Không tìm thấy tuần '{week_id}'")
    if week.get("status") != "active":
        raise ValueError("Tuần đã đóng, không thể xóa setup.")
    if not week_session_started(week):
        raise ValueError("Chưa tới Thứ 2 — chưa chấm điểm setup.")

    before = len(week["setups"])
    week["setups"] = [s for s in week["setups"] if s["id"] != str(setup_id)]
    if len(week["setups"]) == before:
        raise ValueError(f"Không tìm thấy setup '{setup_id}'")

    save_weeks(weeks)
    return week
