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
#   hoặc start_api.bat
#   (mặc định lắng nghe tại http://127.0.0.1:5001, chỉ localhost, không expose
#   ra mạng ngoài vì có thao tác gửi lệnh thật + thông tin tài khoản)
#
# AUTO-RELOAD
#   - Sửa file .py hoặc bất kỳ file .xml trong project → process tự restart, nạp lại toàn bộ.
#   - Thêm lớp an toàn: mỗi request /api/accounts và /api/action vẫn kiểm tra mtime
#     xml/accounts.xml và nạp lại ngay nếu file đổi (không chờ reloader).
#
# ENDPOINT
#   GET  /api/accounts          -> danh sách account (không kèm password; có path)
#   POST /api/accounts          -> thêm account mới
#   PUT  /api/accounts/<name>   -> sửa cấu hình (không đổi login/password/server/name)
#   POST /api/reload-accounts   -> nạp lại xml/accounts.xml (ép buộc)
#   POST /api/action            -> thực thi action (status/open/close-all/modify-all)
#   GET  /api/history?limit=50  -> N dòng gần nhất trong history_mt5.txt
#
# Kết quả của /api/action trả về đúng nguyên văn các dòng print() của mt5.py
# (dạng text, giống output khi chạy CLI), để hiển thị trực tiếp trên web.
#
# =============================================================================

import contextlib
import io
import os
import threading
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

import mt5 as mt5app

API_HOST = "127.0.0.1"
API_PORT = 5001
ROOT_DIR = Path(__file__).resolve().parent

app = Flask(__name__)
CORS(app)

# mt5.py giữ state toàn cục (NO_ASK, CURRENT_ACCOUNT_NAME, kết nối MT5 đang mở),
# nên phải serialize mọi lệnh gọi vào đó để 2 request web không chạy song song.
_lock = threading.Lock()


def _watch_extra_files():
    """Mọi .py (root) và mọi .xml trong project — đổi là reloader restart process."""
    watched = {p.resolve() for p in ROOT_DIR.glob("*.py") if p.is_file()}
    watched.update(p.resolve() for p in ROOT_DIR.rglob("*.xml") if p.is_file())
    # Luôn theo dõi accounts.xml kể cả lúc chưa tồn tại (tạo sau khi API đã chạy).
    watched.add((ROOT_DIR / "xml" / "accounts.xml").resolve())
    return [str(p) for p in sorted(watched)]


def _account_public(acc):
    """Thông tin account an toàn để trả cho web, KHÔNG bao gồm password."""
    return {
        "name": acc.get("name"),
        "login": acc.get("login"),
        "server": acc.get("server"),
        "path": acc.get("path") or "",
        "suffix": acc.get("suffix"),
        "multi": acc.get("multi"),
        "xauusd_max_loss": acc.get("xauusd_max_loss"),
        "auto_copy_enabled": acc.get("auto_copy_enabled"),
        "auto_copy_targets": acc.get("auto_copy_targets"),
    }


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
        "path", "suffix", "multi", "xauusd_max_loss",
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
        path = data.get("path")
        fields["path"] = (str(path).strip() if path not in (None, "") else None)
    if "suffix" in data:
        fields["suffix"] = str(data.get("suffix") or "")
    if "multi" in data:
        fields["multi"] = _to_float(data.get("multi"), "multi", default=1.0)
    if "xauusd_max_loss" in data:
        fields["xauusd_max_loss"] = _to_float_or_none(data.get("xauusd_max_loss"), "xauusd_max_loss")
    if "auto_copy_enabled" in data:
        fields["auto_copy_enabled"] = bool(data.get("auto_copy_enabled"))
    if "auto_copy_targets" in data:
        fields["auto_copy_targets"] = _parse_auto_copy_targets(data.get("auto_copy_targets"))
    return fields


def _find_account_index(name):
    for idx, acc in enumerate(mt5app.ACCOUNTS):
        if acc.get("name") == name:
            return idx
    return None


@app.get("/api/accounts")
def get_accounts():
    with _lock:
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
            "path", "suffix", "multi", "xauusd_max_loss",
            "auto_copy_enabled", "auto_copy_targets",
        )
        if k in data
    }
    try:
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
        lot = float(data.get("lot", 0.01))
        tp_price = _to_float_or_none(data.get("tp_price"), "tp_price")
        sl_price = _to_float_or_none(data.get("sl_price"), "sl_price")
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

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
                )
        except Exception as exc:
            print(f"Lỗi: {exc}", file=buf)

    return jsonify({"output": buf.getvalue()})


@app.get("/api/history")
def history_endpoint():
    limit = request.args.get("limit", default=50, type=int)
    if not mt5app.HISTORY_FILE.exists():
        return jsonify({"lines": []})

    text = mt5app.HISTORY_FILE.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    return jsonify({"lines": lines[:limit]})


if __name__ == "__main__":
    # Process mẹ của reloader có WERKZEUG_RUN_MAIN=false — bỏ qua banner trùng.
    if os.environ.get("WERKZEUG_RUN_MAIN") != "false":
        print(f"Đang chạy MT5 API tại http://{API_HOST}:{API_PORT} (chỉ localhost)")
        print("Auto-reload: sửa .py hoặc .xml → process restart và nạp lại nội dung.")

    app.run(
        host=API_HOST,
        port=API_PORT,
        threaded=True,
        use_reloader=True,
        extra_files=_watch_extra_files(),
    )
