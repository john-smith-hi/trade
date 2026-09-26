"""
Lịch tin kinh tế mạnh (HIGH IMPACT) — phục vụ checklist ⑧ và bias GOLD/USD.

Cách dùng:
  python cal.py
  python cal.py --majors
  python cal.py --ccy USD,EUR,GBP
  python cal.py --impact med
  python cal.py --days 7
  python cal.py --week last
  python cal.py --from 2026-09-10 --to 2026-09-18
  python cal.py --source ff
  python cal.py --asset usd
  python cal.py -o out.txt

Nguồn:
  tv  = TradingView Economic Calendar (JSON, không cần key)
  ff  = Forex Factory weekly JSON (dự phòng / khi TV lỗi)
  auto = TV, lỗi thì FF
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Cấu hình
# ---------------------------------------------------------------------------

try:
    VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
except Exception:
    VN_TZ = timezone(timedelta(hours=7))
UTC = timezone.utc

TV_URL = "https://economic-calendar.tradingview.com/events"
FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

TV_HEADERS = {
    "Origin": "https://www.tradingview.com",
    "Referer": "https://www.tradingview.com/economic-calendar/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
}

FF_HEADERS = {
    "User-Agent": TV_HEADERS["User-Agent"],
    "Accept": "application/json",
}

# Quốc gia TradingView theo tiền tệ
CCY_COUNTRIES = {
    "USD": ["US"],
    "EUR": ["EU", "DE", "FR", "IT", "ES"],
    "GBP": ["GB"],
    "JPY": ["JP"],
    "AUD": ["AU"],
    "CAD": ["CA"],
    "NZD": ["NZ"],
    "CHF": ["CH"],
    "CNY": ["CN"],
}

MAJORS = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "NZD", "CHF", "CNY"]

# Sự kiện lạm phát: thấp hơn dự báo = Tốt (dovish)
INFLATION_KEYS = (
    "cpi", "ppi", "pce", "inflation", "price index", "lạm phát", "core pce",
    "producer price", "consumer price", "gdp price",
)

# Cao hơn dự báo = Tốt cho nền kinh tế nhưng inverted cho "xấu hơn"
INVERT_KEYS = (
    "unemployment", "jobless", "claims", "thất nghiệp", "trợ cấp",
)

# Sự kiện định tính (không chấm Tốt/Xấu)
QUALITATIVE_KEYS = (
    "press conference", "họp báo", "statement", "tuyên bố",
    "projections", "dot plot", "dự báo kinh tế", "speech", "speaks",
    "minutes", "biên bản", "testimony",
)

# Trọng số surprise → xác suất (GOLD/USD)
WEIGHT_RULES = (
    (("nfp", "nonfarm", "non farm", "payroll", "cpi", "inflation", "pce",
      "fomc", "fed interest", "federal funds", "rate decision", "lãi suất"), 3.0),
    (("gdp", "retail", "ppi", "employment", "unemployment", "michigan",
      "ism", "pmi", "claims", "consumer confidence", "tâm lý"), 2.0),
    (("housing", "permit", "home sales", "durable", "trade", "inventory",
      "nhà ở", "giấy phép", "bán nhà"), 1.0),
)

TITLE_VI = {
    "PPI MoM": "Chỉ số Giá Sản xuất PPI (Theo tháng)",
    "Core PPI MoM": "PPI Cốt lõi (Theo tháng)",
    "Existing Home Sales": "Doanh số Bán Nhà Đã qua Sử dụng (Hiện có)",
    "Core Inflation Rate MoM": "Tỷ lệ Lạm phát Cốt lõi (Theo tháng)",
    "Core Inflation Rate YoY": "Tỷ lệ Lạm phát Cốt lõi (Theo năm)",
    "Inflation Rate YoY": "Tỷ lệ Lạm phát (Theo năm)",
    "Inflation Rate MoM": "Tỷ lệ Lạm phát (Theo tháng)",
    "Michigan Consumer Sentiment Prel": "Chỉ số Tâm lý Người tiêu dùng Sơ bộ (ĐH Michigan)",
    "Michigan Consumer Sentiment": "Chỉ số Tâm lý Người tiêu dùng (ĐH Michigan)",
    "Retail Sales MoM": "Doanh số Bán lẻ Toàn quốc (Theo tháng)",
    "Retail Sales YoY": "Doanh số Bán lẻ (Theo năm)",
    "Core Retail Sales MoM": "Doanh số Bán lẻ Cốt lõi (Theo tháng)",
    "Fed Interest Rate Decision": "Quyết định Lãi suất của Fed",
    "Federal Funds Rate": "Quyết định Lãi suất của Fed",
    "FOMC Economic Projections": "Dự báo Kinh tế của FOMC (Biểu đồ Dot Plot)",
    "FOMC Statement": "Tuyên bố của FOMC",
    "Fed Press Conference": "Họp báo Quyết định Lãi suất của Fed",
    "Housing Starts": "Số lượng Nhà ở Mới Khởi công",
    "Building Permits Prel": "Số Giấy phép Xây dựng Mới (Sơ bộ)",
    "Building Permits": "Số Giấy phép Xây dựng Mới",
    "Non Farm Payrolls": "Bảng lương Phi Nông nghiệp (NFP)",
    "Nonfarm Payrolls": "Bảng lương Phi Nông nghiệp (NFP)",
    "Unemployment Rate": "Tỷ lệ Thất nghiệp",
    "Average Hourly Earnings MoM": "Thu nhập Trung bình Theo giờ (Theo tháng)",
    "Average Hourly Earnings YoY": "Thu nhập Trung bình Theo giờ (Theo năm)",
    "Initial Jobless Claims": "Số Đơn xin Trợ cấp Thất nghiệp Lần đầu",
    "Continuing Jobless Claims": "Số Đơn xin Trợ cấp Thất nghiệp Tiếp diễn",
    "GDP Growth Rate QoQ": "Tăng trưởng GDP (Theo quý)",
    "GDP Growth Rate QoQ Adv": "Tăng trưởng GDP Sơ bộ (Theo quý)",
    "GDP Growth Rate QoQ Final": "Tăng trưởng GDP Chính thức (Theo quý)",
    "Core PCE Price Index MoM": "PCE Cốt lõi (Theo tháng)",
    "Core PCE Price Index YoY": "PCE Cốt lõi (Theo năm)",
    "PCE Price Index MoM": "Chỉ số Giá PCE (Theo tháng)",
    "ISM Manufacturing PMI": "PMI Sản xuất ISM",
    "ISM Services PMI": "PMI Dịch vụ ISM",
    "CB Consumer Confidence": "Chỉ số Tín nhiệm Người tiêu dùng CB",
    "Durable Goods Orders MoM": "Đơn hàng Hàng bền (Theo tháng)",
    "New Home Sales": "Doanh số Nhà Mới",
    "ADP Employment Change": "Biến động Việc làm ADP",
    "JOLTs Job Openings": "Số Việc làm Trống JOLTs",
    "BoE Interest Rate Decision": "Quyết định Lãi suất của BoE",
    "BoJ Interest Rate Decision": "Quyết định Lãi suất của BoJ",
    "ECB Interest Rate Decision": "Quyết định Lãi suất của ECB",
    "RBA Interest Rate Decision": "Quyết định Lãi suất của RBA",
    "BoC Interest Rate Decision": "Quyết định Lãi suất của BoC",
    "SNB Interest Rate Decision": "Quyết định Lãi suất của SNB",
    "RBNZ Interest Rate Decision": "Quyết định Lãi suất của RBNZ",
    "Industrial Production YoY": "Sản xuất Công nghiệp (Theo năm)",
    "Industrial Production MoM": "Sản xuất Công nghiệp (Theo tháng)",
    "Balance of Trade": "Cán cân Thương mại",
    "ZEW Economic Sentiment Index": "Chỉ số Tín nhiệm Kinh tế ZEW",
    "Ifo Business Climate": "Chỉ số Khí hậu Kinh doanh Ifo",
    "Crude Oil Inventories": "Tồn kho Dầu thô",
    "Claimant Count Change": "Biến động Số người nhận Trợ cấp",
    "CPI m/m": "CPI (Theo tháng)",
    "CPI y/y": "CPI (Theo năm)",
    "Core CPI m/m": "CPI Cốt lõi (Theo tháng)",
    "Core CPI y/y": "CPI Cốt lõi (Theo năm)",
    "Median CPI y/y": "CPI Trung vị (Theo năm)",
    "Trimmed CPI y/y": "CPI Cắt đuôi (Theo năm)",
}

TITLE_PATTERNS = (
    (r"\bPrel\b", "Sơ bộ"),
    (r"\bAdv\b", "Sơ bộ"),
    (r"\bFinal\b", "Chính thức"),
    (r"\bMoM\b", "(Theo tháng)"),
    (r"\bm/m\b", "(Theo tháng)"),
    (r"\bYoY\b", "(Theo năm)"),
    (r"\by/y\b", "(Theo năm)"),
    (r"\bQoQ\b", "(Theo quý)"),
    (r"\bq/q\b", "(Theo quý)"),
    (r"\bCore\b", "Cốt lõi"),
    (r"Inflation Rate", "Tỷ lệ Lạm phát"),
    (r"Interest Rate Decision", "Quyết định Lãi suất"),
    (r"Retail Sales", "Doanh số Bán lẻ"),
    (r"Unemployment Rate", "Tỷ lệ Thất nghiệp"),
    (r"Building Permits", "Giấy phép Xây dựng"),
    (r"Housing Starts", "Nhà ở Mới Khởi công"),
    (r"Consumer Sentiment", "Tâm lý Người tiêu dùng"),
    (r"Consumer Confidence", "Tín nhiệm Người tiêu dùng"),
)


# ---------------------------------------------------------------------------
# ANSI
# ---------------------------------------------------------------------------

class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[96m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"
    MAGENTA = "\033[95m"


USE_COLOR = True


def paint(text: str, *codes: str) -> str:
    if not USE_COLOR or not codes:
        return text
    return f"{''.join(codes)}{text}{C.RESET}"


def enable_windows_ansi() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Thời gian / tuần
# ---------------------------------------------------------------------------

def now_vn() -> datetime:
    return datetime.now(VN_TZ)


def week_bounds(which: str, ref: datetime | None = None) -> tuple[datetime, datetime]:
    """Thứ 2 00:00 → Thứ 2 tuần sau 00:00 (giờ VN)."""
    ref = ref or now_vn()
    monday = ref.date() - timedelta(days=ref.weekday())
    if which == "last":
        monday -= timedelta(days=7)
    elif which == "next":
        monday += timedelta(days=7)
    start = datetime.combine(monday, datetime.min.time(), tzinfo=VN_TZ)
    return start, start + timedelta(days=7)


def parse_iso(value: str) -> datetime:
    text = (value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(VN_TZ)


def parse_day(value: str, end: bool = False) -> datetime:
    day = datetime.strptime(value.strip(), "%Y-%m-%d").date()
    if end:
        return datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=VN_TZ)
    return datetime.combine(day, datetime.min.time(), tzinfo=VN_TZ)


def to_utc_iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def http_json(url: str, headers: dict, timeout: int = 18) -> object:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Chuẩn hóa sự kiện
# ---------------------------------------------------------------------------

def _contains(text: str, keys: tuple[str, ...]) -> bool:
    t = (text or "").lower()
    return any(k in t for k in keys)


def translate_title(title: str) -> str:
    if not title:
        return ""
    if title in TITLE_VI:
        return TITLE_VI[title]
    out = title
    for pat, repl in TITLE_PATTERNS:
        out = re.sub(pat, repl, out, flags=re.I)
    out = re.sub(r"\s+", " ", out).strip()
    out = re.sub(r"\(\s+", "(", out)
    out = re.sub(r"\s+\)", ")", out)
    return out


def is_inflation(title: str) -> bool:
    return _contains(title, INFLATION_KEYS)


def is_inverted(title: str) -> bool:
    return _contains(title, INVERT_KEYS)


def is_qualitative(title: str) -> bool:
    return _contains(title, QUALITATIVE_KEYS)


def event_weight(title: str) -> float:
    t = (title or "").lower()
    if is_qualitative(title):
        return 0.0
    for keys, w in WEIGHT_RULES:
        if any(k in t for k in keys):
            return w
    return 1.0


def fmt_num(value, unit: str | None = None, scale: str | None = None) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, str):
        text = value.strip()
        return text if text else "-"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(num - round(num)) < 1e-9 and abs(num) >= 1:
        s = str(int(round(num)))
    else:
        s = f"{num:.3f}".rstrip("0").rstrip(".")
    parts = [s]
    if scale:
        parts.append(str(scale))
    if unit:
        parts.append(str(unit))
    return " ".join(parts)


def parse_ff_value(raw: str | None) -> tuple[float | None, str | None, str | None, str]:
    """Trả (số, unit, scale, chuỗi hiển thị)."""
    text = (raw or "").strip()
    if not text or text in {"-", "—"}:
        return None, None, None, "-"
    m = re.match(r"^([+-]?\d+(?:\.\d+)?)(.*)$", text.replace(",", ""))
    if not m:
        return None, None, None, text
    num = float(m.group(1))
    suf = m.group(2).strip()
    unit = "%" if "%" in suf else None
    scale = None
    up = suf.upper()
    if re.search(r"\bK\b", up) or up.endswith("K"):
        scale = "K"
    elif re.search(r"\bB\b", up) or up.endswith("B"):
        scale = "B"
    elif re.search(r"\bM\b", up) or up.endswith("M"):
        scale = "M"
    return num, unit, scale, fmt_num(num, unit, scale)


def classify(actual, forecast, title: str) -> str | None:
    """Tốt / Xấu / Đạt / None (chưa ra hoặc không so được)."""
    if actual is None or forecast is None:
        return None
    try:
        a, f = float(actual), float(forecast)
    except (TypeError, ValueError):
        return None
    if abs(a - f) < 1e-9:
        return "Đạt"
    better_if_lower = is_inflation(title) or is_inverted(title)
    if better_if_lower:
        return "Tốt" if a < f else "Xấu"
    return "Tốt" if a > f else "Xấu"


def usd_surprise_sign(actual, forecast, title: str) -> int:
    """
    +1 = USD hawkish (GOLD bearish), -1 = USD dovish (GOLD bullish), 0 = hòa.
    """
    if actual is None or forecast is None or is_qualitative(title):
        return 0
    try:
        a, f = float(actual), float(forecast)
    except (TypeError, ValueError):
        return 0
    if abs(a - f) < 1e-9:
        return 0
    higher_is_hawkish = not is_inverted(title)
    # Lạm phát cao hơn dự báo = hawkish USD
    if a > f:
        return 1 if higher_is_hawkish else -1
    return -1 if higher_is_hawkish else 1


def normalize_event(
    *,
    title: str,
    currency: str,
    when: datetime,
    actual,
    forecast,
    previous,
    unit: str | None,
    scale: str | None,
    importance: str,
    source: str,
    actual_disp: str | None = None,
    forecast_disp: str | None = None,
    previous_disp: str | None = None,
) -> dict:
    title_vi = translate_title(title)
    verdict = classify(actual, forecast, f"{title} {title_vi}")
    return {
        "title": title,
        "title_vi": title_vi,
        "currency": (currency or "").upper() or "USD",
        "when": when,
        "actual": actual,
        "forecast": forecast,
        "previous": previous,
        "unit": unit,
        "scale": scale,
        "actual_s": actual_disp or fmt_num(actual, unit, scale),
        "forecast_s": forecast_disp or fmt_num(forecast, unit, scale),
        "previous_s": previous_disp or fmt_num(previous, unit, scale),
        "importance": importance,
        "source": source,
        "verdict": verdict,
        "qualitative": is_qualitative(f"{title} {title_vi}"),
        "weight": event_weight(f"{title} {title_vi}"),
    }


# ---------------------------------------------------------------------------
# Nguồn
# ---------------------------------------------------------------------------

def fetch_tradingview(start: datetime, end: datetime, currencies: list[str]) -> list[dict]:
    countries: list[str] = []
    for ccy in currencies:
        countries.extend(CCY_COUNTRIES.get(ccy.upper(), []))
    countries = list(dict.fromkeys(countries)) or ["US"]
    params = {
        "from": to_utc_iso(start),
        "to": to_utc_iso(end - timedelta(seconds=1)),
        "countries": ",".join(countries),
    }
    url = f"{TV_URL}?{urllib.parse.urlencode(params)}"
    data = http_json(url, TV_HEADERS)
    rows = data.get("result", []) if isinstance(data, dict) else data
    events = []
    want = {c.upper() for c in currencies}
    for row in rows or []:
        ccy = (row.get("currency") or "").upper()
        country = (row.get("country") or "").upper()
        if ccy not in want:
            # EU sự kiện đôi khi currency EUR nhưng filter theo country
            mapped = None
            for code, nations in CCY_COUNTRIES.items():
                if country in nations:
                    mapped = code
                    break
            if mapped not in want:
                continue
            ccy = mapped or ccy
        try:
            when = parse_iso(row.get("date") or "")
        except (TypeError, ValueError):
            continue
        if when < start or when >= end:
            continue
        imp = row.get("importance")
        importance = "high" if imp in (1, "1", 2, 3) else ("medium" if imp in (0, "0") else "low")
        unit = row.get("unit") or None
        scale = row.get("scale") or None
        events.append(
            normalize_event(
                title=row.get("title") or row.get("indicator") or "",
                currency=ccy,
                when=when,
                actual=row.get("actual"),
                forecast=row.get("forecast"),
                previous=row.get("previous"),
                unit=unit,
                scale=scale,
                importance=importance,
                source="TradingView",
            )
        )
    return events


def fetch_forexfactory(start: datetime, end: datetime, currencies: list[str]) -> list[dict]:
    rows = http_json(FF_URL, FF_HEADERS)
    if not isinstance(rows, list):
        return []
    want = {c.upper() for c in currencies}
    events = []
    for row in rows:
        ccy = (row.get("country") or row.get("currency") or "").upper()
        if ccy == "ALL" or ccy not in want:
            continue
        try:
            when = parse_iso(row.get("date") or "")
        except (TypeError, ValueError):
            continue
        if when < start or when >= end:
            continue
        impact = (row.get("impact") or "").strip().lower()
        if impact in {"high", "red"}:
            importance = "high"
        elif impact in {"medium", "med", "orange"}:
            importance = "medium"
        elif impact in {"holiday", "none"}:
            continue
        else:
            importance = "low"
        a, au, ascl, ad = parse_ff_value(row.get("actual"))
        f, fu, fscl, fd = parse_ff_value(row.get("forecast"))
        p, pu, pscl, pd = parse_ff_value(row.get("previous"))
        unit = au or fu or pu
        scale = ascl or fscl or pscl
        events.append(
            normalize_event(
                title=row.get("title") or "",
                currency=ccy,
                when=when,
                actual=a,
                forecast=f,
                previous=p,
                unit=unit,
                scale=scale,
                importance=importance,
                source="Forex Factory",
                actual_disp=ad,
                forecast_disp=fd,
                previous_disp=pd,
            )
        )
    return events


def load_events(source: str, start: datetime, end: datetime, currencies: list[str]) -> tuple[list[dict], str]:
    errors = []
    if source in ("auto", "tv"):
        try:
            ev = fetch_tradingview(start, end, currencies)
            return ev, "TradingView"
        except Exception as exc:
            errors.append(f"TradingView: {exc}")
            if source == "tv":
                raise RuntimeError("; ".join(errors)) from exc
    try:
        ev = fetch_forexfactory(start, end, currencies)
        return ev, "Forex Factory"
    except Exception as exc:
        errors.append(f"Forex Factory: {exc}")
        raise RuntimeError("Không lấy được lịch tin. " + " | ".join(errors)) from exc


# ---------------------------------------------------------------------------
# Xác suất
# ---------------------------------------------------------------------------

def gold_usd_bias(events: list[dict], now: datetime) -> dict:
    """
    Surprise tin HIGH đã ra → xác suất ủng hộ GOLD BUY vs SELL.
    GOLD thường nghịch USD: hawkish USD → GOLD SELL.
    """
    scored = []
    for ev in events:
        if ev["importance"] != "high":
            continue
        if ev["when"] > now:
            continue
        if ev["qualitative"] or ev["weight"] <= 0:
            continue
        if ev["actual"] is None or ev["forecast"] is None:
            continue
        sign = usd_surprise_sign(ev["actual"], ev["forecast"], f"{ev['title']} {ev['title_vi']}")
        if sign == 0:
            continue
        w = ev["weight"]
        # USD tin nặng hơn cho GOLD
        if ev["currency"] == "USD":
            w *= 1.35
        scored.append((ev, sign, w))

    hawk = sum(w for _, s, w in scored if s > 0)
    dove = sum(w for _, s, w in scored if s < 0)
    total = hawk + dove

    upcoming_high = [e for e in events if e["importance"] == "high" and e["when"] > now]
    n_scored = len(scored)

    if total <= 0:
        gold_buy = 50.0
        gold_sell = 50.0
    else:
        # dove (USD yếu) ủng hộ GOLD BUY
        gold_buy = 100.0 * dove / total
        gold_sell = 100.0 * hawk / total
        # co về 50 khi ít mẫu
        shrink = 0.55 + 0.45 * min(1.0, n_scored / 4.0)
        gold_buy = 50.0 + (gold_buy - 50.0) * shrink
        gold_sell = 100.0 - gold_buy

    conf = 0.28 + 0.12 * min(n_scored, 5) - 0.08 * min(len(upcoming_high), 4)
    conf = max(0.18, min(0.82, conf))
    if n_scored == 0:
        conf = 0.18
        label = "Thấp (chưa có surprise số liệu)"
    elif conf < 0.4:
        label = "Thấp"
    elif conf < 0.6:
        label = "Trung bình"
    else:
        label = "Khá"

    reasons = []
    for ev, sign, w in sorted(scored, key=lambda x: -x[2])[:5]:
        delta = ev["actual"] - ev["forecast"]
        side = "USD mạnh / GOLD↓" if sign > 0 else "USD yếu / GOLD↑"
        reasons.append(
            f"{ev['currency']} {ev['title_vi']}: {ev['actual_s']} vs {ev['forecast_s']} "
            f"({delta:+.3g}) → {side}"
        )
    if not reasons:
        reasons.append("Chưa có tin HIGH nào lệch dự báo trong khoảng đang xem.")
    if upcoming_high:
        nxt = upcoming_high[0]
        delta = nxt["when"] - now
        reasons.append(
            f"Rủi ro sự kiện: còn {len(upcoming_high)} tin HIGH phía trước "
            f"(sắp nhất {nxt['title_vi']} lúc {nxt['when'].strftime('%H:%M %d-%m')}, còn {_ago(delta)})."
        )

    lean = "Trung lập"
    if gold_buy >= 58:
        lean = "Ủng hộ GOLD BUY (USD yếu / risk-on từ tin)"
    elif gold_sell >= 58:
        lean = "Ủng hộ GOLD SELL (USD mạnh / hawkish từ tin)"

    return {
        "gold_buy": gold_buy,
        "gold_sell": gold_sell,
        "usd_strong": gold_sell,
        "usd_weak": gold_buy,
        "confidence": conf,
        "confidence_label": label,
        "n_scored": n_scored,
        "n_upcoming": len(upcoming_high),
        "lean": lean,
        "reasons": reasons,
        "next_event": upcoming_high[0] if upcoming_high else None,
    }


def _ago(delta: timedelta) -> str:
    sec = int(delta.total_seconds())
    if sec < 0:
        return "đã qua"
    h, rem = divmod(sec, 3600)
    m = rem // 60
    if h >= 48:
        return f"{h // 24} ngày {h % 24} giờ"
    if h > 0:
        return f"{h} giờ {m} phút"
    return f"{m} phút"


def bar(pct: float, width: int = 16) -> str:
    filled = int(round(max(0.0, min(100.0, pct)) / 100.0 * width))
    return "█" * filled + "░" * (width - filled)


# ---------------------------------------------------------------------------
# Hiển thị
# ---------------------------------------------------------------------------

def pad(text: str, width: int, align: str = "left") -> str:
    text = text or ""
    if len(text) > width:
        text = text[: max(0, width - 1)] + "…"
    if align == "right":
        return text.rjust(width)
    return text.ljust(width)


def visible_len(text: str) -> int:
    return len(re.sub(r"\033\[[0-9;]*m", "", text))


def pad_ansi(text: str, width: int, align: str = "left") -> str:
    vis = visible_len(text)
    gap = max(0, width - vis)
    if align == "right":
        return " " * gap + text
    return text + " " * gap


def print_report(events: list[dict], src: str, start: datetime, end: datetime, impact: str, asset: str) -> None:
    now = now_vn()
    high = [e for e in events if e["importance"] == "high"]
    if impact == "med":
        show = [e for e in events if e["importance"] in ("high", "medium")]
        impact_label = "HIGH + MEDIUM"
    elif impact == "all":
        show = events
        impact_label = "ALL"
    else:
        show = high
        impact_label = "HIGH IMPACT"

    show = sorted(show, key=lambda e: e["when"])
    released = [e for e in show if e["when"] <= now]
    upcoming = [e for e in show if e["when"] > now]

    good = sum(1 for e in released if e["verdict"] == "Tốt")
    bad = sum(1 for e in released if e["verdict"] == "Xấu")
    met = sum(1 for e in released if e["verdict"] == "Đạt")

    print(paint("TÓM TẮT SỰ KIỆN QUAN TRỌNG ", C.BOLD, C.CYAN) + paint(f"({impact_label})", C.CYAN))
    high_word = "High" if impact == "high" else impact_label
    print(f"{'Tổng sự kiện ' + high_word:<22} {paint(str(len(show)), C.YELLOW)} sự kiện")
    print(f"{'Sắp diễn ra':<22} {paint(str(len(upcoming)), C.YELLOW)} sự kiện")
    mix = (
        f"{paint(str(good) + ' Tốt', C.GREEN)} | "
        f"{paint(str(bad) + ' Xấu', C.RED)} | "
        f"{paint(str(met) + ' Đạt', C.WHITE)}"
    )
    print(f"{'Đã công bố':<22} {paint(str(len(released)), C.CYAN)} sự kiện ({mix})")
    print()

    title_w = 52
    num_w = 10
    print(paint("DANH SÁCH SỰ KIỆN TÁC ĐỘNG MẠNH", C.BOLD, C.CYAN))
    header = (
        f"{pad('THỜI GIAN', 14)} {pad('TIỀN', 4)} {pad('SỰ KIỆN KINH TẾ (' + impact_label.split()[0] + ')', title_w)} "
        f"{pad('THỰC TẾ', num_w, 'right')} {pad('DỰ BÁO', num_w, 'right')} {pad('KỲ TRƯỚC', num_w, 'right')}"
    )
    print(paint(header, C.GRAY))

    today = now.date()
    for ev in show:
        t = ev["when"].strftime("%H:%M %d-%m")
        is_up = ev["when"] > now
        is_today = ev["when"].date() == today
        time_s = t
        if is_up or is_today:
            time_s = paint(t, C.YELLOW)
        time_s = pad_ansi(time_s, 14)

        ccy = pad(ev["currency"], 4)
        name = pad(ev["title_vi"] or ev["title"], title_w)

        actual_s = pad(ev["actual_s"], num_w, "right")
        if ev["verdict"] == "Tốt":
            actual_s = pad_ansi(paint(ev["actual_s"], C.GREEN), num_w, "right")
        elif ev["verdict"] == "Xấu":
            actual_s = pad_ansi(paint(ev["actual_s"], C.RED), num_w, "right")
        elif is_up:
            actual_s = pad_ansi(paint(ev["actual_s"], C.YELLOW), num_w, "right")

        fc = ev["forecast_s"]
        prev = ev["previous_s"]
        if is_up:
            fc = paint(fc, C.YELLOW)
            prev = paint(prev, C.YELLOW)
        fc_s = pad_ansi(fc, num_w, "right")
        prev_s = pad_ansi(prev, num_w, "right")
        print(f"{time_s} {ccy} {name} {actual_s} {fc_s} {prev_s}")

    if not show:
        print(paint("  (Không có sự kiện trong bộ lọc)", C.DIM))

    print()
    bias = gold_usd_bias(events, now)
    print(paint("TỶ LỆ XÁC SUẤT ỦNG HỘ ", C.BOLD, C.CYAN) + paint("(surprise tin HIGH đã ra)", C.GRAY))
    if asset == "usd":
        print(f"  USD mạnh   {bias['usd_strong']:5.1f}%  {paint(bar(bias['usd_strong']), C.RED)}")
        print(f"  USD yếu    {bias['usd_weak']:5.1f}%  {paint(bar(bias['usd_weak']), C.GREEN)}")
    else:
        print(f"  GOLD BUY   {bias['gold_buy']:5.1f}%  {paint(bar(bias['gold_buy']), C.GREEN)}")
        print(f"  GOLD SELL  {bias['gold_sell']:5.1f}%  {paint(bar(bias['gold_sell']), C.RED)}")
    print(f"  Kết luận   {paint(bias['lean'], C.BOLD, C.YELLOW)}")
    print(f"  Độ tin cậy {bias['confidence_label']} ({bias['n_scored']} surprise / {bias['n_upcoming']} tin HIGH còn lại)")
    print(paint("  Gợi ý:", C.GRAY))
    for line in bias["reasons"]:
        print(f"    • {line}")

    nxt = bias["next_event"]
    if nxt:
        mins = (nxt["when"] - now).total_seconds() / 60.0
        warn = paint("  Checklist ⑧: KHÔNG giữ lệnh qua tin mạnh.", C.RED, C.BOLD)
        if mins <= 90:
            print(warn + paint(f" Còn {max(0, int(mins))} phút tới {nxt['title_vi']}.", C.RED))
        else:
            print(paint("  Checklist ⑧: đứng ngoài ±30–60 phút quanh tin HIGH / FOMC.", C.GRAY))

    print()
    print(
        paint("Chú thích: ", C.GRAY)
        + paint("■ Tốt", C.GREEN) + paint(" (Vượt kỳ vọng / Lạm phát giảm)  ", C.GRAY)
        + paint("■ Xấu", C.RED) + paint(" (Hụt kỳ vọng / Lạm phát tăng)  ", C.GRAY)
        + paint("■ Hôm nay / Sắp ra", C.YELLOW)
    )
    stamp = now.strftime("%H:%M:%S %d/%m/%Y")
    rng = f"{start.strftime('%d/%m')}–{(end - timedelta(seconds=1)).strftime('%d/%m/%Y')}"
    print(paint(f"Cập nhật lúc: {stamp}  |  Khoảng: {rng}  |  Nguồn: {src}", C.GRAY))


def events_to_json(events: list[dict], src: str, bias: dict) -> dict:
    def pack(ev: dict) -> dict:
        return {
            "time_vn": ev["when"].strftime("%Y-%m-%d %H:%M"),
            "currency": ev["currency"],
            "title": ev["title"],
            "title_vi": ev["title_vi"],
            "actual": ev["actual_s"],
            "forecast": ev["forecast_s"],
            "previous": ev["previous_s"],
            "importance": ev["importance"],
            "verdict": ev["verdict"],
            "source": ev["source"],
        }
    return {
        "source": src,
        "updated_vn": now_vn().strftime("%Y-%m-%d %H:%M:%S"),
        "events": [pack(e) for e in events],
        "bias": {
            "gold_buy": round(bias["gold_buy"], 1),
            "gold_sell": round(bias["gold_sell"], 1),
            "lean": bias["lean"],
            "confidence": bias["confidence_label"],
            "reasons": bias["reasons"],
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_currencies(raw: str | None, majors: bool) -> list[str]:
    if majors:
        return list(MAJORS)
    if not raw:
        return ["USD"]
    parts = [p.strip().upper() for p in re.split(r"[,;\s]+", raw) if p.strip()]
    return parts or ["USD"]


def resolve_range(args) -> tuple[datetime, datetime]:
    if args.date_from or args.date_to:
        start = parse_day(args.date_from) if args.date_from else now_vn().replace(hour=0, minute=0, second=0, microsecond=0)
        end = parse_day(args.date_to, end=True) if args.date_to else start + timedelta(days=7)
        return start, end
    if args.days is not None:
        start = now_vn().replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=max(1, args.days))
    return week_bounds(args.week)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Lịch tin HIGH IMPACT trong tuần + xác suất ủng hộ GOLD/USD.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ví dụ:\n"
            "  python cal.py\n"
            "  python cal.py --majors --impact med\n"
            "  python cal.py --ccy USD,EUR --week last\n"
            "  python cal.py --days 5 --asset usd\n"
        ),
    )
    p.add_argument("--ccy", default=None, help="Tiền tệ, cách nhau bởi dấu phẩy (mặc định: USD)")
    p.add_argument("--majors", action="store_true", help="USD EUR GBP JPY AUD CAD NZD CHF CNY")
    p.add_argument("--impact", choices=["high", "med", "all"], default="high", help="Mức tin (mặc định: high)")
    p.add_argument("--week", choices=["this", "last", "next"], default="this", help="Tuần ISO giờ VN (T2–CN)")
    p.add_argument("--days", type=int, default=None, help="Từ 0h hôm nay thêm N ngày (ghi đè --week)")
    p.add_argument("--from", dest="date_from", help="YYYY-MM-DD")
    p.add_argument("--to", dest="date_to", help="YYYY-MM-DD (inclusive)")
    p.add_argument("--source", choices=["auto", "tv", "ff"], default="auto", help="tv=TradingView, ff=Forex Factory")
    p.add_argument("--asset", choices=["gold", "usd"], default="gold", help="Khung xác suất (mặc định: gold)")
    p.add_argument("--json", action="store_true", help="Xuất JSON thay vì bảng màu")
    p.add_argument("--no-color", action="store_true", help="Tắt ANSI")
    p.add_argument("-o", "--output", help="Ghi UTF-8 ra file")
    return p


def main() -> int:
    global USE_COLOR
    args = build_parser().parse_args()

    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    enable_windows_ansi()
    to_file = bool(args.output)
    USE_COLOR = not args.no_color and not to_file and not args.json and sys.stdout.isatty()

    currencies = parse_currencies(args.ccy, args.majors)
    start, end = resolve_range(args)

    original = sys.stdout
    fh = None
    if to_file:
        folder = os.path.dirname(args.output)
        if folder:
            os.makedirs(folder, exist_ok=True)
        fh = open(args.output, "w", encoding="utf-8")
        sys.stdout = fh

    try:
        events, src = load_events(args.source, start, end, currencies)
        events.sort(key=lambda e: e["when"])
        if args.impact == "med":
            listed = [e for e in events if e["importance"] in ("high", "medium")]
        elif args.impact == "all":
            listed = events
        else:
            listed = [e for e in events if e["importance"] == "high"]
        if args.json:
            bias = gold_usd_bias(events, now_vn())
            print(json.dumps(events_to_json(listed, src, bias), ensure_ascii=False, indent=2))
        else:
            print_report(events, src, start, end, args.impact, args.asset)
    except Exception as exc:
        sys.stdout = original
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 1
    finally:
        if fh is not None:
            sys.stdout = original
            fh.close()
            print(f"Kết quả lưu tại: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
