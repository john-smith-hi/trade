# =============================================================================
# HƯỚNG DẪN SỬ DỤNG
# =============================================================================
#
# Đây là 1 HTTP API mỏng để giao diện web (đặt tại D:\wamp64\www\mt5) gọi vào
# các hàm giao dịch có sẵn trong mt5.py. Không thay đổi logic giao dịch, chỉ
# bọc lại qua HTTP để trang web dùng fetch() gọi được.
#
# CÀI ĐẶT
#   python -m pip install flask flask-cors
#
# CHẠY
#   python api.py
#   hoặc start_server.bat  (24/7 + vòng restart nếu crash)
#   (mặc định lắng nghe tại http://127.0.0.1:5001, chỉ localhost, không expose
#   ra mạng ngoài vì có thao tác gửi lệnh thật + thông tin tài khoản)
#
# AUTO-RELOAD
#   - Sửa file .py hoặc bất kỳ file .xml trong project → process tự restart, nạp lại toàn bộ.
#   - Thêm lớp an toàn: mỗi request /api/accounts và /api/action vẫn kiểm tra mtime
#     xml/accounts.xml và nạp lại ngay nếu file đổi (không chờ reloader).
#
# ENDPOINT
#   GET  /api/paths             -> danh sách path (name + exe) từ xml/paths.xml
#   POST /api/paths             -> thêm path mới
#   PUT  /api/paths/<name>      -> sửa exe của path (không đổi name)
#   GET  /api/accounts          -> danh sách account (path = tên path; có path_exe)
#   POST /api/accounts          -> thêm account mới
#   PUT  /api/accounts/<name>   -> sửa cấu hình (không đổi login/password/server/name)
#   POST /api/reload-accounts   -> nạp lại xml/accounts.xml (ép buộc)
#   POST /api/action            -> thực thi action (status/open/pending/cancel-pending/close-all/modify-all)
#   GET  /api/quote?account=&symbol=&side=  -> bid/ask/entry tick live (điền TP/SL)
#   GET  /api/candle?account=&symbol=&closed=1  -> nến M1 (mặc định nến đã đóng)
#   GET  /api/positions?account=            -> lệnh mở JSON (điền TP/SL khi modify-all)
#   GET  /api/orders?account=               -> lệnh chờ JSON (cancel-pending)
#   GET    /api/history?limit=50  -> lịch sử (lines + rows đã parse cho bảng)
#   DELETE /api/history           -> xóa toàn bộ history_mt5.txt
#
# Kết quả của /api/action trả về đúng nguyên văn các dòng print() của mt5.py
# (dạng text, giống output khi chạy CLI), để hiển thị trực tiếp trên web.
#
# CHECKLIST SETUP (day_trade.py)
#   UI WAMP: D:\wamp64\www\setup → http://localhost/setup/ (proxy.php → api.py)
#   Mã nguồn UI cũng có trong repo setup/ (cùng pattern mt5/: common.js + proxy.php)
#   GET    /api/setup/week              -> tuần hiện tại (auto đóng/tạo) + weekday + can_trade + monday_complete
#   PUT    /api/setup/week/<week_id>    -> lưu quan sát ① (H/L, tin) + xu hướng ②
#   GET    /api/setup/reaction-check    -> ⑤ kiểm tra rejection 1 nến/2 nến/vùng giá theo nến H1 (gợi ý)
#   POST   /api/setup/setups            -> chấm điểm + lưu 1 setup mới
#   PUT    /api/setup/setups/<id>       -> chấm điểm lại + sửa 1 setup (tuần active)
#   DELETE /api/setup/setups/<id>?week_id=  -> xóa 1 setup (tuần active)
#   GET    /api/setup/timer             -> danh sách báo thức vùng giá (xml/timer.xml)
#   PUT    /api/setup/timer             -> lưu toàn bộ danh sách báo thức
#   POST   /api/setup/telegram-test     -> gửi 1 tin thử qua bot Telegram
#   GET    /setup/, /setup/<file>       -> serve file tĩnh repo (dev); production dùng WAMP
#
# CHẠY 24/7 (Windows Server)
#   start_server.bat  → TRADE_SERVER=1, watcher Timer + lệnh, KHÔNG Flask-reloader
#                       (tránh 2 process kẹt port → UI timeout 12s). Sửa .py → restart bat.
#                       Sửa accounts/paths.xml → soft-reload, không cần restart.
#
# =============================================================================

import contextlib
import io
import os
import threading
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

import day_trade
import mt5 as mt5app
import telegram_notify
import timer_alerts
import watch
import watch_state

API_HOST = "127.0.0.1"
API_PORT = 5001
ROOT_DIR = Path(__file__).resolve().parent
SETUP_DIR = ROOT_DIR / "setup"
SERVER_MODE = os.environ.get("TRADE_SERVER") == "1"
# Server 24/7: tắt reloader — trên Windows dễ có 2 process LISTEN cùng port,
# TCP nối được nhưng không trả HTTP → trình duyệt AbortError "API timeout" sau 12s.
USE_RELOADER = not SERVER_MODE

app = Flask(__name__)
CORS(app)

# mt5.py giữ state toàn cục (NO_ASK, CURRENT_ACCOUNT_NAME, kết nối MT5 đang mở),
# nên phải serialize mọi lệnh gọi vào đó để 2 request web không chạy song song.
_lock = threading.Lock()


def _watch_extra_files():
    """Mọi .py (root) và mọi .xml trong project — đổi là reloader restart process.

    Ngoại lệ: XML dữ liệu đổi liên tục (checklist, timer, telegram, watch)
    không nên coi là "đổi code" -> loại khỏi danh sách theo dõi.
    """
    skip = {
        day_trade.WEEK_FILE.resolve(),
        timer_alerts.ALERTS_FILE.resolve(),
        telegram_notify.CONFIG_FILE.resolve(),
        watch_state.WATCH_FILE.resolve(),
    }
    watched = {p.resolve() for p in ROOT_DIR.glob("*.py") if p.is_file()}
    watched.update(
        p.resolve() for p in ROOT_DIR.rglob("*.xml")
        if p.is_file() and p.resolve() not in skip
    )
    watched.add((ROOT_DIR / "xml" / "accounts.xml").resolve())
    watched.add((ROOT_DIR / "xml" / "paths.xml").resolve())
    watched -= skip
    return [str(p) for p in sorted(watched)]


def _resolve_path_exe(path_ref):
    if not path_ref:
        return ""
    try:
        return mt5app.resolve_terminal_path({"path": path_ref}) or ""
    except RuntimeError:
        return ""


def _account_public(acc):
    """Thông tin account an toàn để trả cho web, KHÔNG bao gồm password."""
    path_ref = acc.get("path") or ""
    return {
        "name": acc.get("name"),
        "login": acc.get("login"),
        "server": acc.get("server"),
        "path": path_ref,
        "path_exe": _resolve_path_exe(path_ref),
        "suffix": acc.get("suffix"),
        "multi": acc.get("multi"),
        "default_lot": acc.get("default_lot", 0.01),
        "xauusd_max_loss": acc.get("xauusd_max_loss"),
        "auto_copy_enabled": acc.get("auto_copy_enabled"),
        "auto_copy_targets": acc.get("auto_copy_targets"),
    }


def _validate_path_ref(path_ref):
    """path trên account phải là tên trong paths.xml (hoặc rỗng)."""
    if path_ref in (None, ""):
        return None
    ref = str(path_ref).strip().lower()
    if mt5app._looks_like_filesystem_path(ref):
        raise ValueError(
            "path của account phải là tên trong paths.xml (vd: exness, ftmo), không nhập full path."
        )
    names = {p.get("name") for p in mt5app.PATHS}
    if ref not in names:
        raise ValueError(f"Path '{ref}' không tồn tại trong paths.xml. Các path hiện có: {', '.join(sorted(names))}")
    return ref


def _to_float_or_none(value, field_name):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"'{field_name}' không hợp lệ: {value!r}")


def _to_float(value, field_name, default=None):
    if value in (None, ""):
        if default is not None:
            return default
        raise ValueError(f"Thiếu '{field_name}'")
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"'{field_name}' không hợp lệ: {value!r}")


def _parse_auto_copy_targets(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _parse_editable_fields(data, *, require_present=False):
    """Parse các trường được phép sửa (không gồm login/password/server/name)."""
    allowed = {
        "path", "suffix", "multi", "default_lot", "xauusd_max_loss",
        "auto_copy_enabled", "auto_copy_targets",
    }
    forbidden = {"login", "password", "server", "name"}
    present_forbidden = sorted(forbidden & set(data.keys()))
    if present_forbidden:
        raise ValueError(
            "Không được thay đổi: " + ", ".join(present_forbidden)
        )

    unknown = sorted(set(data.keys()) - allowed)
    if unknown:
        raise ValueError("Trường không hỗ trợ: " + ", ".join(unknown))

    if require_present:
        missing = sorted(allowed - set(data.keys()))
        if missing:
            raise ValueError("Thiếu trường: " + ", ".join(missing))

    fields = {}
    if "path" in data:
        fields["path"] = _validate_path_ref(data.get("path"))
    if "suffix" in data:
        fields["suffix"] = str(data.get("suffix") or "")
    if "multi" in data:
        fields["multi"] = _to_float(data.get("multi"), "multi", default=1.0)
    if "default_lot" in data:
        default_lot = _to_float(data.get("default_lot"), "default_lot", default=0.01)
        if default_lot <= 0:
            raise ValueError("'default_lot' phải > 0")
        fields["default_lot"] = default_lot
    if "xauusd_max_loss" in data:
        fields["xauusd_max_loss"] = _to_float_or_none(data.get("xauusd_max_loss"), "xauusd_max_loss")
    if "auto_copy_enabled" in data:
        fields["auto_copy_enabled"] = bool(data.get("auto_copy_enabled"))
    if "auto_copy_targets" in data:
        fields["auto_copy_targets"] = _parse_auto_copy_targets(data.get("auto_copy_targets"))
    return fields


def _resolve_lot_for_account(account_name, lot_raw):
    if lot_raw not in (None, ""):
        try:
            lot = float(lot_raw)
            if lot > 0:
                return lot
        except (TypeError, ValueError):
            pass
    for acc in mt5app.ACCOUNTS:
        if acc.get("name") == account_name:
            return float(acc.get("default_lot") or 0.01)
    return 0.01


def _find_account_index(name):
    for idx, acc in enumerate(mt5app.ACCOUNTS):
        if acc.get("name") == name:
            return idx
    return None


def _find_path_index(name):
    key = str(name or "").strip().lower()
    for idx, item in enumerate(mt5app.PATHS):
        if item.get("name") == key:
            return idx
    return None


@app.get("/api/paths")
def get_paths():
    # Không lấy _lock MT5 — chỉ đọc XML; tránh treo khi watcher đang connect.
    mt5app.ensure_paths_fresh()
    return jsonify({"paths": list(mt5app.PATHS)})


@app.post("/api/paths")
def create_path_endpoint():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or "").strip().lower()
    exe = str(data.get("exe") or "").strip()
    if not name:
        return jsonify({"error": "Thiếu 'name'"}), 400
    if not exe:
        return jsonify({"error": "Thiếu 'exe'"}), 400
    if mt5app._looks_like_filesystem_path(name):
        return jsonify({"error": "name path không được là đường dẫn file"}), 400

    with _lock:
        mt5app.ensure_paths_fresh()
        if _find_path_index(name) is not None:
            return jsonify({"error": f"Path '{name}' đã tồn tại"}), 400
        paths = list(mt5app.PATHS)
        paths.append({"name": name, "exe": exe})
        mt5app.save_paths(paths)
        paths = mt5app.reload_paths()
    return jsonify({"paths": paths}), 201


@app.put("/api/paths/<name>")
def update_path_endpoint(name):
    data = request.get_json(silent=True) or {}
    if "name" in data:
        return jsonify({"error": "Không được đổi name của path"}), 400
    if "exe" not in data:
        return jsonify({"error": "Thiếu 'exe'"}), 400
    exe = str(data.get("exe") or "").strip()
    if not exe:
        return jsonify({"error": "'exe' không được rỗng"}), 400

    with _lock:
        mt5app.ensure_paths_fresh()
        idx = _find_path_index(name)
        if idx is None:
            return jsonify({"error": f"Không tìm thấy path '{name}'"}), 404
        paths = list(mt5app.PATHS)
        updated = dict(paths[idx])
        updated["exe"] = exe
        updated["name"] = paths[idx]["name"]
        paths[idx] = updated
        mt5app.save_paths(paths)
        paths = mt5app.reload_paths()
    return jsonify({"paths": paths})


@app.get("/api/accounts")
def get_accounts():
    # Không lấy _lock MT5 — trang web / trình duyệt mở URL này không bị watcher chặn.
    mt5app.ensure_accounts_fresh()
    accounts = [_account_public(acc) for acc in mt5app.ACCOUNTS]
    return jsonify({"accounts": accounts})


@app.post("/api/accounts")
def create_account_endpoint():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Thiếu 'name'"}), 400

    required = ("login", "password", "server")
    missing = [k for k in required if data.get(k) in (None, "")]
    if missing:
        return jsonify({"error": "Thiếu: " + ", ".join(missing)}), 400

    try:
        login = int(data.get("login"))
    except (TypeError, ValueError):
        return jsonify({"error": "'login' không hợp lệ"}), 400

    password = str(data.get("password"))
    server = str(data.get("server")).strip()
    if not server:
        return jsonify({"error": "Thiếu 'server'"}), 400

    editable_raw = {
        k: data[k]
        for k in (
            "path", "suffix", "multi", "default_lot", "xauusd_max_loss",
            "auto_copy_enabled", "auto_copy_targets",
        )
        if k in data
    }
    try:
        with _lock:
            mt5app.ensure_paths_fresh()
            editable = _parse_editable_fields(editable_raw)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    new_account = {
        "name": name,
        "login": login,
        "password": password,
        "server": server,
        "path": editable.get("path"),
        "suffix": editable.get("suffix", ""),
        "multi": editable.get("multi", 1.0),
        "default_lot": editable.get("default_lot", 0.01),
        "xauusd_max_loss": editable.get("xauusd_max_loss"),
        "auto_copy_enabled": editable.get("auto_copy_enabled", False),
        "auto_copy_targets": editable.get("auto_copy_targets", []),
    }

    with _lock:
        mt5app.ensure_accounts_fresh()
        if _find_account_index(name) is not None:
            return jsonify({"error": f"Account '{name}' đã tồn tại"}), 400
        accounts = list(mt5app.ACCOUNTS)
        accounts.append(new_account)
        mt5app.save_accounts(accounts)
        accounts = mt5app.reload_accounts()

    return jsonify({"accounts": [_account_public(acc) for acc in accounts]}), 201


@app.put("/api/accounts/<name>")
def update_account_endpoint(name):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "Body JSON không hợp lệ"}), 400

    try:
        with _lock:
            mt5app.ensure_paths_fresh()
            # Sửa: bắt buộc gửi đủ các trường editable để form UI đồng bộ.
            fields = _parse_editable_fields(data, require_present=True)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    with _lock:
        mt5app.ensure_accounts_fresh()
        idx = _find_account_index(name)
        if idx is None:
            return jsonify({"error": f"Không tìm thấy account '{name}'"}), 404

        accounts = list(mt5app.ACCOUNTS)
        updated = dict(accounts[idx])
        # Giữ nguyên login / password / server / name.
        updated.update(fields)
        updated["name"] = accounts[idx]["name"]
        updated["login"] = accounts[idx]["login"]
        updated["password"] = accounts[idx]["password"]
        updated["server"] = accounts[idx]["server"]
        accounts[idx] = updated
        mt5app.save_accounts(accounts)
        accounts = mt5app.reload_accounts()

    return jsonify({"accounts": [_account_public(acc) for acc in accounts]})


@app.post("/api/reload-accounts")
def reload_accounts_endpoint():
    with _lock:
        accounts = mt5app.reload_accounts()
    return jsonify({"accounts": [_account_public(acc) for acc in accounts]})


@app.post("/api/action")
def action_endpoint():
    data = request.get_json(silent=True) or {}

    account = data.get("account")
    action = data.get("action")
    if not account or not action:
        return jsonify({"error": "Thiếu 'account' hoặc 'action'"}), 400

    symbol = data.get("symbol") or "XAUUSD"
    side = data.get("side") or "buy"
    comment = data.get("comment") or "Python trader test"
    no_ask = bool(data.get("no_ask", False))

    try:
        with _lock:
            mt5app.ensure_accounts_fresh()
            lot = _resolve_lot_for_account(account, data.get("lot"))
        tp_price = _to_float_or_none(data.get("tp_price"), "tp_price")
        sl_price = _to_float_or_none(data.get("sl_price"), "sl_price")
        price = _to_float_or_none(data.get("price"), "price")
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    pending_type = (data.get("pending_type") or "limit").strip().lower()
    if pending_type not in ("limit", "stop"):
        return jsonify({"error": "'pending_type' phải là limit hoặc stop"}), 400

    if action in ("open", "pending", "modify-all"):
        if sl_price is None or sl_price <= 0:
            return jsonify({"error": "Stop loss là bắt buộc (sl_price > 0)"}), 400

    copy_raw = data.get("copy", None)
    if copy_raw is None:
        copy_names = None  # dùng auto_copy_enabled/auto_copy_targets cấu hình sẵn
    else:
        copy_names = [c.strip() for c in str(copy_raw).split(",") if c.strip()]

    buf = io.StringIO()
    with _lock:
        mt5app.ensure_accounts_fresh()
        try:
            with contextlib.redirect_stdout(buf):
                mt5app.execute_request(
                    account, action, symbol, side, lot,
                    tp_price, sl_price, comment, no_ask, copy_names,
                    price=price, pending_type=pending_type,
                )
        except Exception as exc:
            print(f"Lỗi: {exc}", file=buf)

    return jsonify({"output": buf.getvalue()})


@app.get("/api/quote")
def quote_endpoint():
    """Lấy bid/ask/entry cho symbol — dùng UI điền TP/SL khi chọn open."""
    account_name = (request.args.get("account") or "").strip()
    symbol = (request.args.get("symbol") or "XAUUSD").strip()
    side = (request.args.get("side") or "buy").strip().lower()
    if not account_name:
        return jsonify({"error": "Thiếu 'account'"}), 400
    if side not in ("buy", "sell"):
        return jsonify({"error": "'side' phải là buy hoặc sell"}), 400

    buf = io.StringIO()
    with _lock:
        mt5app.ensure_accounts_fresh()
        try:
            account = mt5app.get_account(account_name)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 404
        try:
            with contextlib.redirect_stdout(buf):
                mt5app.connect_mt5(account)
                quote = mt5app.fetch_quote(account, symbol, side)
        except Exception as exc:
            return jsonify({"error": str(exc), "detail": buf.getvalue()}), 500
        finally:
            try:
                mt5app.mt5.shutdown()
            except Exception:
                pass

    return jsonify(quote)


@app.get("/api/candle")
def candle_endpoint():
    """Nến M1 — mặc định nến đã đóng gần nhất (closed=1). Timer dùng endpoint này."""
    account_name = (request.args.get("account") or "").strip()
    symbol = (request.args.get("symbol") or "XAUUSD").strip()
    closed_raw = (request.args.get("closed") or "1").strip().lower()
    closed = closed_raw not in ("0", "false", "no", "off")
    if not account_name:
        return jsonify({"error": "Thiếu 'account'"}), 400

    buf = io.StringIO()
    with _lock:
        mt5app.ensure_accounts_fresh()
        try:
            account = mt5app.get_account(account_name)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 404
        try:
            with contextlib.redirect_stdout(buf):
                mt5app.connect_mt5(account)
                candle = mt5app.fetch_last_m1_candle(account, symbol, closed=closed)
        except Exception as exc:
            return jsonify({"error": str(exc), "detail": buf.getvalue()}), 500
        finally:
            try:
                mt5app.mt5.shutdown()
            except Exception:
                pass

    return jsonify(candle)


@app.get("/api/setup/reaction-check")
def setup_reaction_check_endpoint():
    """Kiểm tra tự động 3 kiểu rejection (⑤) tại 1 vùng giá, dựa trên nến H1 live.

    Chỉ để gợi ý — không ép buộc checkbox, người dùng vẫn tự tick/sửa trên UI.
    """
    account_name = (request.args.get("account") or "").strip()
    symbol = (request.args.get("symbol") or "XAUUSD").strip()
    side = (request.args.get("side") or "buy").strip().lower()
    zone_raw = (request.args.get("zone") or "").strip()
    if not account_name:
        return jsonify({"error": "Thiếu 'account'"}), 400
    if side not in ("buy", "sell"):
        return jsonify({"error": "'side' phải là buy hoặc sell"}), 400
    try:
        zone = float(zone_raw)
    except (TypeError, ValueError):
        return jsonify({"error": "Thiếu hoặc sai 'zone' (giá vùng cần kiểm tra)"}), 400

    buf = io.StringIO()
    with _lock:
        mt5app.ensure_accounts_fresh()
        try:
            account = mt5app.get_account(account_name)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 404
        try:
            with contextlib.redirect_stdout(buf):
                mt5app.connect_mt5(account)
                candles = mt5app.fetch_h1_candles(account, symbol, count=10)
        except Exception as exc:
            return jsonify({"error": str(exc), "detail": buf.getvalue()}), 500
        finally:
            try:
                mt5app.mt5.shutdown()
            except Exception:
                pass

    checks = {
        "wick_1candle": day_trade.check_wick_rejection(candles, side, zone),
        "engulf_2candle": day_trade.check_engulf_rejection(candles, side, zone),
        "zone_sweep": day_trade.check_zone_sweep_rejection(candles, side, zone),
    }
    return jsonify({
        "symbol": candles[-1]["symbol"] if candles else symbol,
        "side": side,
        "zone": zone,
        "checks": checks,
        "candles": candles[-6:],
    })


@app.get("/api/positions")
def positions_endpoint():
    """Lệnh đang mở (JSON) — dùng UI điền TP/SL khi chọn modify-all."""
    account_name = (request.args.get("account") or "").strip()
    if not account_name:
        return jsonify({"error": "Thiếu 'account'"}), 400

    buf = io.StringIO()
    with _lock:
        mt5app.ensure_accounts_fresh()
        try:
            account = mt5app.get_account(account_name)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 404
        try:
            with contextlib.redirect_stdout(buf):
                mt5app.connect_mt5(account)
                positions = mt5app.list_open_positions_data()
        except Exception as exc:
            return jsonify({"error": str(exc), "detail": buf.getvalue()}), 500
        finally:
            try:
                mt5app.mt5.shutdown()
            except Exception:
                pass

    return jsonify({"positions": positions})


@app.get("/api/orders")
def orders_endpoint():
    """Lệnh chờ (JSON) — dùng UI khi chọn cancel-pending."""
    account_name = (request.args.get("account") or "").strip()
    if not account_name:
        return jsonify({"error": "Thiếu 'account'"}), 400

    buf = io.StringIO()
    with _lock:
        mt5app.ensure_accounts_fresh()
        try:
            account = mt5app.get_account(account_name)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 404
        try:
            with contextlib.redirect_stdout(buf):
                mt5app.connect_mt5(account)
                orders = mt5app.list_pending_orders_data()
        except Exception as exc:
            return jsonify({"error": str(exc), "detail": buf.getvalue()}), 500
        finally:
            try:
                mt5app.mt5.shutdown()
            except Exception:
                pass

    return jsonify({"orders": orders})


@app.get("/api/history")
def history_endpoint():
    limit = request.args.get("limit", default=50, type=int)
    if limit is None or limit < 1:
        limit = 50
    limit = min(limit, 500)

    if not mt5app.HISTORY_FILE.exists():
        return jsonify({"lines": [], "rows": []})

    text = mt5app.HISTORY_FILE.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    lines = lines[:limit]
    rows = [_parse_history_line(line) for line in lines]
    return jsonify({"lines": lines, "rows": rows})


@app.delete("/api/history")
def history_delete_endpoint():
    with _lock:
        mt5app.HISTORY_FILE.write_text("", encoding="utf-8")
    return jsonify({"ok": True, "lines": [], "rows": []})


def _parse_history_line(line):
    """Parse 1 dòng history_mt5.txt thành object bảng."""
    parts = [p.strip() for p in str(line).split("|")]
    row = {
        "time": "",
        "account": "",
        "symbol": "",
        "lot": "",
        "status": "",
        "ticket": "",
        "retcode": "",
        "comment": "",
        "detail": "",
        "raw": line,
    }
    if not parts:
        return row

    # Phần đầu thường là timestamp (không có key=).
    first = parts[0]
    if "=" not in first:
        row["time"] = first
        parts = parts[1:]
    else:
        row["time"] = ""

    for part in parts:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        if key in row:
            row[key] = value
    return row


@app.get("/setup/")
@app.get("/setup/<path:filename>")
def setup_static(filename="index.html"):
    return send_from_directory(SETUP_DIR, filename)


@app.get("/api/setup/week")
def setup_week_endpoint():
    # Không lấy _lock MT5 — chỉ XML tuần; tránh treo khi watcher đang connect.
    week, weekday, is_weekend = day_trade.ensure_current_week()
    monday_complete = bool(week) and day_trade.monday_session_complete(week)
    return jsonify({
        "week": week,
        "weekday": weekday,
        "is_weekend": is_weekend,
        "monday_complete": monday_complete,
        "can_trade": bool(week) and week.get("status") == "active" and day_trade.week_session_started(week),
    })


@app.put("/api/setup/week/<week_id>")
def setup_week_update_endpoint(week_id):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "Body JSON không hợp lệ"}), 400

    try:
        with _lock:
            week = day_trade.update_week_observations(week_id, data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"week": week})


@app.post("/api/setup/setups")
def setup_create_endpoint():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "Body JSON không hợp lệ"}), 400

    week_id = str(data.get("week_id") or "").strip()
    if not week_id:
        return jsonify({"error": "Thiếu 'week_id'"}), 400
    symbol = data.get("symbol") or "XAUUSD"
    trade_range = bool(data.get("trade_range"))

    try:
        with _lock:
            week, weekday, _ = day_trade.ensure_current_week()
            if week is None or week.get("id") != week_id:
                return jsonify({"error": "week_id không khớp tuần đang active — tải lại trang."}), 400
            evaluated = day_trade.evaluate_setup(week, data, weekday)
            week, setup = day_trade.add_setup(week_id, symbol, evaluated["side"], trade_range, evaluated)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"week": week, "setup": setup}), 201


@app.put("/api/setup/setups/<setup_id>")
def setup_update_endpoint(setup_id):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "Body JSON không hợp lệ"}), 400

    week_id = str(data.get("week_id") or "").strip()
    if not week_id:
        return jsonify({"error": "Thiếu 'week_id'"}), 400
    symbol = data.get("symbol") or "XAUUSD"
    trade_range = bool(data.get("trade_range"))

    try:
        with _lock:
            week = day_trade.get_week(week_id)
            if week is None:
                return jsonify({"error": f"Không tìm thấy tuần '{week_id}'"}), 404
            _, weekday, _ = day_trade.ensure_current_week()
            evaluated = day_trade.evaluate_setup(week, data, weekday)
            week, setup = day_trade.update_setup(week_id, setup_id, symbol, evaluated["side"], trade_range, evaluated)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"week": week, "setup": setup})


@app.delete("/api/setup/setups/<setup_id>")
def setup_delete_endpoint(setup_id):
    week_id = str(request.args.get("week_id") or "").strip()
    if not week_id:
        return jsonify({"error": "Thiếu 'week_id'"}), 400

    try:
        with _lock:
            week = day_trade.delete_setup(week_id, setup_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"week": week})


@app.get("/api/setup/timer")
def setup_timer_list_endpoint():
    return jsonify({"alerts": timer_alerts.load_alerts()})


@app.put("/api/setup/timer")
def setup_timer_save_endpoint():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "Body JSON không hợp lệ"}), 400

    raw = data.get("alerts")
    if raw is None:
        return jsonify({"error": "Thiếu 'alerts'"}), 400

    try:
        with _lock:
            alerts = timer_alerts.replace_alerts(raw)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"alerts": alerts})


@app.post("/api/setup/telegram-test")
def setup_telegram_test_endpoint():
    status = telegram_notify.config_status()
    if not status.get("configured"):
        return jsonify({
            "error": "Chưa cấu hình xml/telegram.xml (bot_token / chat_id).",
            **status,
        }), 400
    if not status.get("enabled"):
        return jsonify({
            "error": "Telegram đang tắt — đặt <enabled>true</enabled> trong xml/telegram.xml.",
            **status,
        }), 400
    ok = telegram_notify.send_alert(
        telegram_notify.build_message("TEST TELEGRAM", ["Bot cảnh báo trade đang hoạt động."]),
    )
    if not ok:
        detail = telegram_notify.last_send_error() or "không rõ lỗi"
        return jsonify({
            "error": f"Gửi thất bại — {detail}",
            **status,
        }), 502
    return jsonify({"ok": True, **status})


def _should_start_watcher():
    # Không reloader: start ngay. Có reloader: chỉ process con (WERKZEUG_RUN_MAIN=true).
    if not USE_RELOADER:
        return True
    return os.environ.get("WERKZEUG_RUN_MAIN") == "true"


if __name__ == "__main__":
    if _should_start_watcher():
        watch.start_watcher(_lock)
        print(f"Đang chạy MT5 API tại http://{API_HOST}:{API_PORT} (chỉ localhost)")
        if SERVER_MODE:
            print("Chế độ server 24/7: watcher Timer + lệnh → Telegram (không Flask-reloader).")
        else:
            print("Auto-reload: sửa .py hoặc .xml → process restart và nạp lại nội dung.")

    app.run(
        host=API_HOST,
        port=API_PORT,
        threaded=True,
        use_reloader=USE_RELOADER,
        extra_files=_watch_extra_files() if USE_RELOADER else None,
    )
