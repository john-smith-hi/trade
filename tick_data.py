# =============================================================================
# Tick CSV (Bid/Ask) — lưu tại www/tick (xml/www.xml), tra cứu theo giờ Việt Nam
# =============================================================================
#
# File nguồn kiểu Exness:
#   "Exness","Symbol","Timestamp","Bid","Ask"
#   "exness","XAUUSDm","2026-09-01 00:00:00.065Z",4452.22,4452.48
#
# Timestamp trong CSV là UTC. API nhận/trả thời gian giờ Việt Nam (UTC+7, không DST).
# File tháng có hàng triệu dòng: không load hết RAM; binary search rồi đọc tuần tự.
#
# =============================================================================

from __future__ import annotations

import csv
import io
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO, Iterable

ROOT = Path(__file__).resolve().parent
LEGACY_DIR = ROOT / "data" / "GOLD" / "tick"
VN = timezone(timedelta(hours=7))
UTC = timezone.utc

MAX_UPLOAD_BYTES = 64 * 1024 * 1024
MAX_PASTE_CHARS = 8 * 1024 * 1024
MAX_TABLE_LIMIT = 500
MAX_CHART_POINTS = 1200
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9._()\[\] -]{1,180}$")

_range_cache: dict[tuple[str, int, int], dict] = {}


class TickError(ValueError):
    pass


def www_tick_dir() -> Path:
    """Folder CSV trên WAMP: <www>/tick — cùng chỗ trang web."""
    try:
        import copy_www
        return copy_www.load_www_path() / "tick"
    except Exception:
        return ROOT / "tick"


def tick_dir() -> Path:
    return www_tick_dir()


def csv_dirs() -> list[Path]:
    """www/tick (ưu tiên) rồi data/GOLD/tick nếu còn file tháng cũ."""
    out: list[Path] = []
    seen: set[Path] = set()
    for path in (www_tick_dir(), LEGACY_DIR):
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if path.is_dir():
            out.append(path)
    return out


def iter_csv_files() -> list[Path]:
    found: dict[str, Path] = {}
    for folder in csv_dirs():
        for path in sorted(folder.glob("*.csv")):
            if path.is_file() and path.name not in found:
                found[path.name] = path
    return [found[name] for name in sorted(found)]


def ensure_dir() -> Path:
    dest = www_tick_dir()
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def safe_filename(name: str) -> str:
    base = Path(str(name or "")).name.strip()
    base = re.sub(r'[\x00-\x1f\x7f<>:"|?*\\/]', "_", base).strip()
    if not base.lower().endswith(".csv"):
        base = (base or "pasted") + ".csv"
    if not SAFE_NAME_RE.match(base) or base.startswith("."):
        raise TickError("Tên file không hợp lệ.")
    return base[:180]


def storage_dir_label() -> str:
    path = www_tick_dir()
    try:
        return path.resolve().as_posix()
    except OSError:
        return str(path)


def parse_utc(raw: str) -> datetime | None:
    s = str(raw or "").strip().strip('"')
    if not s:
        return None
    if s.endswith("Z") or s.endswith("z"):
        s = s[:-1]
    if "T" in s:
        s = s.replace("T", " ", 1)
    if len(s) < 19:
        return None
    try:
        year = int(s[0:4])
        month = int(s[5:7])
        day = int(s[8:10])
        hour = int(s[11:13])
        minute = int(s[14:16])
        second = int(s[17:19])
        micro = 0
        if len(s) > 19 and s[19] == ".":
            frac = re.sub(r"\D", "", s[20:])[:6]
            if frac:
                micro = int(frac.ljust(6, "0"))
        return datetime(year, month, day, hour, minute, second, micro, tzinfo=UTC)
    except (ValueError, IndexError):
        return None


def parse_vn_param(raw: str, *, end: bool = False) -> datetime:
    s = str(raw or "").strip()
    if not s:
        raise TickError("Thiếu thời gian.")
    s = s.replace(" ", "T", 1)
    if "T" not in s:
        s += "T23:59:59" if end else "T00:00:00"
    date_part, time_part = s.split("T", 1)
    dm = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", date_part)
    if not dm:
        raise TickError("Thời gian phải dạng YYYY-MM-DDTHH:MM:SS (giờ Việt Nam).")
    time_part = time_part.strip()
    if re.match(r"^\d{2}:\d{2}$", time_part):
        time_part += ":00"
    tm = re.match(r"^(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?$", time_part)
    if not tm:
        raise TickError("Giờ phải dạng HH:MM:SS.")
    try:
        micro = int((tm.group(4) or "").ljust(6, "0")[:6]) if tm.group(4) else 0
        if end and tm.group(4) is None:
            micro = 999999
        dt = datetime(
            int(dm.group(1)), int(dm.group(2)), int(dm.group(3)),
            int(tm.group(1)), int(tm.group(2)), int(tm.group(3)),
            micro, tzinfo=VN,
        )
    except ValueError as exc:
        raise TickError("Thời gian không hợp lệ.") from exc
    return dt


def fmt_vn(dt: datetime) -> str:
    local = dt.astimezone(VN)
    ms = local.microsecond
    base = local.strftime("%d/%m/%Y %H:%M:%S")
    if ms and ms != 999999:
        return base + f".{ms:06d}".rstrip("0")
    return base


def fmt_iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _header_cols(header_line: str) -> dict[str, int]:
    row = [c.strip().strip('"').lower() for c in next(csv.reader([header_line]))]
    if row and row[0].startswith("\ufeff"):
        row[0] = row[0].lstrip("\ufeff")

    def find(*names: str) -> int | None:
        for name in names:
            if name in row:
                return row.index(name)
        return None

    ts = find("timestamp", "time", "datetime")
    bid = find("bid")
    ask = find("ask")
    symbol = find("symbol")
    if ts is None or bid is None or ask is None:
        raise TickError("CSV cần cột Timestamp, Bid, Ask.")
    return {"ts": ts, "bid": bid, "ask": ask, "symbol": symbol if symbol is not None else -1}


def _parse_line(line: str, cols: dict[str, int]) -> tuple[datetime, str, float, float] | None:
    raw = line.strip()
    if not raw:
        return None
    try:
        row = next(csv.reader([raw]))
    except csv.Error:
        return None
    ts_i, bid_i, ask_i, sym_i = cols["ts"], cols["bid"], cols["ask"], cols["symbol"]
    n = len(row)
    if n <= max(ts_i, bid_i, ask_i):
        return None
    ts = parse_utc(row[ts_i])
    if ts is None:
        return None
    try:
        bid = float(row[bid_i])
        ask = float(row[ask_i])
    except ValueError:
        return None
    symbol = row[sym_i].strip().strip('"') if 0 <= sym_i < n else ""
    return ts, symbol, bid, ask


def _decode_line(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace").strip()


def _read_header(path: Path) -> tuple[dict[str, int], int]:
    with path.open("rb") as fh:
        header = _decode_line(fh.readline())
        data_pos = fh.tell()
    if not header:
        raise TickError(f"{path.name}: file trống.")
    return _header_cols(header), data_pos


def _last_data_line(path: Path) -> str:
    size = path.stat().st_size
    if size <= 0:
        return ""
    with path.open("rb") as fh:
        fh.seek(max(0, size - 16384))
        chunk = fh.read().decode("utf-8", errors="replace")
    lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
    if not lines:
        return ""
    if size <= 16384 and len(lines) >= 2:
        return lines[-1]
    return lines[-1]


def _file_meta(path: Path) -> dict:
    st = path.stat()
    key = (str(path.resolve()), st.st_mtime_ns, st.st_size)
    hit = _range_cache.get(key)
    if hit is not None:
        return hit
    try:
        cols, data_pos = _read_header(path)
        first = None
        symbol = ""
        with path.open("rb") as fh:
            fh.seek(data_pos)
            for _ in range(20):
                raw = fh.readline()
                if not raw:
                    break
                parsed = _parse_line(_decode_line(raw), cols)
                if parsed is None:
                    continue
                first = parsed[0]
                symbol = parsed[1]
                break
        last = None
        last_line = _last_data_line(path)
        if last_line:
            parsed_last = _parse_line(last_line, cols)
            if parsed_last:
                last = parsed_last[0]
        sorted_ok = bool(first and last and first <= last)
        meta = {
            "name": path.name,
            "size": st.st_size,
            "mtime": int(st.st_mtime),
            "symbol": symbol,
            "first": first,
            "last": last,
            "sorted": sorted_ok,
            "error": "",
        }
    except Exception as exc:
        meta = {
            "name": path.name,
            "size": st.st_size,
            "mtime": int(st.st_mtime),
            "symbol": "",
            "first": None,
            "last": None,
            "sorted": False,
            "error": str(exc),
        }
    _range_cache[key] = meta
    if len(_range_cache) > 64:
        _range_cache.pop(next(iter(_range_cache)))
    return meta


def _public_file(meta: dict) -> dict:
    first = meta.get("first")
    last = meta.get("last")
    return {
        "name": meta["name"],
        "size": meta["size"],
        "mtime": meta["mtime"],
        "symbol": meta.get("symbol") or "",
        "first_utc": fmt_iso(first) if first else "",
        "last_utc": fmt_iso(last) if last else "",
        "first_vn": fmt_vn(first) if first else "",
        "last_vn": fmt_vn(last) if last else "",
        "error": meta.get("error") or "",
    }


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _storage_kind(path: Path) -> str:
    if _is_under(path, www_tick_dir()):
        return "www"
    if _is_under(path, LEGACY_DIR):
        return "legacy"
    return "other"


def _public_file_from_path(path: Path) -> dict:
    out = _public_file(_file_meta(path))
    out["storage"] = _storage_kind(path)
    return out


def list_files() -> list[dict]:
    ensure_dir()
    return [_public_file_from_path(path) for path in iter_csv_files()]


def find_csv(name: str) -> Path | None:
    safe = safe_filename(name)
    for path in iter_csv_files():
        if path.name == safe:
            return path
    return None


def install_file(name: str, size: int | None = None) -> dict:
    """Đưa CSV vào www/tick: đã có đúng size thì giữ; nếu chỉ có data/GOLD/tick thì copy."""
    safe = safe_filename(name)
    dest_dir = ensure_dir()
    dest = dest_dir / safe

    def size_ok(path: Path) -> bool:
        if size is None:
            return True
        return path.stat().st_size == int(size)

    if dest.is_file() and size_ok(dest):
        return {"file": _public_file_from_path(dest), "action": "already"}

    source: Path | None = None
    for folder in (LEGACY_DIR, dest_dir):
        candidate = folder / safe
        if candidate.is_file() and size_ok(candidate):
            source = candidate.resolve()
            break

    if source is None:
        raise TickError(
            f"Không thấy '{safe}' (cùng dung lượng) trong {storage_dir_label()} "
            "hay data/GOLD/tick/. Gửi file từ máy hoặc copy vào một trong hai folder."
        )

    if source == dest.resolve() and dest.is_file():
        return {"file": _public_file_from_path(dest), "action": "already"}

    tmp = dest_dir / (safe + ".part")
    try:
        shutil.copy2(source, tmp)
        if size is not None and tmp.stat().st_size != int(size):
            raise TickError("Sau copy dung lượng không khớp.")
        if dest.is_file():
            dest.unlink()
        tmp.replace(dest)
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise
    _drop_cache(dest)
    from_label = "data/GOLD/tick" if _is_under(source, LEGACY_DIR) else storage_dir_label()
    return {
        "file": _public_file_from_path(dest),
        "action": "copied",
        "from": from_label,
    }


def adopt_file(name: str, size: int | None = None) -> dict:
    """Alias install_file — API /api/tick/adopt."""
    return install_file(name, size)


def _resolve_existing(name: str) -> Path:
    safe = safe_filename(name)
    dest = ensure_dir()
    path = (dest / safe).resolve()
    root = dest.resolve()
    if path.parent == root and path.is_file():
        return path
    raise TickError(
        f"Không thấy '{safe}' trong {storage_dir_label()}. "
        "File trong data/GOLD/tick/ là bản nguồn — xóa tay nếu cần."
    )


def delete_file(name: str) -> None:
    path = _resolve_existing(name)
    path.unlink()


def _validate_csv_prefix(text: str) -> None:
    sample = text[:65536]
    stream = io.StringIO(sample)
    header = stream.readline()
    if not header.strip():
        raise TickError("CSV trống.")
    cols = _header_cols(header)
    ok = 0
    for line in stream:
        if _parse_line(line, cols):
            ok += 1
            if ok >= 1:
                return
    raise TickError("Không đọc được dòng tick nào (Timestamp, Bid, Ask).")


def save_csv_text(filename: str, text: str) -> dict:
    if len(text) > MAX_PASTE_CHARS:
        raise TickError(f"Nội dung dán tối đa {MAX_PASTE_CHARS // (1024 * 1024)} MB.")
    _validate_csv_prefix(text)
    ensure_dir()
    name = safe_filename(filename or "pasted.csv")
    dest = ensure_dir() / name
    dest.write_text(text, encoding="utf-8", newline="\n")
    _drop_cache(dest)
    return _public_file(_file_meta(dest))


def save_upload(filename: str, stream: BinaryIO, size: int | None = None) -> dict:
    if size is not None and size > MAX_UPLOAD_BYTES:
        raise TickError(
            f"Upload qua web tối đa {MAX_UPLOAD_BYTES // (1024 * 1024)} MB. "
            f"File tháng hãy copy thẳng vào {storage_dir_label()}/."
        )
    ensure_dir()
    name = safe_filename(filename)
    dest = ensure_dir() / name
    tmp = dest.with_name(dest.name + ".part")
    written = 0
    head = b""
    try:
        with tmp.open("wb") as out:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    raise TickError(
                        f"Upload qua web tối đa {MAX_UPLOAD_BYTES // (1024 * 1024)} MB. "
                        f"File tháng hãy copy thẳng vào {storage_dir_label()}/."
                    )
                if len(head) < 65536:
                    need = 65536 - len(head)
                    head += chunk[:need]
                out.write(chunk)
        if written == 0:
            raise TickError("File trống.")
        _validate_csv_prefix(head.decode("utf-8", errors="replace"))
        tmp.replace(dest)
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise
    _drop_cache(dest)
    return _public_file(_file_meta(dest))


def _drop_cache(path: Path) -> None:
    prefix = str(path.resolve())
    dead = [key for key in _range_cache if key[0] == prefix]
    for key in dead:
        _range_cache.pop(key, None)


def _seek_first_ge(path: Path, cols: dict[str, int], data_pos: int, target: datetime) -> int:
    with path.open("rb") as fh:
        fh.seek(0, 2)
        end = fh.tell()
        lo = data_pos
        hi = end
        best = data_pos
        while lo < hi:
            mid = (lo + hi) // 2
            fh.seek(mid)
            if mid > data_pos:
                fh.readline()
            pos = fh.tell()
            if pos >= end:
                hi = mid
                continue
            line = fh.readline()
            parsed = _parse_line(_decode_line(line), cols) if line else None
            if parsed is None or parsed[0] < target:
                lo = fh.tell()
            else:
                best = pos
                hi = pos
        return best


def _iter_from(path: Path, start_pos: int) -> Iterable[str]:
    with path.open("rb") as fh:
        fh.seek(start_pos)
        for raw in fh:
            line = _decode_line(raw)
            if line:
                yield line


def _row_public(ts: datetime, symbol: str, bid: float, ask: float, name: str) -> dict:
    spread = round(ask - bid, 6)
    return {
        "t": int(ts.timestamp() * 1000),
        "ts_utc": fmt_iso(ts),
        "ts_vn": fmt_vn(ts),
        "symbol": symbol,
        "bid": bid,
        "ask": ask,
        "spread": spread,
        "file": name,
    }


def query_ticks(
    *,
    start_vn: datetime,
    end_vn: datetime,
    symbol: str = "",
    filename: str = "",
    offset: int = 0,
    limit: int = 100,
    chart_points: int = 800,
) -> dict:
    if end_vn < start_vn:
        raise TickError("Thời gian bắt đầu đang sau thời gian kết thúc.")
    if offset < 0:
        offset = 0
    if limit < 1:
        limit = 100
    limit = min(limit, MAX_TABLE_LIMIT)
    chart_points = max(2, min(int(chart_points or 800), MAX_CHART_POINTS))

    start_utc = start_vn.astimezone(UTC)
    end_utc = end_vn.astimezone(UTC)
    want_symbol = (symbol or "").strip()
    want_file = (filename or "").strip()

    ensure_dir()
    metas = []
    for path in iter_csv_files():
        if not path.is_file():
            continue
        if want_file and path.name != want_file:
            continue
        meta = _file_meta(path)
        if meta.get("error"):
            continue
        first, last = meta.get("first"), meta.get("last")
        if first and last and (last < start_utc or first > end_utc):
            continue
        metas.append((path, meta))

    span_ms = max(1, int((end_utc - start_utc).total_seconds() * 1000))
    bucket_ms = max(1, span_ms // chart_points)
    buckets: dict[int, list] = {}

    count = 0
    skipped = 0
    rows: list[dict] = []
    first_hit = None
    last_hit = None
    bid_min = bid_max = ask_min = ask_max = None
    spread_min = spread_max = None
    spread_sum = 0.0
    used = []

    for path, meta in metas:
        cols, data_pos = _read_header(path)
        start_pos = data_pos
        if meta.get("sorted") and meta.get("first") and meta["first"] < start_utc:
            start_pos = _seek_first_ge(path, cols, data_pos, start_utc)
        used.append(path.name)
        stop_early = bool(meta.get("sorted"))
        for line in _iter_from(path, start_pos):
            parsed = _parse_line(line, cols)
            if parsed is None:
                continue
            ts, sym, bid, ask = parsed
            if ts < start_utc:
                continue
            if ts > end_utc:
                if stop_early:
                    break
                continue
            if want_symbol and sym != want_symbol:
                continue
            spread = ask - bid
            if first_hit is None:
                first_hit = (ts, sym, bid, ask)
            last_hit = (ts, sym, bid, ask)
            if bid_min is None or bid < bid_min:
                bid_min = bid
            if bid_max is None or bid > bid_max:
                bid_max = bid
            if ask_min is None or ask < ask_min:
                ask_min = ask
            if ask_max is None or ask > ask_max:
                ask_max = ask
            if spread_min is None or spread < spread_min:
                spread_min = spread
            if spread_max is None or spread > spread_max:
                spread_max = spread
            spread_sum += spread

            t_ms = int(ts.timestamp() * 1000)
            bidx = min(chart_points - 1, int((t_ms - int(start_utc.timestamp() * 1000)) / bucket_ms))
            cell = buckets.get(bidx)
            if cell is None:
                buckets[bidx] = [t_ms, bid, bid, ask, ask, bid, ask]
            else:
                cell[0] = t_ms
                if bid < cell[1]:
                    cell[1] = bid
                if bid > cell[2]:
                    cell[2] = bid
                if ask < cell[3]:
                    cell[3] = ask
                if ask > cell[4]:
                    cell[4] = ask
                cell[5] = bid
                cell[6] = ask

            if skipped < offset:
                skipped += 1
            elif len(rows) < limit:
                rows.append(_row_public(ts, sym, bid, ask, path.name))
            count += 1

    chart = []
    for idx in sorted(buckets):
        t_ms, bmin, bmax, amin, amax, blast, alast = buckets[idx]
        chart.append({
            "t": t_ms,
            "bid": blast,
            "ask": alast,
            "bid_min": bmin,
            "bid_max": bmax,
            "ask_min": amin,
            "ask_max": amax,
        })

    stats = {
        "count": count,
        "first_vn": fmt_vn(first_hit[0]) if first_hit else "",
        "last_vn": fmt_vn(last_hit[0]) if last_hit else "",
        "first_utc": fmt_iso(first_hit[0]) if first_hit else "",
        "last_utc": fmt_iso(last_hit[0]) if last_hit else "",
        "bid_min": bid_min,
        "bid_max": bid_max,
        "bid_open": first_hit[2] if first_hit else None,
        "bid_close": last_hit[2] if last_hit else None,
        "ask_min": ask_min,
        "ask_max": ask_max,
        "ask_open": first_hit[3] if first_hit else None,
        "ask_close": last_hit[3] if last_hit else None,
        "spread_min": round(spread_min, 6) if spread_min is not None else None,
        "spread_max": round(spread_max, 6) if spread_max is not None else None,
        "spread_avg": round(spread_sum / count, 6) if count else None,
        "symbol": first_hit[1] if first_hit else want_symbol,
    }
    return {
        "rows": rows,
        "total": count,
        "offset": offset,
        "limit": limit,
        "stats": stats,
        "chart": chart,
        "files": used,
        "from_vn": fmt_vn(start_vn),
        "to_vn": fmt_vn(end_vn),
        "dir": storage_dir_label(),
    }
