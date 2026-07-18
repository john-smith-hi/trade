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
#   (mặc định lắng nghe tại http://127.0.0.1:5001, chỉ localhost, không expose
#   ra mạng ngoài vì có thao tác gửi lệnh thật + thông tin tài khoản)
#
# ENDPOINT
#   GET  /api/accounts          -> danh sách account (không kèm password)
#   POST /api/reload-accounts   -> nạp lại xml/accounts.xml (sau khi sửa tay)
#   POST /api/action            -> thực thi action (status/open/close-all/modify-all)
#   GET  /api/history?limit=50  -> N dòng gần nhất trong history_mt5.txt
#
# Kết quả của /api/action trả về đúng nguyên văn các dòng print() của mt5.py
# (dạng text, giống output khi chạy CLI), để hiển thị trực tiếp trên web.
#
# =============================================================================

import contextlib
import io
import threading

from flask import Flask, jsonify, request
from flask_cors import CORS

import mt5 as mt5app

API_HOST = "127.0.0.1"
API_PORT = 5001

app = Flask(__name__)
CORS(app)

# mt5.py giữ state toàn cục (NO_ASK, CURRENT_ACCOUNT_NAME, kết nối MT5 đang mở),
# nên phải serialize mọi lệnh gọi vào đó để 2 request web không chạy song song.
_lock = threading.Lock()


def _account_public(acc):
    """Thông tin account an toàn để trả cho web, KHÔNG bao gồm password."""
    return {
        "name": acc.get("name"),
        "login": acc.get("login"),
        "server": acc.get("server"),
        "suffix": acc.get("suffix"),
        "multi": acc.get("multi"),
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


@app.get("/api/accounts")
def get_accounts():
    return jsonify({"accounts": [_account_public(acc) for acc in mt5app.ACCOUNTS]})


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

    symbol = data.get("symbol") or "BTCUSD"
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
    print(f"Đang chạy MT5 API tại http://{API_HOST}:{API_PORT} (chỉ localhost)")
    app.run(host=API_HOST, port=API_PORT, threaded=True)
