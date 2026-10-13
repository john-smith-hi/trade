# =============================================================================
# HƯỚNG DẪN SỬ DỤNG
# =============================================================================
#
# CÀI ĐẶT
#   python -m pip install MetaTrader5 pandas
#
# CẤU HÌNH TÀI KHOẢN (file xml/accounts.xml, KHÔNG còn để trong code)
#   - File xml/accounts.xml chứa danh sách tài khoản. Nếu chưa có, script sẽ
#     tự tạo từ xml/accounts.example.xml (dữ liệu mẫu) khi chạy lần đầu.
#   - Sửa trực tiếp file này bằng tay (Notepad/VS Code...) để thêm/sửa/xóa tài khoản.
#   - name   : tên account dùng trong --account.
#   - path   : TÊN path trong xml/paths.xml (vd: exness, ftmo) — không ghi full path.
#   - Đường dẫn terminal64.exe khai báo trong xml/paths.xml (name + exe).
#   - suffix : hậu tố symbol theo broker — Exness = "m", FTMO = "".
#              Ví dụ --symbol XAUUSD → XAUUSDm (Exness) hoặc XAUUSD (FTMO).
#   - multi  : hệ số nhân lot khi copy lệnh sang tài khoản đó.
#   - default_lot : lot mặc định trên web khi để trống ô Lot (bỏ trống = 0.01).
#   - xauusd_max_loss : |ước tính lỗ SL| tối đa cho XAUUSD (bỏ trống = không giới hạn).
#     Khi copy: account đích bỏ trống thì lấy xauusd_max_loss của account gốc × multi.
#   - auto_copy_enabled/auto_copy_targets : bật thì account đó sẽ TỰ ĐỘNG copy
#     lệnh sang các account trong auto_copy_targets mỗi khi chạy (không cần
#     truyền --copy). Ví dụ: account "real" auto_copy_targets=prop_demo,prop_1.
#   - xml/accounts.xml chứa mật khẩu thật nên đã nằm trong .gitignore, không bị commit.
#   - Xem xml/accounts.example.xml để biết mẫu cấu trúc.
#
# THAM SỐ BẮT BUỘC
#   --account   tên account khai báo trong xml/accounts.xml (vd: fake, real, prop_demo)
#   --action    status | open | open-2-side | open-2-side-news-multi-auto | demo-open-2-side-news-multi-auto
#               | pending | cancel-pending | close | close-all | modify-all | modify-all-if | cancel-modify-if
#
# THAM SỐ KHÁC
#   --symbol --side --lot --tp-price --sl-price --price --pending-type --comment --copy --no-ask
#   (Không có --no-ask → chỉ xem trước, KHÔNG gửi lệnh thật.)
#   Với open / pending / modify: TP/SL là mức giá cụ thể (không phải số điểm).
#   action=open BẮT BUỘC --sl-price; --tp-price tùy chọn.
#     BUY : SL < giá mở (< TP nếu có)
#     SELL: (TP nếu có <) giá mở < SL
#   action=open-2-side: mở BUY và SELL thị trường cùng lúc. --side bị bỏ qua.
#     --sl-price / --tp-price là KHOẢNG CÁCH so với giá khớp, không phải mức giá.
#     Bắt buộc --sl-price > 0; --tp-price tùy chọn (bỏ trống = không đặt TP).
#     BUY khớp ở ask: SL = ask − SL, TP = ask + TP.
#     SELL khớp ở bid: SL = bid + SL, TP = bid − TP.
#     Ví dụ giá 4000, --sl-price 10 --tp-price 50:
#       BUY  SL 3990 TP 4050 | SELL SL 4010 TP 3950.
#   action=pending BẮT BUỘC --price (giá chờ) + --sl-price; --tp-price tùy chọn.
#     Limit/Stop tự chọn theo giá chờ so với thị trường (không bắt phải nhỏ/lớn hơn).
#     BUY:  giá < ask → LIMIT, còn lại STOP.
#     SELL: giá > bid → LIMIT, còn lại STOP.
#   action=modify-all-if: khi giá chạm vùng thì sửa SL/TP mọi lệnh mở cùng symbol.
#     Bắt buộc --sl-price; --tp-price tùy chọn; vùng = --price hoặc --zone-low/--zone-high.
#     Watcher (start_server.bat) poll tick ~30s. Lần poll đầu chỉ ghi nhận, không kích hoạt.
#   action=close: đóng một phần (hoặc hết) theo --lot, chỉ lệnh cùng --symbol + --side.
#     Lot copy = lot gốc × multi. Nếu --lot lớn hơn tổng đang mở thì đóng hết phần khớp.
#   action=cancel-modify-if: hủy mọi job modify-all-if đang chờ của account.
#   Không truyền --copy → tự dùng auto_copy_enabled/auto_copy_targets của account (nếu có).
#   Truyền --copy "tên1,tên2" → copy đúng danh sách này (override auto-copy).
#   Truyền --copy "" → tắt hẳn copy cho lần chạy đó (bỏ qua cả auto-copy).
#
# VÍ DỤ
#   # Xem trạng thái tài khoản
#   python mt5.py --account prop_demo --action status
#
#   # Mở lệnh (xem trước) — bắt buộc SL; TP tùy chọn, đúng hướng
#   python mt5.py --account fake --action open --symbol XAUUSD --side buy --lot 0.01 --sl-price 58000
#
#   # Mở lệnh thật (có cả TP)
#   python mt5.py --account fake --action open --symbol XAUUSD --side buy --lot 0.01 --tp-price 60000 --sl-price 58000 --no-ask
#
#   # Mua và bán cùng lúc. 10 và 50 là khoảng cách, không phải mức giá.
#   python mt5.py --account fake --action open-2-side --symbol XAUUSD --lot 0.01 --sl-price 10 --tp-price 50 --no-ask
#
#   # Hedge tin: lot tự tính từ MAX_RISK. Không --no-ask = xem trước, không bắn.
#   # --lot bị bỏ qua. Không copy. Không đóng đầu còn lại khi giá quay về mức đệm.
#   python mt5.py --account fake --action open-2-side-news-multi-auto --symbol XAUUSD --max-risk 375 --sl-pips 15 --buffer-pips 8 --max-exec-ms 300 --no-ask
#
#   # In kịch bản mẫu (Ask 4200 / Bid 4199). Không nối MT5, không gửi lệnh.
#   python mt5.py --account fake --action demo-open-2-side-news-multi-auto
#
#   # Đặt lệnh chờ mua (Buy Limit) tại giá
#   python mt5.py --account fake --action pending --symbol XAUUSD --side buy --pending-type limit --price 2500 --lot 0.01 --sl-price 2480 --no-ask
#
#   # Đặt lệnh chờ mua (Buy Stop) khi giá phá lên
#   python mt5.py --account fake --action pending --symbol XAUUSD --side buy --pending-type stop --price 2600 --lot 0.01 --tp-price 2650 --sl-price 2580 --no-ask
#
#   # Hủy toàn bộ lệnh chờ
#   python mt5.py --account fake --action cancel-pending --no-ask
#
#   # Sửa TP/SL tất cả lệnh đang mở (hiện ước tính lời/lỗ so giá mở)
#   python mt5.py --account fake --action modify-all --tp-price 60000 --sl-price 58000 --no-ask
#
#   # Khi giá chạm 3400 thì sửa SL/TP mọi lệnh XAUUSD đang mở (cần API watcher)
#   python mt5.py --account fake --action modify-all-if --symbol XAUUSD --price 3400 --sl-price 3380 --tp-price 3450 --no-ask
#
#   # Hủy job modify-all-if đang chờ
#   python mt5.py --account fake --action cancel-modify-if --no-ask
#
#   # Đóng một phần 0.01 lot BUY XAUUSD (giữ phần còn lại)
#   python mt5.py --account fake --action close --symbol XAUUSD --side buy --lot 0.01 --no-ask
#
#   # Đóng toàn bộ lệnh (hiện P/L hiện tại từng lệnh + tổng)
#   python mt5.py --account fake --action close-all --no-ask
#
#   # Copy lệnh từ real sang prop (lot prop = lot gốc × multi), chỉ định thủ công
#   python mt5.py --account real --action open --symbol XAUUSD --side buy --lot 0.01 --tp-price 60000 --sl-price 58000 --copy prop_demo --no-ask
#
#   # Account "real" đã cấu hình auto_copy_targets=prop_demo,prop_1 -> không cần --copy,
#   # lệnh sẽ tự copy sang cả prop_demo và prop_1
#   python mt5.py --account real --action open --symbol XAUUSD --side buy --lot 0.01 --tp-price 60000 --sl-price 58000 --no-ask
#
# LỊCH SỬ
#   Mỗi lần gửi lệnh sẽ ghi vào history_mt5.txt (mới nhất ở đầu file).
#
# =============================================================================

import argparse
import math
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

import MetaTrader5 as mt5

import modify_if

# Console Windows (PowerShell/cmd) thường dùng codepage cp1252/cp850, không encode được
# tiếng Việt có dấu -> ép stdout/stderr sang UTF-8 để tránh crash khi print() thông báo lỗi.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HISTORY_FILE = Path(__file__).with_name("history_mt5.txt")
XML_DIR = Path(__file__).with_name("xml")
ACCOUNTS_FILE = XML_DIR / "accounts.xml"
ACCOUNTS_EXAMPLE_FILE = XML_DIR / "accounts.example.xml"
PATHS_FILE = XML_DIR / "paths.xml"
PATHS_EXAMPLE_FILE = XML_DIR / "paths.example.xml"

COPYABLE_ACTIONS = {
    "open", "open-2-side", "pending", "cancel-pending", "close", "close-all", "modify-all",
    "modify-all-if", "cancel-modify-if",
}
PENDING_TYPES = {"limit", "stop"}
ORDER_TYPE_LABELS = {
    0: "BUY",
    1: "SELL",
    2: "BUY_LIMIT",
    3: "SELL_LIMIT",
    4: "BUY_STOP",
    5: "SELL_STOP",
    6: "BUY_STOP_LIMIT",
    7: "SELL_STOP_LIMIT",
}
NO_ASK = False
TELEGRAM_IS_COPY = False
DEFAULT_MAGIC = 234567
NEWS_HEDGE_MAGIC = 234568
NEWS_HEDGE_ACTION = "open-2-side-news-multi-auto"
NEWS_HEDGE_DEMO_ACTION = "demo-open-2-side-news-multi-auto"
_NEWS_HISTORY_QUEUE = []
DEFAULT_DEVIATION = 20
CURRENT_ACCOUNT_NAME = None
# Giới hạn XAUUSD đang áp dụng cho action hiện tại (None = không giới hạn).
# Dùng object() làm sentinel để phân biệt "chưa set" vs "không giới hạn".
_UNSET_MAX_LOSS = object()
_ACTIVE_XAUUSD_MAX_LOSS = _UNSET_MAX_LOSS


def _xml_text(node, tag, default=""):
    child = node.find(tag)
    if child is None or child.text is None:
        return default
    return child.text.strip()


def _xml_bool(node, tag, default=False):
    text = _xml_text(node, tag, "").lower()
    if not text:
        return default
    return text in ("1", "true", "yes", "on")


def _xml_list(node, tag):
    text = _xml_text(node, tag, "")
    return [item.strip() for item in text.split(",") if item.strip()]


def _default_paths():
    return [
        {
            "name": "exness",
            "exe": r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe",
        },
        {
            "name": "ftmo",
            "exe": r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe",
        },
    ]


def load_paths():
    """Đọc danh sách path (name → exe) từ xml/paths.xml."""
    XML_DIR.mkdir(parents=True, exist_ok=True)
    if not PATHS_FILE.exists():
        if PATHS_EXAMPLE_FILE.exists():
            PATHS_FILE.write_text(PATHS_EXAMPLE_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            save_paths(_default_paths())

    try:
        root = ET.parse(PATHS_FILE).getroot()
    except ET.ParseError as exc:
        raise RuntimeError(f"File paths.xml bị lỗi định dạng: {exc}")

    paths = []
    for node in root.findall("path"):
        name = _xml_text(node, "name").lower()
        exe = _xml_text(node, "exe")
        if not name:
            continue
        paths.append({"name": name, "exe": exe})
    if not paths:
        paths = _default_paths()
        save_paths(paths)
    return paths


def save_paths(paths):
    """Ghi danh sách path ra xml/paths.xml."""
    XML_DIR.mkdir(parents=True, exist_ok=True)
    root = ET.Element("paths")
    for item in paths:
        node = ET.SubElement(root, "path")
        ET.SubElement(node, "name").text = str(item.get("name", "")).strip().lower()
        ET.SubElement(node, "exe").text = str(item.get("exe") or "")
    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")
    tree.write(PATHS_FILE, encoding="UTF-8", xml_declaration=True)


def load_accounts():
    """Đọc danh sách tài khoản từ accounts.xml.

    Nếu accounts.xml chưa tồn tại, tự tạo từ accounts.example.xml (hoặc file rỗng
    nếu không có mẫu) để lần đầu chạy không bị lỗi thiếu file.

    Trường path trên account là TÊN path trong paths.xml (vd: exness, ftmo).
    """
    XML_DIR.mkdir(parents=True, exist_ok=True)
    if not ACCOUNTS_FILE.exists():
        if ACCOUNTS_EXAMPLE_FILE.exists():
            ACCOUNTS_FILE.write_text(ACCOUNTS_EXAMPLE_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            save_accounts([])

    try:
        root = ET.parse(ACCOUNTS_FILE).getroot()
    except ET.ParseError as exc:
        raise RuntimeError(f"File accounts.xml bị lỗi định dạng: {exc}")

    accounts = []
    for node in root.findall("account"):
        name = _xml_text(node, "name")
        if not name:
            continue

        try:
            login = int(_xml_text(node, "login", "0") or "0")
        except ValueError:
            login = 0

        multi_text = _xml_text(node, "multi")
        try:
            multi = float(multi_text) if multi_text else 1.0
        except ValueError:
            multi = 1.0

        default_lot_text = _xml_text(node, "default_lot")
        try:
            default_lot = float(default_lot_text) if default_lot_text else 0.01
        except ValueError:
            default_lot = 0.01
        if default_lot <= 0:
            default_lot = 0.01

        max_loss_text = _xml_text(node, "xauusd_max_loss")
        # Bỏ trống = không giới hạn (None).
        xauusd_max_loss = None
        if max_loss_text:
            try:
                xauusd_max_loss = float(max_loss_text)
            except ValueError:
                xauusd_max_loss = None

        path_ref = _xml_text(node, "path") or None
        if path_ref:
            path_ref = path_ref.strip()
            # Chuẩn hóa tên path về chữ thường nếu không phải legacy full path.
            if not _looks_like_filesystem_path(path_ref):
                path_ref = path_ref.lower()

        accounts.append({
            "name": name,
            "login": login,
            "password": _xml_text(node, "password"),
            "server": _xml_text(node, "server"),
            "path": path_ref,
            "suffix": _xml_text(node, "suffix"),
            "multi": multi,
            "default_lot": default_lot,
            "xauusd_max_loss": xauusd_max_loss,
            "auto_copy_enabled": _xml_bool(node, "auto_copy_enabled", False),
            "auto_copy_targets": _xml_list(node, "auto_copy_targets"),
        })
    return accounts


def save_accounts(accounts):
    """Ghi danh sách tài khoản (list[dict]) ra xml/accounts.xml."""
    XML_DIR.mkdir(parents=True, exist_ok=True)
    root = ET.Element("accounts")
    for acc in accounts:
        node = ET.SubElement(root, "account")
        ET.SubElement(node, "name").text = str(acc.get("name", ""))
        ET.SubElement(node, "login").text = str(acc.get("login", 0))
        ET.SubElement(node, "password").text = str(acc.get("password", ""))
        ET.SubElement(node, "server").text = str(acc.get("server", ""))
        path_ref = acc.get("path") or ""
        if path_ref and not _looks_like_filesystem_path(str(path_ref)):
            path_ref = str(path_ref).strip().lower()
        ET.SubElement(node, "path").text = str(path_ref)
        ET.SubElement(node, "suffix").text = str(acc.get("suffix", ""))
        ET.SubElement(node, "multi").text = str(acc.get("multi", 1.0))
        default_lot = acc.get("default_lot")
        ET.SubElement(node, "default_lot").text = "" if default_lot is None else str(default_lot)
        max_loss = acc.get("xauusd_max_loss")
        ET.SubElement(node, "xauusd_max_loss").text = "" if max_loss is None else str(max_loss)
        ET.SubElement(node, "auto_copy_enabled").text = "true" if acc.get("auto_copy_enabled") else "false"
        ET.SubElement(node, "auto_copy_targets").text = ",".join(acc.get("auto_copy_targets") or [])

    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")
    tree.write(ACCOUNTS_FILE, encoding="UTF-8", xml_declaration=True)


def _looks_like_filesystem_path(value):
    text = str(value or "")
    return ("\\" in text) or ("/" in text) or text.lower().endswith(".exe")


PATHS = load_paths()
ACCOUNTS = load_accounts()


def _paths_file_mtime():
    try:
        return PATHS_FILE.stat().st_mtime
    except OSError:
        return None


def _accounts_file_mtime():
    try:
        return ACCOUNTS_FILE.stat().st_mtime
    except OSError:
        return None


_paths_mtime = _paths_file_mtime()
_accounts_mtime = _accounts_file_mtime()


def reload_paths():
    """Nạp lại PATHS từ paths.xml."""
    global PATHS, _paths_mtime
    PATHS = load_paths()
    _paths_mtime = _paths_file_mtime()
    return PATHS


def ensure_paths_fresh():
    """Nếu paths.xml đổi trên đĩa thì nạp lại. Trả True nếu đã reload."""
    global PATHS, _paths_mtime
    mtime = _paths_file_mtime()
    if mtime == _paths_mtime:
        return False
    PATHS = load_paths()
    _paths_mtime = _paths_file_mtime()
    return True


def get_path_entry(path_name):
    """Lấy cấu hình path theo name (vd: exness, ftmo)."""
    key = str(path_name or "").strip().lower()
    for item in PATHS:
        if item.get("name") == key:
            return item
    raise RuntimeError(f"Không tìm thấy path tên: {path_name}")


def resolve_terminal_path(account):
    """Từ account.path (tên trong paths.xml) → đường dẫn exe thật.

    Hỗ trợ legacy: nếu path vẫn là full path (.exe / có \\) thì dùng trực tiếp.
    """
    path_ref = account.get("path")
    if not path_ref:
        return None
    path_ref = str(path_ref).strip()
    if not path_ref:
        return None
    if _looks_like_filesystem_path(path_ref):
        return path_ref
    entry = get_path_entry(path_ref)
    exe = (entry.get("exe") or "").strip()
    if not exe:
        raise RuntimeError(
            f"Path '{path_ref}' chưa có exe trong paths.xml. "
            f"Vào trang Accounts → Cấu hình path để điền terminal64.exe."
        )
    if "CHANGE_ME" in exe:
        raise RuntimeError(
            f"Path '{path_ref}' chưa cấu hình exe thật (còn CHANGE_ME)."
        )
    return exe


def reload_accounts():
    """Nạp lại ACCOUNTS từ accounts.xml (dùng sau khi sửa file hoặc lưu qua GUI)."""
    global ACCOUNTS, _accounts_mtime
    ensure_paths_fresh()
    ACCOUNTS = load_accounts()
    _accounts_mtime = _accounts_file_mtime()
    return ACCOUNTS


def ensure_accounts_fresh():
    """Nếu accounts.xml đổi trên đĩa thì nạp lại vào bộ nhớ. Trả True nếu đã reload."""
    global ACCOUNTS, _accounts_mtime
    ensure_paths_fresh()
    mtime = _accounts_file_mtime()
    if mtime == _accounts_mtime:
        return False
    ACCOUNTS = load_accounts()
    _accounts_mtime = _accounts_file_mtime()
    return True


def get_account(account_name):
    for acc in ACCOUNTS:
        if acc["name"] == account_name:
            return acc
    raise RuntimeError(f"Không tìm thấy cấu hình account tên: {account_name}")


def get_account_multi(account):
    return account.get("multi", 1.0)


def _optional_max_loss(value):
    """None / rỗng = không giới hạn; số hợp lệ = giới hạn."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_xauusd_max_loss(account=None):
    """Lấy giới hạn lỗ XAUUSD. Trả None nếu không cấu hình (không giới hạn)."""
    if account is not None:
        return _optional_max_loss(account.get("xauusd_max_loss"))
    if _ACTIVE_XAUUSD_MAX_LOSS is not _UNSET_MAX_LOSS:
        return _optional_max_loss(_ACTIVE_XAUUSD_MAX_LOSS)
    if CURRENT_ACCOUNT_NAME:
        try:
            return _optional_max_loss(get_account(CURRENT_ACCOUNT_NAME).get("xauusd_max_loss"))
        except RuntimeError:
            return None
    return None


def resolve_copy_xauusd_max_loss(copy_account, primary_account):
    """Giới hạn khi copy: dùng của account đích nếu có; không thì gốc × multi; gốc trống → None."""
    own = _optional_max_loss(copy_account.get("xauusd_max_loss"))
    if own is not None:
        return own
    primary = _optional_max_loss(primary_account.get("xauusd_max_loss"))
    if primary is None:
        return None
    return primary * get_account_multi(copy_account)


def get_auto_copy_targets(account):
    """Danh sách tài khoản tự động copy lệnh sang, cấu hình theo từng account
    trong xml/accounts.xml (auto_copy_enabled + auto_copy_targets)."""
    if not account.get("auto_copy_enabled"):
        return []
    return list(account.get("auto_copy_targets") or [])


def save_trade_history(symbol, lot, result, request, status, detail="", profit=None, position=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ticket = getattr(result, "order", None)
    retcode = getattr(result, "retcode", None)

    entry = (
        f"{timestamp} | account={CURRENT_ACCOUNT_NAME or '-'} | symbol={symbol} | lot={lot} | status={status} | "
        f"ticket={ticket if ticket is not None else '-'} | "
        f"retcode={retcode if retcode is not None else '-'} | "
        f"comment={request.get('comment', '')}"
    )
    if detail:
        entry += f" | detail={detail}"

    existing_content = ""
    if HISTORY_FILE.exists():
        existing_content = HISTORY_FILE.read_text(encoding="utf-8").strip()

    if existing_content:
        new_content = f"{entry}\n{existing_content}"
    else:
        new_content = entry

    HISTORY_FILE.write_text(new_content + "\n", encoding="utf-8")
    _notify_trade_telegram(symbol, lot, result, request, status, detail, profit=profit, position=position)


def _request_side_label(request, position=None):
    if position is not None:
        pos_type = int(getattr(position, "type", -1))
        if pos_type == mt5.ORDER_TYPE_BUY:
            return "BUY"
        if pos_type == mt5.ORDER_TYPE_SELL:
            return "SELL"
    order_type = request.get("type") if isinstance(request, dict) else None
    if order_type is None:
        return ""
    return ORDER_TYPE_LABELS.get(int(order_type), "")


def _recent_deal_for_order(order_ticket, position_ticket=None, entry=None):
    if order_ticket is None and position_ticket is None:
        return None
    try:
        deals = mt5.history_deals_get(datetime.now() - timedelta(minutes=3), datetime.now())
    except Exception:
        return None
    if not deals:
        return None
    want_order = int(order_ticket) if order_ticket not in (None, "") else None
    want_pos = int(position_ticket) if position_ticket not in (None, "") else None
    for deal in reversed(deals):
        if want_order is not None and int(getattr(deal, "order", 0) or 0) != want_order:
            if want_pos is None or int(getattr(deal, "position_id", 0) or 0) != want_pos:
                continue
        elif want_order is None and want_pos is not None:
            if int(getattr(deal, "position_id", 0) or 0) != want_pos:
                continue
        if entry is not None and int(getattr(deal, "entry", -1)) != entry:
            continue
        return deal
    return None


# Status lệnh thành công → Telegram + cập nhật watch_state.
_TELEGRAM_OK = {"SUCCESS", "PENDING_SUCCESS", "CLOSE_SUCCESS", "MODIFY_SUCCESS"}
# Terminal không thực hiện được (retcode lỗi / không phản hồi) → Telegram cảnh báo.
_TELEGRAM_FAIL = {
    "FAILED": "LỖI MỞ LỆNH",
    "PENDING_FAILED": "LỖI ĐẶT LỆNH CHỜ",
    "CANCEL_PENDING_FAILED": "LỖI HỦY LỆNH CHỜ",
    "CLOSE_FAILED": "LỖI ĐÓNG LỆNH",
    "MODIFY_FAILED": "LỖI SỬA TP/SL",
}


def _notify_trade_telegram(symbol, lot, result, request, status, detail, profit=None, position=None):
    """Cảnh báo ngay sau lệnh do web/CLI/copy thực hiện. Lỗi Telegram không raise."""
    if status not in _TELEGRAM_OK and status not in _TELEGRAM_FAIL:
        return
    try:
        import telegram_notify
        import watch_state
    except Exception:
        return

    account = CURRENT_ACCOUNT_NAME or "-"
    order_ticket = getattr(result, "order", None) if result is not None else None
    pos_ticket = getattr(position, "ticket", None) if position is not None else None
    side = _request_side_label(request, position)
    prefix = "[COPY] " if TELEGRAM_IS_COPY else ""
    lines = [
        f"account: {account}",
        f"{symbol} {side} {lot}".strip(),
    ]

    if status in _TELEGRAM_FAIL:
        title = f"{prefix}{_TELEGRAM_FAIL[status]}"
        retcode = getattr(result, "retcode", None) if result is not None else None
        term_comment = getattr(result, "comment", None) if result is not None else None
        if retcode is not None:
            lines.append(f"retcode: {retcode}")
        if term_comment:
            lines.append(f"terminal: {term_comment}")
        if detail:
            lines.append(detail)
        if pos_ticket is not None:
            lines.append(f"ticket: {pos_ticket}")
        elif order_ticket is not None:
            lines.append(f"ticket: {order_ticket}")

    elif status == "SUCCESS":
        title = f"{prefix}MỞ LỆNH"
        price = request.get("price") if isinstance(request, dict) else None
        if price not in (None, ""):
            lines.append(f"giá: {price}")
        lines.append(f"ticket: {order_ticket if order_ticket is not None else '-'}")
        deal = _recent_deal_for_order(order_ticket, entry=getattr(mt5, "DEAL_ENTRY_IN", 0))
        if deal is not None:
            watch_state.remember_deal(getattr(deal, "ticket", None))
        watch_state.remember_skip_open_order(order_ticket)

    elif status == "PENDING_SUCCESS":
        title = f"{prefix}ĐẶT LỆNH CHỜ"
        if detail:
            lines.append(detail)
        lines.append(f"ticket: {order_ticket if order_ticket is not None else '-'}")
        watch_state.add_pending_ticket(account, order_ticket)

    elif status == "MODIFY_SUCCESS":
        title = f"{prefix}SỬA TP/SL"
        sl = request.get("sl") if isinstance(request, dict) else None
        tp = request.get("tp") if isinstance(request, dict) else None
        try:
            sl_n = float(sl) if sl is not None else 0.0
        except (TypeError, ValueError):
            sl_n = 0.0
        try:
            tp_n = float(tp) if tp is not None else 0.0
        except (TypeError, ValueError):
            tp_n = 0.0
        lines.append(f"SL: {sl_n if sl_n > 0 else 'không đặt'}")
        lines.append(f"TP: {tp_n if tp_n > 0 else 'không đặt'}")
        lines.append(f"ticket: {pos_ticket if pos_ticket is not None else '-'}")

    else:
        req_vol = None
        if isinstance(request, dict) and request.get("volume") is not None:
            try:
                req_vol = float(request.get("volume"))
            except (TypeError, ValueError):
                req_vol = None
        pos_vol = float(getattr(position, "volume", 0) or 0) if position is not None else 0.0
        if req_vol is not None and pos_vol > 0 and req_vol + 1e-12 < pos_vol:
            title = f"{prefix}ĐÓNG MỘT PHẦN"
        else:
            title = f"{prefix}ĐÓNG LỆNH (tay)"
        lines.append(f"ticket: {pos_ticket if pos_ticket is not None else order_ticket}")
        deal = _recent_deal_for_order(
            order_ticket,
            position_ticket=pos_ticket,
            entry=getattr(mt5, "DEAL_ENTRY_OUT", 1),
        )
        pnl = profit
        if deal is not None:
            pnl = getattr(deal, "profit", pnl)
            watch_state.remember_deal(getattr(deal, "ticket", None))
        pnl_text = telegram_notify.format_pnl(pnl)
        if pnl_text:
            lines.append(f"P/L: {pnl_text}")

    try:
        telegram_notify.send_alert(telegram_notify.build_message(title, lines))
    except Exception:
        pass


def confirm_action(message):
    """Xác nhận hành động. Không có --no-ask → chỉ xem trước, KHÔNG gửi lệnh thật.
    Các bước in thông tin / ước tính lời-lỗ phía trước vẫn luôn chạy.
    """
    if NO_ASK:
        return True
    print(f"[XEM TRƯỚC] {message}")
    print("[XEM TRƯỚC] Chưa truyền --no-ask nên KHÔNG có lệnh nào được thực thi thật (kể cả copy).")
    return False


def connect_mt5(account, quiet=False, timeout_ms=None):
    global CURRENT_ACCOUNT_NAME

    terminal_path = resolve_terminal_path(account)

    # Ngắt phiên MT5 cũ trước khi gắn terminal khác (Exness -> FTMO Demo -> FTMO Server).
    # Nếu không shutdown, tick/symbol có thể còn cache từ terminal trước -> giá vào sai.
    mt5.shutdown()

    # Watcher/quiet: timeout ngắn để không giữ API lock quá lâu.
    if timeout_ms is None:
        timeout_ms = 8000 if quiet else 60000

    # Với các broker/prop-firm khác (VD: FTMO), phải chỉ định path tới terminal MT5 riêng của họ,
    # vì terminal MT5 mặc định (thường là bản Exness) không có server tương ứng nên sẽ bị IPC timeout.
    init_kwargs = {
        "login": account["login"],
        "password": account["password"],
        "server": account["server"],
        "timeout": int(timeout_ms),
    }
    if terminal_path:
        init_kwargs["path"] = terminal_path

    if not mt5.initialize(**init_kwargs):
        raise RuntimeError(f"Không thể kết nối vào MT5, lỗi: {mt5.last_error()}")

    if mt5.terminal_info() is None:
        mt5.shutdown()
        raise RuntimeError("MetaTrader 5 chưa mở hoặc không thể lấy thông tin.")

    login_success = mt5.login(login=account["login"], password=account["password"], server=account["server"])
    if not login_success:
        mt5.shutdown()
        raise RuntimeError(f"Đăng nhập thất bại, mã lỗi: {mt5.last_error()}")

    account_info = mt5.account_info()
    if account_info is None or account_info.login != account["login"]:
        mt5.shutdown()
        raise RuntimeError(
            f"Sau khi đăng nhập, terminal không khớp account '{account['name']}' "
            f"(mong đợi login {account['login']}). Kiểm tra path '{account.get('path')}' trong paths.xml."
        )

    CURRENT_ACCOUNT_NAME = account["name"]
    path_ref = account.get("path") or "(mặc định)"
    terminal_label = terminal_path or "(terminal mặc định đang chạy)"
    if not quiet:
        print(f"Đang sử dụng tài khoản {account['name']}: {account['login']} | server: {account['server']}")
        print(f"Path config: {path_ref} → {terminal_label}")
        print("Đăng nhập MT5 thành công!")


def resolve_symbol_for_account(symbol, account):
    """Tự thêm/bỏ hậu tố symbol (VD: "m" của Exness) theo account đang chạy."""
    base = symbol[:-1] if symbol.endswith("m") else symbol
    return f"{base}{account.get('suffix', '')}"


def select_symbol(symbol, account):
    resolved = resolve_symbol_for_account(symbol, account)
    if mt5.symbol_select(resolved, True):
        return resolved
    raise RuntimeError(f"Không tìm thấy symbol nào phù hợp: {resolved}")


def get_current_price(symbol, retries=10, delay=0.3):
    """Lấy tick mới sau khi chọn symbol; retry để tránh dùng giá cache khi vừa chuyển terminal."""
    if not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"Không thể chọn symbol {symbol}")

    last_tick = None
    for attempt in range(retries):
        tick = mt5.symbol_info_tick(symbol)
        if tick is not None and tick.bid > 0 and tick.ask > 0 and tick.ask >= tick.bid:
            last_tick = tick
            # Đọc ít nhất 2 lần, lần sau cùng thường là feed mới sau khi chuyển terminal.
            if attempt >= 1:
                return tick
        time.sleep(delay)

    if last_tick is not None:
        return last_tick
    raise RuntimeError(f"Không lấy được tick hợp lệ cho symbol {symbol}")


def get_entry_price(symbol, side):
    tick = get_current_price(symbol)
    return tick.ask if side == "buy" else tick.bid


def estimate_tp_sl_pnl(side, entry_price, tp_price, sl_price, volume, contract_size):
    """Ước tính lời/lỗ tại mức TP/SL theo (chênh giá × lot × contract_size)."""
    estimated = {}
    side_l = (side or "").lower()
    if tp_price is not None:
        if side_l == "buy":
            estimated["tp"] = (float(tp_price) - float(entry_price)) * float(volume) * float(contract_size)
        else:
            estimated["tp"] = (float(entry_price) - float(tp_price)) * float(volume) * float(contract_size)
    if sl_price is not None:
        if side_l == "buy":
            estimated["sl"] = (float(sl_price) - float(entry_price)) * float(volume) * float(contract_size)
        else:
            estimated["sl"] = (float(entry_price) - float(sl_price)) * float(volume) * float(contract_size)
    return estimated


def is_xauusd_symbol(symbol):
    """Nhận XAUUSD và biến thể có hậu tố broker (vd: XAUUSDm)."""
    if not symbol:
        return False
    base = symbol[:-1] if symbol.endswith("m") else symbol
    return base.upper() == "XAUUSD"


def validate_xauusd_max_loss(symbol, side, entry_price, sl_price, volume, account=None):
    """Với XAUUSD: ước tính lỗ tại SL không được lớn hơn xauusd_max_loss.
    Không cấu hình xauusd_max_loss → bỏ qua (không giới hạn).
    """
    if sl_price is None or not is_xauusd_symbol(symbol):
        return

    max_loss = get_xauusd_max_loss(account)
    if max_loss is None:
        return

    contract_size = resolve_contract_size(symbol)
    estimated = estimate_tp_sl_pnl(side, entry_price, None, sl_price, volume, contract_size)
    sl_pnl = estimated.get("sl")
    if sl_pnl is None:
        return

    loss_amount = abs(sl_pnl) if sl_pnl < 0 else 0.0
    if loss_amount > max_loss:
        raise RuntimeError(
            f"Symbol {symbol}: ước tính lỗ SL={sl_pnl:.8f} vượt giới hạn {max_loss} "
            f"(|lỗ|={loss_amount:.8f} > {max_loss}, cấu hình xauusd_max_loss trong accounts.xml)"
        )


def resolve_contract_size(symbol):
    """Lấy contract size; ưu tiên trade_contract_size, fallback tick_value/tick_size."""
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        return 1.0

    contract_size = getattr(symbol_info, "trade_contract_size", None)
    if contract_size and contract_size > 0:
        return float(contract_size)

    tick_size = getattr(symbol_info, "trade_tick_size", None) or getattr(symbol_info, "point", None)
    tick_value = getattr(symbol_info, "trade_tick_value", None)
    if tick_size and tick_value and tick_size > 0:
        return float(tick_value) / float(tick_size)

    return 1.0


def collect_tp_sl_warnings(side, entry_price, tp_price=None, sl_price=None):
    """Trả về list cảnh báo khi TP/SL ngược hướng so với side + giá vào."""
    warnings = []
    side_l = (side or "").lower()
    entry = float(entry_price)

    if tp_price is not None:
        tp = float(tp_price)
        if tp <= 0:
            warnings.append(f"TP={tp} không hợp lệ (phải > 0)")
        elif side_l == "buy" and tp <= entry:
            warnings.append(
                f"TP={tp} bất thường với lệnh BUY: phải LỚN HƠN giá vào {entry} "
                f"(hiện TP đang thấp hơn → chốt lời sẽ thành lỗ)"
            )
        elif side_l == "sell" and tp >= entry:
            warnings.append(
                f"TP={tp} bất thường với lệnh SELL: phải NHỎ HƠN giá vào {entry} "
                f"(hiện TP đang cao hơn → chốt lời sẽ thành lỗ)"
            )

    if sl_price is not None:
        sl = float(sl_price)
        if sl <= 0:
            warnings.append(f"SL={sl} không hợp lệ (phải > 0)")
        elif side_l == "buy" and sl >= entry:
            warnings.append(
                f"SL={sl} bất thường với lệnh BUY: phải NHỎ HƠN giá vào {entry} "
                f"(hiện SL đang cao hơn → dừng lỗ sẽ thành lãi giả)"
            )
        elif side_l == "sell" and sl <= entry:
            warnings.append(
                f"SL={sl} bất thường với lệnh SELL: phải LỚN HƠN giá vào {entry} "
                f"(hiện SL đang thấp hơn → dừng lỗ sẽ thành lãi giả)"
            )

    if tp_price is not None and sl_price is not None:
        tp = float(tp_price)
        sl = float(sl_price)
        if side_l == "buy" and not (sl < entry < tp):
            if sl >= tp:
                warnings.append(f"Với BUY cần SL < giá vào < TP, nhưng SL={sl} và TP={tp} đang sai thứ tự")
        elif side_l == "sell" and not (tp < entry < sl):
            if tp >= sl:
                warnings.append(f"Với SELL cần TP < giá vào < SL, nhưng TP={tp} và SL={sl} đang sai thứ tự")

    return warnings


def print_tp_sl_warnings(side, entry_price, tp_price=None, sl_price=None, indent=""):
    warnings = collect_tp_sl_warnings(side, entry_price, tp_price, sl_price)
    for msg in warnings:
        print(f"{indent}[CẢNH BÁO] {msg}", flush=True)
    return warnings


def print_open_tp_sl_estimate(symbol, side, entry_price, tp_price, sl_price, lot, indent=""):
    """In ước tính lời/lỗ tại TP/SL. Luôn chạy ở chế độ xem trước (kể cả khi chưa --no-ask)."""
    if tp_price is None and sl_price is None:
        print(f"{indent}Không có TP/SL để ước tính lời/lỗ.", flush=True)
        return

    try:
        contract_size = resolve_contract_size(symbol)
        estimated = estimate_tp_sl_pnl(side, entry_price, tp_price, sl_price, lot, contract_size)
        # Luôn in rõ — không phụ thuộc --no-ask (confirm_action chỉ chặn gửi lệnh thật).
        if "tp" in estimated:
            print(f"{indent}Ước tính lời TP: {estimated['tp']:.8f}", flush=True)
        if "sl" in estimated:
            print(f"{indent}Ước tính lỗ SL: {estimated['sl']:.8f}", flush=True)
        if not estimated:
            print(f"{indent}Không ước tính được lời/lỗ (thiếu TP/SL).", flush=True)
    except Exception as exc:
        # Fallback tính thô nếu lấy contract_size từ MT5 lỗi
        try:
            estimated = estimate_tp_sl_pnl(side, entry_price, tp_price, sl_price, lot, 1.0)
            print(f"{indent}(fallback contract_size=1) Không lấy được contract size: {exc}", flush=True)
            if "tp" in estimated:
                print(f"{indent}Ước tính lời TP: {estimated['tp']:.8f}", flush=True)
            if "sl" in estimated:
                print(f"{indent}Ước tính lỗ SL: {estimated['sl']:.8f}", flush=True)
        except Exception as exc2:
            print(f"{indent}Không ước tính được lời/lỗ: {exc2}", flush=True)


def get_filling_mode(symbol):
    """
    Tự động kiểm tra chế độ khớp lệnh (Filling Mode) bằng bitmask nguyên bản.
    Tránh lỗi AttributeError trên một số phiên bản thư viện MetaTrader5.
    """
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        return 2  # Mặc định trả về ORDER_FILL_RETURN nếu không lấy được thông tin
        
    filling_mode = symbol_info.filling_mode
    
    # Sử dụng giá trị số nguyên (bitmask) trực tiếp của hệ thống MT5:
    # 1 = SYMBOL_FILLING_FOK
    # 2 = SYMBOL_FILLING_IOC
    if filling_mode & 1:
        return 0  # Giá trị số của mt5.ORDER_FILL_FOK
    elif filling_mode & 2:
        return 1  # Giá trị số của mt5.ORDER_FILL_IOC
    else:
        return 2  # Giá trị số của mt5.ORDER_FILL_RETURN


def validate_tp_sl(side, entry_price, tp_price, sl_price, is_modification=False):
    """Kiểm tra hướng TP/SL so với giá vào (dùng cho open).

    is_modification: chỉ cho phép None (không đổi field đó). Không dùng so với giá thị trường.
    """
    side_l = (side or "").lower()
    entry = float(entry_price)

    if tp_price is not None and tp_price <= 0:
        raise RuntimeError("TP phải lớn hơn 0")
    if sl_price is not None and sl_price <= 0:
        raise RuntimeError("SL phải lớn hơn 0")

    if side_l == "buy":
        if tp_price is not None and tp_price <= entry:
            raise RuntimeError(f"TP mua không hợp lệ: {tp_price} phải lớn hơn giá mở {entry}")
        if sl_price is not None and sl_price >= entry:
            raise RuntimeError(f"SL mua không hợp lệ: {sl_price} phải nhỏ hơn giá mở {entry}")
    else:
        if tp_price is not None and tp_price >= entry:
            raise RuntimeError(f"TP bán không hợp lệ: {tp_price} phải nhỏ hơn giá mở {entry}")
        if sl_price is not None and sl_price <= entry:
            raise RuntimeError(f"SL bán không hợp lệ: {sl_price} phải lớn hơn giá mở {entry}")


def validate_tp_sl_modify(side, tp_price, sl_price):
    """Modify-all: không so với giá hiện tại / giá mở — chỉ kiểm tra TP/SL hợp lệ theo side.

    BUY: SL < TP (nếu cả hai có). SELL: TP < SL (nếu cả hai có). Giá phải > 0.
    """
    side_l = (side or "").lower()

    if tp_price is not None and tp_price <= 0:
        raise RuntimeError("TP phải lớn hơn 0")
    if sl_price is not None and sl_price <= 0:
        raise RuntimeError("SL phải lớn hơn 0")

    if tp_price is None or sl_price is None:
        return

    tp = float(tp_price)
    sl = float(sl_price)
    if side_l == "buy":
        if not (sl < tp):
            raise RuntimeError(f"TP/SL mua không hợp lệ: cần SL < TP (SL={sl}, TP={tp})")
    else:
        if not (tp < sl):
            raise RuntimeError(f"TP/SL bán không hợp lệ: cần TP < SL (TP={tp}, SL={sl})")


def calculate_position_pnl(position):
    """Tính P/L hiện tại theo giá thị trường; trả về (pnl_formula, current_price, contract_size)."""
    contract_size = resolve_contract_size(position.symbol)
    tick = get_current_price(position.symbol)
    current_price = tick.bid if position.type == mt5.ORDER_TYPE_BUY else tick.ask

    if position.type == mt5.ORDER_TYPE_BUY:
        pnl_formula = (current_price - position.price_open) * position.volume * contract_size
    else:
        pnl_formula = (position.price_open - current_price) * position.volume * contract_size

    return pnl_formula, current_price, contract_size


def safe_position_pnl(position):
    """P/L hiển thị: luôn dùng position.profit từ MT5; bổ sung giá/công thức nếu lấy được tick.

    Tránh việc get_current_price lỗi làm mất cả khối in lời/lỗ trong action status.
    Trả về dict: mt5_profit, pnl_formula (hoặc None), current_price (hoặc None), error (hoặc None).
    """
    mt5_profit = float(getattr(position, "profit", 0.0) or 0.0)
    try:
        pnl_formula, current_price, _ = calculate_position_pnl(position)
        return {
            "mt5_profit": mt5_profit,
            "pnl_formula": pnl_formula,
            "current_price": current_price,
            "error": None,
        }
    except Exception as exc:
        return {
            "mt5_profit": mt5_profit,
            "pnl_formula": None,
            "current_price": None,
            "error": str(exc),
        }


def format_pnl_status(pnl_value):
    if pnl_value > 0:
        return f"ĐANG LÃI {pnl_value:.6f}"
    if pnl_value < 0:
        return f"ĐANG LỖ {abs(pnl_value):.6f}"
    return "HÒA"


def print_position_pnl_lines(position, indent="  "):
    """In trạng thái lời/lỗ của 1 vị thế (không để lỗi tick làm mất dòng P/L)."""
    info = safe_position_pnl(position)
    mt5_profit = info["mt5_profit"]
    print(f"{indent}Trạng thái: {format_pnl_status(mt5_profit)}")
    if info["current_price"] is not None:
        print(f"{indent}Giá hiện tại: {info['current_price']}")
    else:
        print(f"{indent}Giá hiện tại: không lấy được ({info['error']})")
    if info["pnl_formula"] is not None:
        print(f"{indent}P/L hiện tại: {mt5_profit} (công thức: {info['pnl_formula']:.6f})")
    else:
        print(f"{indent}P/L hiện tại: {mt5_profit} (MT5)")
    return info


def build_trade_request(symbol, side, lot, tp_price=None, sl_price=None, comment="Python trader test", price=None):
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        raise RuntimeError(f"Không lấy được thông tin symbol {symbol}")

    if price is None:
        tick = get_current_price(symbol)
        price = tick.ask if side == "buy" else tick.bid
    else:
        price = float(price)
    order_type = mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL

    validate_tp_sl(side, price, tp_price, sl_price)

    # Lấy filling mode động phù hợp với cài đặt của Exness
    filling_policy = get_filling_mode(symbol)

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": price,
        "deviation": DEFAULT_DEVIATION,
        "magic": DEFAULT_MAGIC,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling_policy,  # Thay đổi từ mt5.ORDER_FILL_IOC cố định sang chế độ tự chọn động
    }

    if tp_price is not None:
        request["tp"] = tp_price
    if sl_price is not None:
        request["sl"] = sl_price

    return request


def open_trade(account, symbol, side, lot, tp_price=None, sl_price=None, comment="Python trader test"):
    if sl_price is None:
        raise RuntimeError("Lệnh open bắt buộc phải có --sl-price (stop loss)")

    symbol = select_symbol(symbol, account)
    entry_price = get_entry_price(symbol, side)
    validate_tp_sl(side, entry_price, tp_price, sl_price)

    print(f"Sẽ mở lệnh {side.upper()} trên {symbol} với khối lượng {lot} lot")
    print(f"Giá vào dự kiến: {entry_price}")
    print(f"TP: {tp_price if tp_price is not None else 'không đặt'} | SL: {sl_price}")

    # Ước tính luôn in ở chế độ xem trước — --no-ask chỉ quyết định có gửi lệnh thật hay không.
    contract_size = resolve_contract_size(symbol)
    estimated = estimate_tp_sl_pnl(side, entry_price, tp_price, sl_price, lot, contract_size)
    if tp_price is not None:
        print(f"Ước tính lời TP: {estimated.get('tp', 0):.8f}")
    else:
        print("Không đặt TP — bỏ qua ước tính lời TP.")
    print(f"Ước tính lỗ SL: {estimated.get('sl', 0):.8f}")
    validate_xauusd_max_loss(symbol, side, entry_price, sl_price, lot, account=account)

    if not confirm_action("Bạn có muốn thực hiện hành động này không?"):
        print("Đã hủy mở lệnh.")
        return None

    request = build_trade_request(symbol, side, lot, tp_price, sl_price, comment)
    result = mt5.order_send(request)

    if result is None:
        err = mt5.last_error()
        print(f"Đặt lệnh thất bại nặng! Không nhận được phản hồi từ terminal. Lỗi hệ thống: {err}")
        save_trade_history(
            symbol, lot, None, request, "FAILED",
            f"không phản hồi từ terminal | last_error={err}",
        )
        return None

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Đặt lệnh thất bại! Mã lỗi: {result.retcode} ({result.comment})")
        save_trade_history(symbol, lot, result, request, "FAILED", f"retcode={result.retcode} | {result.comment}")
        return None

    print(f"Đặt lệnh thành công! Ticket ID: {result.order}")
    save_trade_history(symbol, lot, result, request, "SUCCESS")
    return result


def levels_from_distance(side, entry_price, sl_distance, tp_distance=None):
    """Đổi khoảng cách SL/TP thành mức giá theo hướng lệnh.

    BUY: SL = giá − khoảng cách SL, TP = giá + khoảng cách TP.
    SELL: SL = giá + khoảng cách SL, TP = giá − khoảng cách TP.
    """
    side_l = (side or "").lower()
    if side_l not in ("buy", "sell"):
        raise RuntimeError("side phải là buy hoặc sell")
    try:
        entry = float(entry_price)
        sl_d = float(sl_distance)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Giá hoặc khoảng cách SL/TP không phải số") from exc
    if not math.isfinite(entry) or entry <= 0:
        raise RuntimeError(f"Giá hiện tại không hợp lệ: {entry_price}")
    if not math.isfinite(sl_d) or sl_d <= 0:
        raise RuntimeError(
            "Stop loss phải là khoảng cách > 0 so với giá hiện tại (ví dụ 10), không phải mức giá"
        )
    tp_d = None
    if tp_distance is not None:
        try:
            tp_d = float(tp_distance)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Khoảng cách take profit không phải số") from exc
        if not math.isfinite(tp_d) or tp_d <= 0:
            raise RuntimeError(
                "Take profit phải là khoảng cách > 0 so với giá hiện tại (ví dụ 50), hoặc bỏ trống"
            )
    if side_l == "buy":
        sl_price = entry - sl_d
        tp_price = None if tp_d is None else entry + tp_d
    else:
        sl_price = entry + sl_d
        tp_price = None if tp_d is None else entry - tp_d
    if sl_price <= 0 or (tp_price is not None and tp_price <= 0):
        raise RuntimeError(
            f"Khoảng cách SL/TP quá lớn so với giá {entry}: SL={sl_price}"
            + (f", TP={tp_price}" if tp_price is not None else "")
        )
    return tp_price, sl_price


def plan_open_two_side(symbol, sl_distance, tp_distance=None):
    """Một tick: BUY theo ask, SELL theo bid, SL/TP là khoảng cách từ giá khớp."""
    tick = get_current_price(symbol)
    plans = []
    for side in ("buy", "sell"):
        entry = float(tick.ask if side == "buy" else tick.bid)
        tp_price, sl_price = levels_from_distance(side, entry, sl_distance, tp_distance)
        sl_price = normalize_price(symbol, sl_price)
        if tp_price is not None:
            tp_price = normalize_price(symbol, tp_price)
        validate_tp_sl(side, entry, tp_price, sl_price)
        plans.append({
            "side": side,
            "entry": entry,
            "tp": tp_price,
            "sl": sl_price,
        })
    return {
        "bid": float(tick.bid),
        "ask": float(tick.ask),
        "plans": plans,
    }


def _print_two_side_plan(symbol, lot, sl_distance, tp_distance, snapshot, account):
    contract_size = resolve_contract_size(symbol)
    tp_label = tp_distance if tp_distance is not None else "không đặt"
    print(f"Sẽ mở BUY và SELL trên {symbol}, mỗi lệnh {lot} lot")
    print(f"Khoảng cách: SL {sl_distance} | TP {tp_label}")
    print(f"Giá hiện tại: bid={snapshot['bid']} ask={snapshot['ask']}")
    print("BUY khớp ở ask, SELL khớp ở bid — cùng thời điểm lấy giá.")
    for plan in snapshot["plans"]:
        side = plan["side"]
        entry = plan["entry"]
        sl_price = plan["sl"]
        tp_price = plan["tp"]
        if side == "buy":
            sl_note = f"giá − {sl_distance}"
            tp_note = f"giá + {tp_distance}" if tp_price is not None else None
        else:
            sl_note = f"giá + {sl_distance}"
            tp_note = f"giá − {tp_distance}" if tp_price is not None else None
        tp_text = f"{tp_price} ({tp_note})" if tp_price is not None else "không đặt"
        print(f"{side.upper()} giá vào {entry} | SL {sl_price} ({sl_note}) | TP {tp_text}")
        estimated = estimate_tp_sl_pnl(side, entry, tp_price, sl_price, lot, contract_size)
        if tp_price is not None:
            print(f"  Ước tính lời TP: {estimated.get('tp', 0):.8f}")
        else:
            print("  Không đặt TP — bỏ qua ước tính lời TP.")
        print(f"  Ước tính lỗ SL: {estimated.get('sl', 0):.8f}")
        validate_xauusd_max_loss(symbol, side, entry, sl_price, lot, account=account)


def _warn_distance_inside_stops(symbol, sl_distance, tp_distance):
    info = mt5.symbol_info(symbol)
    if info is None:
        return
    point = float(getattr(info, "point", 0) or 0)
    stops = int(getattr(info, "trade_stops_level", 0) or 0)
    min_dist = stops * point
    if min_dist <= 0:
        return
    too_close = float(sl_distance) < min_dist
    if tp_distance is not None and float(tp_distance) < min_dist:
        too_close = True
    if too_close:
        print(
            f"Cảnh báo: broker yêu cầu SL/TP cách giá ít nhất {min_dist} "
            f"(stops level {stops}). Khoảng cách nhỏ hơn có thể bị từ chối."
        )


def send_market_order(symbol, side, lot, tp_price, sl_price, comment, price):
    """Gửi một lệnh thị trường. Giá vào đã chốt — không lấy tick mới."""
    request = build_trade_request(
        symbol, side, lot, tp_price, sl_price, comment, price=price,
    )
    result = mt5.order_send(request)
    label = side.upper()
    if result is None:
        err = mt5.last_error()
        print(f"{label}: đặt lệnh thất bại nặng! Không nhận được phản hồi từ terminal. Lỗi hệ thống: {err}")
        save_trade_history(
            symbol, lot, None, request, "FAILED",
            f"không phản hồi từ terminal | last_error={err}",
        )
        return None
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"{label}: đặt lệnh thất bại! Mã lỗi: {result.retcode} ({result.comment})")
        save_trade_history(symbol, lot, result, request, "FAILED", f"retcode={result.retcode} | {result.comment}")
        return None
    print(f"{label}: đặt lệnh thành công! Ticket ID: {result.order}")
    save_trade_history(symbol, lot, result, request, "SUCCESS")
    return result


def open_two_side(account, symbol, lot, tp_distance=None, sl_distance=None, comment="Python trader test"):
    """Mở BUY và SELL thị trường. sl_distance/tp_distance là khoảng cách, không phải mức giá."""
    if sl_distance is None:
        raise RuntimeError(
            "Lệnh open-2-side bắt buộc --sl-price là khoảng cách > 0 (ví dụ 10), không phải mức giá"
        )
    try:
        sl_distance = float(sl_distance)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Khoảng cách stop loss không phải số") from exc
    if not math.isfinite(sl_distance) or sl_distance <= 0:
        raise RuntimeError(
            "Lệnh open-2-side bắt buộc --sl-price là khoảng cách > 0 (ví dụ 10), không phải mức giá"
        )
    if tp_distance is not None:
        try:
            tp_distance = float(tp_distance)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Khoảng cách take profit không phải số") from exc
        if not math.isfinite(tp_distance) or tp_distance <= 0:
            raise RuntimeError(
                "open-2-side: --tp-price phải là khoảng cách > 0 (ví dụ 50), hoặc bỏ trống"
            )

    symbol = select_symbol(symbol, account)
    snapshot = plan_open_two_side(symbol, sl_distance, tp_distance)
    _print_two_side_plan(symbol, lot, sl_distance, tp_distance, snapshot, account)
    _warn_distance_inside_stops(symbol, sl_distance, tp_distance)

    if not confirm_action("Mở đồng thời lệnh BUY và SELL với SL/TP tính theo khoảng cách?"):
        print("Đã hủy mở lệnh 2 phía.")
        return None

    snapshot = plan_open_two_side(symbol, sl_distance, tp_distance)
    print(f"Gửi theo giá mới nhất: bid={snapshot['bid']} ask={snapshot['ask']}")
    for plan in snapshot["plans"]:
        tp_text = plan["tp"] if plan["tp"] is not None else "không đặt"
        print(f"  {plan['side'].upper()} giá vào {plan['entry']} | SL {plan['sl']} | TP {tp_text}")
        validate_xauusd_max_loss(
            symbol, plan["side"], plan["entry"], plan["sl"], lot, account=account,
        )

    results = {}
    for plan in snapshot["plans"]:
        try:
            results[plan["side"]] = send_market_order(
                symbol, plan["side"], lot, plan["tp"], plan["sl"], comment, plan["entry"],
            )
        except Exception as exc:
            results[plan["side"]] = None
            print(f"{plan['side'].upper()}: lỗi khi gửi lệnh: {exc}")

    buy_ok = results.get("buy") is not None
    sell_ok = results.get("sell") is not None
    print(
        "Kết quả open-2-side: "
        f"BUY {'thành công' if buy_ok else 'thất bại'} | "
        f"SELL {'thành công' if sell_ok else 'thất bại'}"
    )
    return results


def pending_order_type_label(order_type):
    return ORDER_TYPE_LABELS.get(int(order_type), f"TYPE_{order_type}")


def resolve_pending_order_type(side, pending_type):
    side_l = (side or "").lower()
    kind = (pending_type or "").lower()
    if side_l not in ("buy", "sell"):
        raise RuntimeError("side phải là buy hoặc sell")
    if kind not in PENDING_TYPES:
        raise RuntimeError("pending-type phải là limit hoặc stop")

    mapping = {
        ("buy", "limit"): (mt5.ORDER_TYPE_BUY_LIMIT, "BUY_LIMIT"),
        ("buy", "stop"): (mt5.ORDER_TYPE_BUY_STOP, "BUY_STOP"),
        ("sell", "limit"): (mt5.ORDER_TYPE_SELL_LIMIT, "SELL_LIMIT"),
        ("sell", "stop"): (mt5.ORDER_TYPE_SELL_STOP, "SELL_STOP"),
    }
    return mapping[(side_l, kind)]


def normalize_price(symbol, price):
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        return float(price)
    digits = int(getattr(symbol_info, "digits", 0) or 0)
    return round(float(price), digits)


def sltp_price(symbol, price):
    """Giá SL/TP cho order_send: luôn Python float. 0.0 = không đặt.

    Wrapper MetaTrader5 từ chối int (kể cả 0) và numpy scalar → last_error
    (-2, 'Invalid "tp" argument') / Invalid "sl" — order_send trả None, terminal
    không nhận lệnh.
    """
    if price is None:
        return 0.0
    try:
        value = float(price)
    except (TypeError, ValueError):
        return 0.0
    if value <= 0:
        return 0.0
    return normalize_price(symbol, value)


def pending_market_info(symbol):
    tick = get_current_price(symbol)
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        raise RuntimeError(f"Không lấy được thông tin symbol {symbol}")
    point = float(getattr(symbol_info, "point", 0) or 0) or 0.0
    stops_level = int(getattr(symbol_info, "trade_stops_level", 0) or 0)
    return {
        "bid": float(tick.bid),
        "ask": float(tick.ask),
        "min_distance": stops_level * point,
        "stops_level": stops_level,
    }


def infer_pending_type(side, price, bid, ask):
    """Limit hay Stop theo giá chờ so với thị trường — không bắt user chọn đúng hướng."""
    side_l = (side or "").lower()
    price = float(price)
    if side_l == "buy":
        return "limit" if price < float(ask) else "stop"
    if side_l == "sell":
        return "limit" if price > float(bid) else "stop"
    raise RuntimeError("side phải là buy hoặc sell")


def resolve_pending_kind(symbol, side, price, pending_type=None):
    """Chọn limit/stop theo giá, bỏ qua pending_type nếu lệch hướng thị trường."""
    market = pending_market_info(symbol)
    inferred = infer_pending_type(side, price, market["bid"], market["ask"])
    requested = (pending_type or "").strip().lower()
    if requested and requested not in PENDING_TYPES:
        raise RuntimeError("pending-type phải là limit hoặc stop")
    market["requested_type"] = requested or None
    market["inferred_type"] = inferred
    market["type_overridden"] = bool(requested) and requested != inferred
    return inferred, market


def validate_pending_price(symbol, side, pending_type, price):
    """Giữ tên cũ: không còn chặn giá chờ bé/lớn hơn thị trường."""
    _kind, market = resolve_pending_kind(symbol, side, price, pending_type)
    return market


def is_order_send_success(result):
    if result is None:
        return False
    ok_codes = {mt5.TRADE_RETCODE_DONE}
    placed = getattr(mt5, "TRADE_RETCODE_PLACED", None)
    if placed is not None:
        ok_codes.add(placed)
    return result.retcode in ok_codes


def build_pending_request(symbol, side, pending_type, price, lot, tp_price=None, sl_price=None,
                          comment="Python pending"):
    price = normalize_price(symbol, price)
    pending_type, _market = resolve_pending_kind(symbol, side, price, pending_type)
    order_type, _label = resolve_pending_order_type(side, pending_type)
    validate_tp_sl(side, price, tp_price, sl_price)

    filling_policy = get_filling_mode(symbol)
    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": float(lot),
        "type": order_type,
        "price": price,
        "deviation": DEFAULT_DEVIATION,
        "magic": DEFAULT_MAGIC,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling_policy,
    }
    if tp_price is not None:
        request["tp"] = normalize_price(symbol, tp_price)
    if sl_price is not None:
        request["sl"] = normalize_price(symbol, sl_price)
    return request


def open_pending_trade(account, symbol, side, pending_type, price, lot,
                       tp_price=None, sl_price=None, comment="Python pending"):
    if price is None:
        raise RuntimeError("Lệnh pending bắt buộc phải có --price (giá chờ)")
    if sl_price is None:
        raise RuntimeError("Lệnh pending bắt buộc phải có --sl-price (stop loss)")

    symbol = select_symbol(symbol, account)
    price = normalize_price(symbol, price)
    pending_type, market = resolve_pending_kind(symbol, side, price, pending_type)
    _order_type, type_label = resolve_pending_order_type(side, pending_type)
    validate_tp_sl(side, price, tp_price, sl_price)

    print(f"Sẽ đặt lệnh chờ {type_label} trên {symbol} với khối lượng {lot} lot")
    print(f"Giá chờ: {price} | bid={market['bid']} ask={market['ask']}")
    if market.get("type_overridden"):
        print(
            f"Đã tự chọn {type_label} theo giá chờ so với thị trường "
            f"(bỏ qua pending-type={market.get('requested_type')})."
        )
    if market["min_distance"]:
        print(f"Khoảng cách stops_level của symbol: {market['min_distance']} (terminal có thể từ chối nếu quá sát).")
    print(f"TP: {tp_price if tp_price is not None else 'không đặt'} | SL: {sl_price}")

    contract_size = resolve_contract_size(symbol)
    estimated = estimate_tp_sl_pnl(side, price, tp_price, sl_price, lot, contract_size)
    if tp_price is not None:
        print(f"Ước tính lời TP: {estimated.get('tp', 0):.8f}")
    else:
        print("Không đặt TP — bỏ qua ước tính lời TP.")
    print(f"Ước tính lỗ SL: {estimated.get('sl', 0):.8f}")
    validate_xauusd_max_loss(symbol, side, price, sl_price, lot, account=account)

    if not confirm_action("Bạn có muốn đặt lệnh chờ này không?"):
        print("Đã hủy đặt lệnh chờ.")
        return None

    request = build_pending_request(
        symbol, side, pending_type, price, lot, tp_price, sl_price, comment,
    )
    result = mt5.order_send(request)

    if result is None:
        err = mt5.last_error()
        print(f"Đặt lệnh chờ thất bại nặng! Không nhận được phản hồi từ terminal. Lỗi hệ thống: {err}")
        save_trade_history(
            symbol, lot, None, request, "PENDING_FAILED",
            f"không phản hồi từ terminal | last_error={err} | type={type_label} | price={price}",
        )
        return None

    if not is_order_send_success(result):
        print(f"Đặt lệnh chờ thất bại! Mã lỗi: {result.retcode} ({result.comment})")
        save_trade_history(
            symbol, lot, result, request, "PENDING_FAILED",
            f"retcode={result.retcode} | {result.comment} | type={type_label} | price={price}",
        )
        return None

    print(f"Đặt lệnh chờ thành công! Ticket ID: {result.order} | {type_label} @ {price}")
    save_trade_history(
        symbol, lot, result, request, "PENDING_SUCCESS",
        f"type={type_label} | price={price}",
    )
    return result


def cancel_pending_order(order, confirm=True):
    type_label = pending_order_type_label(order.type)
    print(
        f"Lệnh chờ: ticket={order.ticket} | symbol={order.symbol} | "
        f"Type={type_label} | Price={order.price_open} | Vol={order.volume_current}"
    )

    if confirm and not confirm_action(f"Bạn có muốn hủy lệnh chờ {order.ticket} này không?"):
        print("Đã hủy thao tác hủy lệnh chờ.")
        return None

    request = {
        "action": mt5.TRADE_ACTION_REMOVE,
        "order": order.ticket,
        "symbol": order.symbol,
        "magic": DEFAULT_MAGIC,
        "comment": "Cancel pending",
    }
    result = mt5.order_send(request)
    if result is None:
        err = mt5.last_error()
        print(f"Hủy lệnh chờ {order.ticket} thất bại! Không nhận được phản hồi.")
        save_trade_history(
            order.symbol, order.volume_current, None, request, "CANCEL_PENDING_FAILED",
            f"ticket={order.ticket} | không phản hồi từ terminal | last_error={err}",
        )
        return None

    if not is_order_send_success(result):
        print(f"Hủy lệnh chờ {order.ticket} thất bại! Mã lỗi: {result.retcode} ({result.comment})")
        save_trade_history(
            order.symbol, order.volume_current, result, request, "CANCEL_PENDING_FAILED",
            f"ticket={order.ticket} | {result.comment}",
        )
        return None

    print(f"Hủy lệnh chờ thành công! Ticket ID: {order.ticket}")
    save_trade_history(
        order.symbol, order.volume_current, result, request, "CANCEL_PENDING_SUCCESS",
        f"ticket={order.ticket}",
    )
    return result


def cancel_all_pending_orders():
    orders = mt5.orders_get()
    if not orders:
        print("Không có lệnh chờ nào để hủy.")
        return []

    print(f"Tìm thấy {len(orders)} lệnh chờ. Đang chuẩn bị hủy toàn bộ...")
    for order in orders:
        type_label = pending_order_type_label(order.type)
        print(
            f"- Ticket: {order.ticket} | Symbol: {order.symbol} | "
            f"Type: {type_label} | Price: {order.price_open} | Vol: {order.volume_current}"
        )

    if not confirm_action("Bạn có muốn hủy toàn bộ các lệnh chờ này không?"):
        print("Đã hủy thao tác hủy toàn bộ lệnh chờ.")
        return []

    results = []
    for order in orders:
        results.append(cancel_pending_order(order, confirm=False))
    return results


def symbol_volume_limits(symbol):
    info = mt5.symbol_info(symbol)
    vmin = 0.01
    vmax = 100.0
    step = 0.01
    if info is not None:
        vmin = float(getattr(info, "volume_min", vmin) or vmin)
        vmax = float(getattr(info, "volume_max", vmax) or vmax)
        step = float(getattr(info, "volume_step", step) or step)
    if vmin <= 0:
        vmin = 0.01
    if vmax <= 0:
        vmax = 100.0
    if step <= 0:
        step = vmin
    return vmin, vmax, step


def round_volume_down(volume, step):
    volume = float(volume)
    step = float(step)
    if step <= 0:
        return volume
    steps = math.floor((volume + 1e-12) / step)
    return round(steps * step, 8)


def clip_close_volume(symbol, want, position_volume):
    """Khối lượng đóng hợp lệ: không vượt vị thế, khớp step, không để dư < volume_min."""
    vmin, vmax, step = symbol_volume_limits(symbol)
    pos = float(position_volume)
    want = float(want)
    if want <= 0 or pos <= 0:
        return 0.0
    want = min(want, pos, vmax)
    vol = round_volume_down(want, step)
    leftover = round(pos - vol, 8)
    if leftover > 1e-12 and leftover < vmin:
        vol = round_volume_down(pos - vmin, step)
        leftover = round(pos - vol, 8)
        if leftover < vmin - 1e-12:
            if want + 1e-12 >= pos:
                return pos
            return 0.0
    if vol + 1e-12 < vmin:
        if want + 1e-12 >= pos:
            return pos
        return 0.0
    if vol > pos:
        return pos
    return vol


def find_position_by_ticket(ticket):
    positions = mt5.positions_get()
    if not positions:
        return None
    ticket = int(ticket)
    for position in positions:
        if int(position.ticket) == ticket:
            return position
    return None


def list_positions_for_close(symbol, side):
    want_type = mt5.ORDER_TYPE_BUY if (side or "").lower() == "buy" else mt5.ORDER_TYPE_SELL
    positions = mt5.positions_get(symbol=symbol)
    if not positions:
        all_pos = mt5.positions_get() or []
        positions = tuple(p for p in all_pos if p.symbol == symbol)
    matched = [p for p in positions if p.type == want_type]
    matched.sort(key=lambda p: (int(getattr(p, "time", 0) or 0), int(p.ticket)))
    return matched


def plan_close_volume(positions, lot):
    remaining = float(lot)
    plan = []
    for position in positions:
        if remaining <= 1e-12:
            break
        vol = clip_close_volume(position.symbol, remaining, position.volume)
        if vol <= 0:
            continue
        plan.append((position, vol))
        remaining = round(remaining - vol, 8)
    return plan, remaining


def build_close_request(position, volume=None):
    symbol = position.symbol
    tick = get_current_price(symbol)
    close_type = mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    close_price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
    filling_policy = get_filling_mode(symbol)
    close_volume = float(position.volume if volume is None else volume)
    is_partial = close_volume + 1e-12 < float(position.volume)

    return {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": close_volume,
        "type": close_type,
        "position": position.ticket,
        "price": close_price,
        "deviation": DEFAULT_DEVIATION,
        "magic": DEFAULT_MAGIC,
        "comment": "Partial close" if is_partial else "Close position",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling_policy,
    }


def close_position(position, confirm=True, volume=None):
    close_vol = float(position.volume if volume is None else volume)
    if close_vol <= 0:
        print(f"Bỏ qua ticket {position.ticket}: volume đóng không hợp lệ ({close_vol}).")
        return None
    if close_vol > float(position.volume) + 1e-12:
        close_vol = float(position.volume)
    is_partial = close_vol + 1e-12 < float(position.volume)
    remain = round(float(position.volume) - close_vol, 8)

    print(f"Lệnh hiện tại: ticket={position.ticket} | symbol={position.symbol}")
    print(f"Loại: {'BUY' if position.type == mt5.ORDER_TYPE_BUY else 'SELL'}")
    print(f"Giá vào: {position.price_open}")
    if is_partial:
        print(f"Đóng một phần: {close_vol} / {position.volume} lot (còn {remain})")
    else:
        print(f"Đóng toàn bộ: {close_vol} lot")
    info = print_position_pnl_lines(position, indent="")
    profit_frac = close_vol / float(position.volume) if position.volume else 1.0
    if is_partial:
        print(f"Ước tính P/L phần đóng: {info['mt5_profit'] * profit_frac:.6f}")

    if confirm and not confirm_action(f"Bạn có muốn đóng lệnh {position.ticket} này không?"):
        print("Đã hủy đóng lệnh.")
        return None

    request = build_close_request(position, close_vol)
    result = mt5.order_send(request)
    if result is None:
        err = mt5.last_error()
        print("Đóng lệnh thất bại! Không nhận được phản hồi.")
        save_trade_history(
            position.symbol, close_vol, None, request, "CLOSE_FAILED",
            f"ticket={position.ticket} | không phản hồi từ terminal | last_error={err}",
            position=position,
        )
        return None

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Đóng lệnh thất bại! Mã lỗi: {result.retcode} ({result.comment})")
        save_trade_history(
            position.symbol, close_vol, result, request, "CLOSE_FAILED",
            f"ticket={position.ticket} | {result.comment}",
            position=position,
        )
        return None

    print(f"Đóng lệnh thành công! Ticket ID: {result.order}")
    detail = f"ticket={position.ticket}"
    if is_partial:
        detail += f" | partial={close_vol}/{position.volume}"
    save_trade_history(
        position.symbol, close_vol, result, request, "CLOSE_SUCCESS",
        detail,
        profit=float(getattr(position, "profit", 0) or 0) * profit_frac,
        position=position,
    )
    return result


def close_all_positions():
    positions = mt5.positions_get()
    if not positions:
        print("Không có lệnh nào đang mở.")
        return []

    print(f"Tìm thấy {len(positions)} lệnh đang mở. Đang chuẩn bị đóng toàn bộ...")
    total_mt5 = 0.0
    total_formula = 0.0
    formula_ok = True
    for position in positions:
        print(
            f"- Ticket: {position.ticket} | Symbol: {position.symbol} | "
            f"Type: {'BUY' if position.type == mt5.ORDER_TYPE_BUY else 'SELL'} | "
            f"Vol: {position.volume}"
        )
        print(f"  Giá vào: {position.price_open}")
        info = print_position_pnl_lines(position)
        total_mt5 += info["mt5_profit"]
        if info["pnl_formula"] is not None:
            total_formula += info["pnl_formula"]
        else:
            formula_ok = False

    if formula_ok:
        print(f"Tổng P/L tất cả lệnh: {format_pnl_status(total_mt5)} | công thức: {total_formula:.6f}")
    else:
        print(f"Tổng P/L tất cả lệnh: {format_pnl_status(total_mt5)} (MT5)")

    if not confirm_action("Bạn có muốn đóng toàn bộ các lệnh này không?"):
        print("Đã hủy đóng toàn bộ lệnh.")
        return []

    results = []
    for position in positions:
        result = close_position(position, confirm=False)
        results.append(result)
    return results


def close_positions_volume(account, symbol, side, lot):
    """Đóng `lot` khối lượng các lệnh mở cùng symbol + side (cho phép đóng một phần)."""
    if lot is None or float(lot) <= 0:
        raise RuntimeError("Lệnh close bắt buộc --lot > 0 (số lot muốn đóng)")

    symbol = select_symbol(symbol, account)
    side_l = (side or "").lower()
    if side_l not in ("buy", "sell"):
        raise RuntimeError("side phải là buy hoặc sell")

    matched = list_positions_for_close(symbol, side_l)
    if not matched:
        print(f"Không có lệnh {side_l.upper()} {symbol} đang mở để đóng.")
        return []

    total = round(sum(float(p.volume) for p in matched), 8)
    requested = float(lot)
    close_target = requested
    if requested > total + 1e-12:
        print(
            f"[CẢNH BÁO] Lot yêu cầu {requested} lớn hơn tổng {side_l.upper()} {symbol} đang mở ({total}). "
            f"Sẽ đóng hết {total} lot."
        )
        close_target = total

    plan, leftover_want = plan_close_volume(matched, close_target)
    planned_vol = round(sum(vol for _pos, vol in plan), 8)

    print(
        f"Sẽ đóng {planned_vol} lot lệnh {side_l.upper()} trên {symbol} "
        f"(đang mở: {total} lot, {len(matched)} ticket)"
    )
    if leftover_want > 1e-12 and planned_vol + 1e-12 < close_target:
        print(
            f"[CẢNH BÁO] Không phân bổ hết {close_target} lot vì volume_min/step "
            f"(còn {leftover_want} lot chưa đóng được mà không để dư nhỏ hơn lot tối thiểu)."
        )

    if not plan:
        raise RuntimeError(
            f"Không đóng được {requested} lot: không khớp volume_min/step, "
            f"hoặc phần còn lại sẽ nhỏ hơn lot tối thiểu."
        )

    for position, vol in plan:
        remain = round(float(position.volume) - vol, 8)
        remain_text = "" if remain <= 1e-12 else f" (còn {remain})"
        print(
            f"- Ticket: {position.ticket} | đóng {vol} / {position.volume} lot{remain_text}"
        )
        print(f"  Giá vào: {position.price_open}")
        info = print_position_pnl_lines(position)
        frac = vol / float(position.volume) if position.volume else 1.0
        print(f"  Ước tính P/L phần đóng: {info['mt5_profit'] * frac:.6f}")

    if not confirm_action(f"Bạn có muốn đóng {planned_vol} lot {side_l.upper()} {symbol} không?"):
        print("Đã hủy đóng một phần.")
        return []

    results = []
    for position, vol in plan:
        live = find_position_by_ticket(position.ticket)
        if live is None:
            print(f"Ticket {position.ticket} không còn mở — bỏ qua.")
            results.append(None)
            continue
        live_vol = clip_close_volume(live.symbol, vol, live.volume)
        if live_vol <= 0:
            print(
                f"Ticket {position.ticket}: không đóng được {vol} lot "
                f"với volume hiện tại {live.volume}."
            )
            results.append(None)
            continue
        results.append(close_position(live, confirm=False, volume=live_vol))
    return results


def print_account_info():
    account_info = mt5.account_info()
    if account_info is None:
        print("Không lấy được thông tin tài khoản")
        return

    print("Thông tin tài khoản:")
    print(f"- Balance: {account_info.balance}")
    print(f"- Equity: {account_info.equity}")
    print(f"- Margin: {account_info.margin}")
    print(f"- Free Margin: {account_info.margin_free}")
    print(f"- Margin Level: {account_info.margin_level}")


def print_open_positions():
    positions = mt5.positions_get()
    print("Các lệnh đang mở:")
    if not positions:
        print("- Không có lệnh nào đang mở")
        return

    total_mt5 = 0.0
    for position in positions:
        side = "buy" if position.type == mt5.ORDER_TYPE_BUY else "sell"
        sl = getattr(position, "sl", 0) or 0
        tp = getattr(position, "tp", 0) or 0
        tp_price = tp if tp > 0 else None
        sl_price = sl if sl > 0 else None
        print(f"- Ticket: {position.ticket} | Symbol: {position.symbol}")
        print(f"  Type: {side.upper()}")
        print(f"  Volume: {position.volume}")
        print(f"  Giá mở cửa: {position.price_open}")
        print(f"  Stop Loss: {sl if sl > 0 else 'chưa đặt'}")
        print(f"  Take Profit: {tp if tp > 0 else 'chưa đặt'}")
        info = print_position_pnl_lines(position)
        print_open_tp_sl_estimate(
            position.symbol,
            side,
            position.price_open,
            tp_price,
            sl_price,
            position.volume,
            indent="  ",
        )
        total_mt5 += info["mt5_profit"]

    if len(positions) > 1:
        print(f"Tổng P/L các lệnh mở: {format_pnl_status(total_mt5)}")


def print_pending_orders():
    orders = mt5.orders_get()
    print("Các lệnh chờ:")
    if not orders:
        print("- Không có lệnh chờ nào")
        return

    for order in orders:
        type_label = pending_order_type_label(order.type)
        price = getattr(order, "price_open", None)
        if price is None:
            price = getattr(order, "price", 0)
        sl = getattr(order, "sl", 0) or 0
        tp = getattr(order, "tp", 0) or 0
        vol = getattr(order, "volume_current", None)
        if vol is None:
            vol = getattr(order, "volume_initial", 0)
        print(
            f"- Ticket: {order.ticket} | Symbol: {order.symbol} | Type: {type_label} | "
            f"Price: {price} | Vol: {vol} | SL: {sl if sl > 0 else 'chưa đặt'} | "
            f"TP: {tp if tp > 0 else 'chưa đặt'}"
        )



def modify_all_positions_tp_sl(tp_price=None, sl_price=None, symbol=None):
    """Thay đổi take profit và stop loss của các lệnh đang mở (lọc symbol nếu có)."""
    positions = mt5.positions_get()
    if positions and symbol:
        want = str(symbol).strip()
        positions = tuple(p for p in positions if p.symbol == want)
    if not positions:
        print("Không có lệnh nào đang mở để thay đổi.")
        return []

    print(f"Tìm thấy {len(positions)} lệnh đang mở. Đang chuẩn bị thay đổi TP/SL cho tất cả...")
    for position in positions:
        side = "buy" if position.type == mt5.ORDER_TYPE_BUY else "sell"
        new_tp = tp_price if tp_price is not None else (position.tp if position.tp > 0 else None)
        new_sl = sl_price if sl_price is not None else (position.sl if position.sl > 0 else None)

        print(f"- Ticket: {position.ticket} | Symbol: {position.symbol} | Type: {side.upper()}")
        print(f"  Giá vào: {position.price_open} | TP cũ: {position.tp if position.tp > 0 else 'chưa đặt'} | SL cũ: {position.sl if position.sl > 0 else 'chưa đặt'}")
        if tp_price is not None:
            print(f"  → TP mới: {tp_price}")
        if sl_price is not None:
            print(f"  → SL mới: {sl_price}")
        # Modify: không bắt so với giá hiện tại / giá mở — chỉ kiểm tra cặp TP/SL theo side.
        try:
            validate_tp_sl_modify(side, new_tp, new_sl)
        except RuntimeError as exc:
            print(f"  [CẢNH BÁO] {exc}", flush=True)
        print_open_tp_sl_estimate(position.symbol, side, position.price_open, new_tp, new_sl, position.volume)
        if new_sl is not None:
            validate_xauusd_max_loss(position.symbol, side, position.price_open, new_sl, position.volume)

    if not confirm_action("Bạn có muốn thay đổi TP/SL cho tất cả các lệnh này không?"):
        print("Đã hủy thay đổi TP/SL cho tất cả lệnh.")
        return []

    results = []
    for position in positions:
        side = "buy" if position.type == mt5.ORDER_TYPE_BUY else "sell"

        new_tp = tp_price if tp_price is not None else position.tp
        new_sl = sl_price if sl_price is not None else position.sl
        send_tp = sltp_price(position.symbol, new_tp)
        send_sl = sltp_price(position.symbol, new_sl)
        check_tp = send_tp if send_tp > 0 else None
        check_sl = send_sl if send_sl > 0 else None
        validate_tp_sl_modify(side, check_tp, check_sl)

        if send_sl > 0:
            validate_xauusd_max_loss(position.symbol, side, position.price_open, send_sl, position.volume)

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": position.symbol,
            "position": int(position.ticket),
            "tp": send_tp,
            "sl": send_sl,
            "magic": DEFAULT_MAGIC,
            "comment": "Modified TP/SL",
        }

        result = mt5.order_send(request)
        if result is None:
            err = mt5.last_error()
            print(f"Thay đổi TP/SL cho ticket {position.ticket} thất bại! Không nhận được phản hồi.")
            save_trade_history(
                position.symbol, position.volume, None, request, "MODIFY_FAILED",
                f"ticket={position.ticket} | không phản hồi từ terminal | last_error={err}",
                position=position,
            )
            results.append(None)
            continue

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"Thay đổi TP/SL cho ticket {position.ticket} thất bại! Mã lỗi: {result.retcode} ({result.comment})")
            save_trade_history(
                position.symbol, position.volume, result, request, "MODIFY_FAILED",
                f"ticket={position.ticket} | {result.comment}",
                position=position,
            )
        else:
            print(f"Thay đổi TP/SL cho ticket {position.ticket} thành công!")
            save_trade_history(position.symbol, position.volume, result, request, "MODIFY_SUCCESS", f"ticket={position.ticket}")

        results.append(result)

    return results


def _print_modify_if_jobs(account_name):
    jobs = modify_if.waiting_jobs(account_name)
    if not jobs:
        print("Không có job modify-all-if đang chờ.")
        return jobs
    print(f"Job modify-all-if đang chờ ({len(jobs)}):")
    for job in jobs:
        tp = job["tpPrice"] if job.get("tpPrice") is not None else "không đặt"
        print(
            f"- {job['symbol']} vùng {job['zoneLow']} – {job['zoneHigh']} "
            f"| SL mới={job['slPrice']} | TP mới={tp}"
        )
    return jobs


def register_modify_all_if(account, symbol, sl_price, tp_price=None, price=None,
                           zone_low=None, zone_high=None):
    """Lưu job: khi giá chạm vùng thì watcher sửa SL/TP các lệnh mở cùng symbol."""
    if sl_price is None or sl_price <= 0:
        raise RuntimeError("modify-all-if bắt buộc --sl-price > 0")
    symbol = select_symbol(symbol, account)
    zone_low, zone_high = modify_if.resolve_zone(price, zone_low, zone_high)
    quote = fetch_quote(account, symbol, "buy")
    positions = list_open_positions_data()
    matched = [p for p in positions if p["symbol"] == symbol]

    print(f"Sẽ đặt modify-all-if cho {account['name']} / {symbol}")
    print(f"Vùng kích hoạt: {zone_low} – {zone_high}")
    print(f"Giá hiện tại: bid={quote['bid']} ask={quote['ask']}")
    print(f"Khi chạm vùng → SL mới={sl_price} | TP mới={tp_price if tp_price is not None else 'không đặt'}")
    print(f"Lệnh mở cùng symbol sẽ bị sửa: {len(matched)}")
    for pos in matched:
        print(f"- Ticket: {pos['ticket']} | {pos['side'].upper()} {pos['volume']} | mở={pos['price_open']}")
    print("Cần start_server.bat (watcher) để job chạy. Lần poll đầu chỉ ghi nhận giá, không kích hoạt.")
    _print_modify_if_jobs(account["name"])

    if not confirm_action("Bạn có muốn đặt job modify-all-if này không?"):
        print("Đã hủy đặt modify-all-if.")
        return None

    job = {
        "id": modify_if.new_job_id(),
        "account": account["name"],
        "symbol": symbol,
        "zoneLow": zone_low,
        "zoneHigh": zone_high,
        "slPrice": sl_price,
        "tpPrice": tp_price,
        "enabled": True,
        "fired": False,
        "primed": False,
        "lastBid": quote["bid"],
        "lastAsk": quote["ask"],
        "lastSymbol": symbol,
        "lastAt": int(time.time() * 1000),
        "lastError": "",
    }
    replaced = modify_if.upsert_waiting_job(job)
    if replaced:
        print(f"Đã thay job modify-all-if cũ của {account['name']} / {symbol}.")
    else:
        print(f"Đã đặt job modify-all-if {job['id']}.")
    return job


def cancel_modify_if_jobs(account):
    name = account["name"] if isinstance(account, dict) else str(account)
    jobs = _print_modify_if_jobs(name)
    if not jobs:
        return []
    if not confirm_action("Bạn có muốn hủy mọi job modify-all-if đang chờ của account này không?"):
        print("Đã hủy thao tác cancel-modify-if.")
        return []
    cancelled = modify_if.cancel_waiting_jobs(name)
    print(f"Đã hủy {len(cancelled)} job modify-all-if.")
    return cancelled


def apply_modify_if_job(account, job):
    """Watcher gọi khi giá chạm vùng. Caller đã connect_mt5. Ép no-ask."""
    global NO_ASK, _ACTIVE_XAUUSD_MAX_LOSS
    prev_ask = NO_ASK
    prev_loss = _ACTIVE_XAUUSD_MAX_LOSS
    NO_ASK = True
    _ACTIVE_XAUUSD_MAX_LOSS = account.get("xauusd_max_loss")
    try:
        resolved = job.get("lastSymbol") or select_symbol(job["symbol"], account)
        print(
            f"[MODIFY-ALL-IF] {account.get('name')} {resolved} "
            f"vùng {job['zoneLow']}–{job['zoneHigh']} → SL={job['slPrice']} "
            f"TP={job['tpPrice'] if job.get('tpPrice') is not None else 'không đặt'}"
        )
        return modify_all_positions_tp_sl(job.get("tpPrice"), job["slPrice"], symbol=resolved)
    finally:
        NO_ASK = prev_ask
        _ACTIVE_XAUUSD_MAX_LOSS = prev_loss


def fetch_quote(account, symbol, side="buy"):
    """Lấy bid/ask/entry (tick live) cho symbol sau khi connect account. Caller chịu trách nhiệm shutdown."""
    symbol = select_symbol(symbol, account)
    tick = get_current_price(symbol)
    side_l = (side or "buy").lower()
    entry = tick.ask if side_l == "buy" else tick.bid
    return {
        "symbol": symbol,
        "side": side_l,
        "bid": float(tick.bid),
        "ask": float(tick.ask),
        "entry": float(entry),
        "source": "tick",
    }


def fetch_last_m1_candle(account, symbol, closed=True):
    """Lấy nến M1: closed=True → nến 1 phút đã đóng gần nhất; False → nến đang chạy.

    MT5 index: pos 0 = nến hiện tại (chưa đóng), pos 1 = nến đã đóng gần nhất.
    """
    symbol = select_symbol(symbol, account)
    count = 2 if closed else 1
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, count)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"Không lấy được nến M1 cho {symbol}: {mt5.last_error()}")
    if closed:
        if len(rates) < 2:
            raise RuntimeError(f"Chưa đủ nến M1 đã đóng cho {symbol}")
        bar = rates[1]
    else:
        bar = rates[0]

    bar_time = int(bar["time"])
    time_str = datetime.fromtimestamp(bar_time).strftime("%Y-%m-%d %H:%M:%S")
    open_p = float(bar["open"])
    high_p = float(bar["high"])
    low_p = float(bar["low"])
    close_p = float(bar["close"])
    return {
        "symbol": symbol,
        "timeframe": "M1",
        "closed": bool(closed),
        "time": bar_time,
        "time_str": time_str,
        "open": open_p,
        "high": high_p,
        "low": low_p,
        "close": close_p,
        # Tương thích chỗ cũ so với bid/ask: dùng close.
        "bid": close_p,
        "ask": close_p,
        "entry": close_p,
        "source": "m1_closed" if closed else "m1_current",
    }


def list_open_positions_data():
    """Snapshot lệnh mở (JSON-friendly) — dùng cho UI điền SL/TP từ status."""
    positions = mt5.positions_get()
    if not positions:
        return []
    rows = []
    for position in positions:
        side = "buy" if position.type == mt5.ORDER_TYPE_BUY else "sell"
        sl = float(getattr(position, "sl", 0) or 0)
        tp = float(getattr(position, "tp", 0) or 0)
        rows.append({
            "ticket": int(position.ticket),
            "symbol": position.symbol,
            "side": side,
            "volume": float(position.volume),
            "price_open": float(position.price_open),
            "sl": sl if sl > 0 else None,
            "tp": tp if tp > 0 else None,
            "profit": float(getattr(position, "profit", 0) or 0),
        })
    return rows


def list_pending_orders_data():
    """Snapshot lệnh chờ (JSON-friendly) — dùng cho UI cancel-pending."""
    orders = mt5.orders_get()
    if not orders:
        return []
    rows = []
    for order in orders:
        type_label = pending_order_type_label(order.type)
        price = getattr(order, "price_open", None)
        if price is None:
            price = getattr(order, "price", 0)
        vol = getattr(order, "volume_current", None)
        if vol is None:
            vol = getattr(order, "volume_initial", 0)
        sl = float(getattr(order, "sl", 0) or 0)
        tp = float(getattr(order, "tp", 0) or 0)
        type_i = int(order.type)
        if type_i in (mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP, mt5.ORDER_TYPE_BUY_STOP_LIMIT):
            side = "buy"
        else:
            side = "sell"
        rows.append({
            "ticket": int(order.ticket),
            "symbol": order.symbol,
            "side": side,
            "type": type_label,
            "volume": float(vol),
            "price": float(price),
            "sl": sl if sl > 0 else None,
            "tp": tp if tp > 0 else None,
        })
    return rows


def _news_fmt_lot(value, step):
    text = f"{float(step):.8f}".rstrip("0").rstrip(".")
    decimals = len(text.split(".")[1]) if "." in text else 0
    return f"{float(value):.{decimals}f}"


def _news_fmt_num(value):
    value = float(value)
    if abs(value - round(value)) < 1e-6:
        return str(int(round(value)))
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text or "0"


def _news_fmt_px(value, digits):
    return f"{float(value):.{int(digits)}f}"


def _news_lot_from_units(units, step):
    step = float(step)
    text = f"{step:.8f}".rstrip("0").rstrip(".")
    decimals = len(text.split(".")[1]) if "." in text else 0
    return round(int(units) * step, decimals)


def _news_floor_units(volume, step):
    return max(0, math.floor(float(volume) / float(step) + 1e-9))


def _news_round_units(volume, step):
    return max(0, int(math.floor(float(volume) / float(step) + 0.5)))


def _news_money(distance, units, contract_size, step):
    return float(distance) * int(units) * float(contract_size) * float(step)


def _news_require_positive(name, value):
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{name} phải là số > 0") from exc
    if not math.isfinite(number) or number <= 0:
        raise RuntimeError(f"{name} phải là số > 0")
    return number


def news_hedge_scenario(p_ref, sell_avg, buy_sl, sell_sl, buffer_eff, volume_units, contract_size, volume_step):
    """Lỗ thiết kế khi một đầu cháy rồi giá về mức đệm, và lỗ nếu cả hai SL đều cháy."""
    p_ref = float(p_ref)
    sell_avg = float(sell_avg)
    buy_sl = float(buy_sl)
    sell_sl = float(sell_sl)
    buffer_eff = float(buffer_eff)
    s_real = p_ref - sell_avg
    logical_buy = sell_sl - buffer_eff
    logical_sell = buy_sl + buffer_eff
    sell_loss_dist = sell_sl - sell_avg
    buy_profit_dist = logical_buy - p_ref
    buy_loss_dist = p_ref - buy_sl
    sell_profit_dist = sell_avg - logical_sell
    net_dist = buffer_eff + s_real
    both_dist = sell_loss_dist + buy_loss_dist
    return {
        "s_real": s_real,
        "logical_buy": logical_buy,
        "logical_sell": logical_sell,
        "sell_loss_dist": sell_loss_dist,
        "buy_profit_dist": buy_profit_dist,
        "buy_loss_dist": buy_loss_dist,
        "sell_profit_dist": sell_profit_dist,
        "net_dist": net_dist,
        "both_dist": both_dist,
        "sell_loss": _news_money(sell_loss_dist, volume_units, contract_size, volume_step),
        "buy_profit": _news_money(buy_profit_dist, volume_units, contract_size, volume_step),
        "buy_loss": _news_money(buy_loss_dist, volume_units, contract_size, volume_step),
        "sell_profit": _news_money(sell_profit_dist, volume_units, contract_size, volume_step),
        "net": _news_money(net_dist, volume_units, contract_size, volume_step),
        "both_sl_loss": _news_money(both_dist, volume_units, contract_size, volume_step),
    }


def build_news_hedge_plan(
    max_risk, sl_pips, buffer_pips, leverage, max_exec_ms, stop_out,
    ask, bid, equity, free_margin, contract_size,
    volume_step, volume_min, volume_max,
    t_benchmark_ms=None, margin_hedged=0.0, hedging=True, digits=2,
    locked_units=None,
):
    """Tính V, chia chunk và mức SL. Không đụng MT5."""
    max_risk = float(max_risk)
    sl_pips = float(sl_pips)
    buffer_pips = float(buffer_pips)
    leverage = float(leverage)
    max_exec_ms = float(max_exec_ms)
    stop_out = float(stop_out)
    ask = float(ask)
    bid = float(bid)
    equity = float(equity)
    free_margin = float(free_margin)
    contract_size = float(contract_size)
    volume_step = float(volume_step)
    volume_min = float(volume_min)
    volume_max = float(volume_max)
    spread = ask - bid
    blockers = []
    notes = []

    if ask <= 0 or bid <= 0:
        blockers.append("Giá Ask/Bid không hợp lệ")
    if spread < -1e-12:
        blockers.append("Spread âm")
    if leverage <= 0:
        blockers.append("Đòn bẩy không hợp lệ")
    if contract_size <= 0 or volume_step <= 0 or volume_min <= 0:
        blockers.append("Contract size hoặc bước lot không hợp lệ")
    if locked_units is None and equity + 1e-9 < max_risk:
        blockers.append(f"Equity { _news_fmt_num(equity) } nhỏ hơn MAX_RISK { _news_fmt_num(max_risk) }")
    if locked_units is None and free_margin + 1e-9 < max_risk:
        blockers.append(
            f"Free Margin { _news_fmt_num(free_margin) } nhỏ hơn MAX_RISK { _news_fmt_num(max_risk) }"
        )
    if not hedging:
        blockers.append("Tài khoản không ở hedging mode. BUY rồi SELL sẽ tự trừ nhau")
    if float(margin_hedged) > 1e-6:
        blockers.append(
            f"margin_hedged={margin_hedged} khác 0. Giả định ký quỹ bù trừ không đúng, hủy"
        )

    loss_per_lot = None
    v_risk = None
    v_so = None
    v_units = 0
    v_lot = 0.0
    if contract_size > 0 and buffer_pips + spread > 0:
        loss_per_lot = contract_size * (buffer_pips + spread)
        v_risk = max_risk / loss_per_lot
        if leverage > 0:
            denom = contract_size * (ask * stop_out / leverage + buffer_pips + spread)
            if denom > 0:
                v_so = equity / denom
    if v_risk is None or v_so is None or volume_step <= 0:
        blockers.append("Không tính được V")
    else:
        raw_units = _news_floor_units(min(v_risk, v_so), volume_step)
        if volume_max > 0:
            max_units = _news_floor_units(volume_max, volume_step)
            if raw_units > max_units:
                notes.append(f"V cắt theo volume_max { _news_fmt_num(volume_max) }")
                raw_units = max_units
        v_units = raw_units
        v_lot = _news_lot_from_units(v_units, volume_step)
    if locked_units is not None and volume_step > 0:
        v_units = max(0, int(locked_units))
        v_lot = _news_lot_from_units(v_units, volume_step)
        notes.append(f"V khóa {_news_fmt_num(v_lot)} vì cặp mẫu đã nằm trong V")

    bench_units = 0
    if volume_step > 0 and volume_min > 0:
        bench_units = max(1, math.ceil(volume_min / volume_step - 1e-12))
    bench_lot = _news_lot_from_units(bench_units, volume_step) if bench_units else 0.0
    if v_units < bench_units:
        blockers.append(
            f"V { _news_fmt_num(v_lot) } nhỏ hơn lot mẫu { _news_fmt_num(bench_lot) }"
        )

    units_rest = max(0, v_units - bench_units)
    n_from_time = None
    n_pairs = None
    base = None
    rem = None
    chunk_units = None
    if t_benchmark_ms is not None:
        t_benchmark_ms = float(t_benchmark_ms)
        if t_benchmark_ms <= 0:
            n_from_time = units_rest
        else:
            n_from_time = max(1, math.floor(max_exec_ms / t_benchmark_ms))
        n_pairs = min(n_from_time, units_rest)
        chunk_units = []
        if n_pairs > 0:
            base = units_rest // n_pairs
            rem = units_rest % n_pairs
            chunk_units = [(base + 1 if i < rem else base) for i in range(n_pairs)]
        else:
            base = 0
            rem = 0

    chunk_lots = None
    chunk_max_units = 0
    if chunk_units is not None:
        chunk_lots = [_news_lot_from_units(unit, volume_step) for unit in chunk_units]
        if chunk_units:
            chunk_max_units = max(chunk_units)

    chunk_max_lot = _news_lot_from_units(chunk_max_units, volume_step) if chunk_max_units else 0.0
    guard_margin = None
    guard_ok = None
    if chunk_units and leverage > 0 and chunk_max_lot > 0:
        guard_margin = chunk_max_lot * contract_size * ask / leverage
        guard_ok = guard_margin <= free_margin + 1e-6
        if not guard_ok:
            blockers.append(
                f"Margin Guardrail: chunk { _news_fmt_num(chunk_max_lot) } cần "
                f"{ _news_fmt_num(guard_margin) }, Free Margin { _news_fmt_num(free_margin) }"
            )

    s_real = spread
    risk_real = None
    buffer_eff = buffer_pips
    designed_loss = None
    if loss_per_lot is not None and v_units > 0:
        designed_loss = _news_money(buffer_pips + spread, v_units, contract_size, volume_step)
        risk_real = designed_loss
        if risk_real > max_risk + 1e-6 and contract_size > 0:
            buffer_eff = max_risk / (v_units * contract_size * volume_step) - s_real
    if buffer_eff <= 0 and v_units > 0:
        blockers.append("BUFFER_eff <= 0 sau khi tính spread. Phải đóng hết nếu đã có vị thế")

    buy_sl = ask - sl_pips
    sell_sl = ask + sl_pips
    scenario = None
    if v_units > 0 and buffer_eff > 0:
        scenario = news_hedge_scenario(
            ask, bid, buy_sl, sell_sl, buffer_eff, v_units, contract_size, volume_step,
        )

    return {
        "max_risk": max_risk,
        "sl_pips": sl_pips,
        "buffer_pips": buffer_pips,
        "leverage": leverage,
        "max_exec_ms": max_exec_ms,
        "stop_out": stop_out,
        "ask": ask,
        "bid": bid,
        "spread": spread,
        "equity": equity,
        "free_margin": free_margin,
        "contract_size": contract_size,
        "volume_step": volume_step,
        "volume_min": volume_min,
        "volume_max": volume_max,
        "digits": int(digits),
        "margin_hedged": float(margin_hedged),
        "hedging": bool(hedging),
        "loss_per_lot": loss_per_lot,
        "v_risk": v_risk,
        "v_so": v_so,
        "v_units": v_units,
        "v": v_lot,
        "bench_units": bench_units,
        "bench_lot": bench_lot,
        "units_rest": units_rest,
        "t_benchmark_ms": None if t_benchmark_ms is None else float(t_benchmark_ms),
        "n_from_time": n_from_time,
        "n_pairs": n_pairs,
        "base": base,
        "rem": rem,
        "chunk_units": chunk_units,
        "chunk_lots": chunk_lots,
        "chunk_max_lot": chunk_max_lot,
        "guard_margin": guard_margin,
        "guard_ok": guard_ok,
        "s_real": s_real,
        "risk_real": risk_real,
        "buffer_eff": buffer_eff,
        "designed_loss": designed_loss,
        "buy_sl": buy_sl,
        "sell_sl": sell_sl,
        "scenario": scenario,
        "blockers": blockers,
        "notes": notes,
    }


def _news_loss_line(label, distance, units, money):
    return (
        f"{label} { _news_fmt_num(distance) } * {units} = { _news_fmt_num(money) }$"
    )


def _print_news_hedge_outcome(title, p_ref, sell_avg, buy_sl, sell_sl, buffer_eff, volume_units,
                              contract_size, volume_step, digits, max_risk):
    scenario = news_hedge_scenario(
        p_ref, sell_avg, buy_sl, sell_sl, buffer_eff, volume_units, contract_size, volume_step,
    )
    print(title)
    print(
        f"P_ref={_news_fmt_px(p_ref, digits)} | giá SELL trung bình={_news_fmt_px(sell_avg, digits)} | "
        f"S_real={_news_fmt_num(scenario['s_real'])}"
    )
    print(
        f"BUY SL={_news_fmt_px(buy_sl, digits)} | SELL SL={_news_fmt_px(sell_sl, digits)} | "
        f"BUFFER_eff={_news_fmt_num(buffer_eff)} | mất ròng thiết kế={_news_fmt_num(scenario['net'])}$ "
        f"(MAX_RISK { _news_fmt_num(max_risk) })"
    )
    print(
        f"- Giá lên, SELL chạm {_news_fmt_px(sell_sl, digits)}: "
        + _news_loss_line("SELL lỗ", scenario["sell_loss_dist"], volume_units, scenario["sell_loss"])
        + f". Giá về {_news_fmt_px(scenario['logical_buy'], digits)}: "
        + _news_loss_line("BUY lời", scenario["buy_profit_dist"], volume_units, scenario["buy_profit"])
        + f". Mất ròng {_news_fmt_num(scenario['net'])}$."
    )
    print(
        f"  BUY giữ SL {_news_fmt_px(buy_sl, digits)}. Giá chạy tới SL đó: "
        + _news_loss_line("BUY lỗ", scenario["buy_loss_dist"], volume_units, scenario["buy_loss"])
        + f". Hai SL cộng {_news_fmt_num(scenario['both_sl_loss'])}$."
    )
    print(
        f"- Giá xuống, BUY chạm {_news_fmt_px(buy_sl, digits)}: "
        + _news_loss_line("BUY lỗ", scenario["buy_loss_dist"], volume_units, scenario["buy_loss"])
        + f". Giá về {_news_fmt_px(scenario['logical_sell'], digits)}: "
        + _news_loss_line("SELL lời", scenario["sell_profit_dist"], volume_units, scenario["sell_profit"])
        + f". Mất ròng {_news_fmt_num(scenario['net'])}$."
    )
    print(
        f"  SELL giữ SL {_news_fmt_px(sell_sl, digits)}. Giá chạy tới SL đó: "
        + _news_loss_line("SELL lỗ", scenario["sell_loss_dist"], volume_units, scenario["sell_loss"])
        + f". Hai SL cộng {_news_fmt_num(scenario['both_sl_loss'])}$."
    )
    return scenario


def _print_news_hedge_plan(plan, mode):
    digits = plan["digits"]
    print(
        f"Input: MAX_RISK={_news_fmt_num(plan['max_risk'])} | SL_PIPS={_news_fmt_num(plan['sl_pips'])} | "
        f"BUFFER_PIPS={_news_fmt_num(plan['buffer_pips'])} | LEVERAGE={_news_fmt_num(plan['leverage'])} | "
        f"MAX_EXEC_TIME={_news_fmt_num(plan['max_exec_ms'])} ms | SO={_news_fmt_num(plan['stop_out'] * 100)}%"
    )
    print(
        f"Thị trường: Ask={_news_fmt_px(plan['ask'], digits)} Bid={_news_fmt_px(plan['bid'], digits)} "
        f"Spread={_news_fmt_num(plan['spread'])} | Equity={_news_fmt_num(plan['equity'])} | "
        f"Free Margin={_news_fmt_num(plan['free_margin'])} | CS={_news_fmt_num(plan['contract_size'])} | "
        f"step={_news_fmt_num(plan['volume_step'])} min={_news_fmt_num(plan['volume_min'])}"
    )
    print(
        f"Hedge: margin_hedged={_news_fmt_num(plan['margin_hedged'])} | "
        f"hedging mode={'có' if plan['hedging'] else 'không'}"
    )
    for note in plan["notes"]:
        print(f"Ghi chú: {note}")

    print("Bước 1 — khối lượng mỗi phía")
    if plan["loss_per_lot"] is None:
        print("Chưa tính được Loss_per_lot.")
    else:
        print(
            f"Loss_per_lot = {_news_fmt_num(plan['contract_size'])} * "
            f"({_news_fmt_num(plan['buffer_pips'])} + {_news_fmt_num(plan['spread'])}) "
            f"= {_news_fmt_num(plan['loss_per_lot'])}"
        )
        print(
            f"V_risk = {_news_fmt_num(plan['max_risk'])} / {_news_fmt_num(plan['loss_per_lot'])} "
            f"= {_news_fmt_num(plan['v_risk'])}"
        )
        print(
            f"V_so = {_news_fmt_num(plan['equity'])} / "
            f"[CS * (Price*SO/LEVERAGE + BUFFER + Spread)] = {_news_fmt_num(plan['v_so'])}"
        )
        print(
            f"V = {_news_fmt_num(plan['v'])} lot mỗi phía "
            f"({_news_fmt_num(plan['v'])} BUY + {_news_fmt_num(plan['v'])} SELL). "
            f"Lỗ thiết kế = {_news_fmt_num(plan['designed_loss']) if plan['designed_loss'] is not None else '?'}$"
        )
    if mode == "demo":
        print("Nếu bỏ spread, 375/800 = 0.46 lot sẽ mất 0.46 * 900 = 414$, vượt MAX_RISK.")

    print("Bước 2 — đo tốc độ")
    if plan["t_benchmark_ms"] is None:
        print(
            f"Chưa đo T_benchmark. Cặp mẫu {_news_fmt_num(plan['bench_lot'])} lot "
            "chỉ bắn khi có --no-ask, và được giữ trong V."
        )
    else:
        print(
            f"T_benchmark = {_news_fmt_num(plan['t_benchmark_ms'])} ms. "
            f"Cặp mẫu {_news_fmt_num(plan['bench_lot'])} lot được giữ trong V."
        )

    print("Bước 3 — số cặp và Margin Guardrail")
    print(
        f"units = {plan['v_units']}, cặp mẫu = {plan['bench_units']} bước, "
        f"units_rest = {plan['units_rest']}"
    )
    if plan["chunk_lots"] is None:
        print("Chưa có T_benchmark nên chưa chia chunk và chưa kiểm tra Margin Guardrail.")
    else:
        print(
            f"N_pairs = min(max(1, floor(MAX_EXEC_TIME / T_benchmark)) = {plan['n_from_time']}, "
            f"units_rest = {plan['units_rest']}) = {plan['n_pairs']}"
        )
        print(f"base = {plan['base']}, rem = {plan['rem']}")
        if plan["chunk_lots"]:
            def _lot(value):
                return _news_fmt_lot(value, plan["volume_step"])

            chunk_text = ", ".join(_lot(lot) for lot in plan["chunk_lots"])
            rest = _news_lot_from_units(plan["units_rest"], plan["volume_step"])
            print(
                f"Các cặp: {chunk_text} (tổng {_lot(rest)}) "
                f"+ mẫu {_lot(plan['bench_lot'])} = {_lot(plan['v'])}"
            )
        else:
            print(f"Không còn chunk. Chỉ giữ cặp mẫu {_news_fmt_num(plan['bench_lot'])}.")
        if plan["guard_margin"] is not None:
            print(
                f"Margin Guardrail: {_news_fmt_num(plan['chunk_max_lot'])} * "
                f"{_news_fmt_num(plan['contract_size'])} * {_news_fmt_px(plan['ask'], digits)} / "
                f"{_news_fmt_num(plan['leverage'])} = {_news_fmt_num(plan['guard_margin'])} "
                f"so với Free Margin {_news_fmt_num(plan['free_margin'])}: "
                f"{'đạt' if plan['guard_ok'] else 'không đạt'}"
            )

    print("Bước 4 — bắn xen kẽ")
    if mode == "demo":
        if plan["chunk_lots"]:
            seq = " -> ".join(
                f"BUY({_news_fmt_num(lot)}) -> SELL({_news_fmt_num(lot)})" for lot in plan["chunk_lots"]
            )
            print(f"Mô phỏng: {seq}. Demo không gửi lệnh.")
        else:
            print("Demo không gửi lệnh.")
    elif plan["chunk_lots"] is None:
        print("Mỗi cặp là BUY rồi SELL cùng khối lượng. Hết giờ thì dừng ở đầu cặp sau. Chưa gửi.")
    else:
        print("Đã có danh sách chunk. Lệnh thật đi theo danh sách này.")

    print("Bước 5 và 6 — SL dự kiến nếu không trượt giá, và kịch bản thua")
    if plan["scenario"] is None:
        print("Chưa đủ số để dựng kịch bản.")
    else:
        _print_news_hedge_outcome(
            "SL dự kiến bám P_ref = Ask. S_real = Spread.",
            plan["ask"], plan["bid"], plan["buy_sl"], plan["sell_sl"], plan["buffer_eff"],
            plan["v_units"], plan["contract_size"], plan["volume_step"], digits, plan["max_risk"],
        )
    if plan["blockers"]:
        print("Dừng phần còn lại:" if mode == "live" else "Hủy, không gửi lệnh:")
        for blocker in plan["blockers"]:
            print(f"- {blocker}")


def print_news_hedge_demo(max_risk=375.0, sl_pips=15.0, buffer_pips=8.0, max_exec_ms=300.0):
    """In đúng bảng mẫu. Không initialize và không gửi lệnh."""
    print("demo-open-2-side-news-multi-auto")
    print("Không nối MT5. Không gửi lệnh. Số liệu cố định: Ask 4200, Bid 4199, Equity 375, T_benchmark 45 ms.")
    sample = (375.0, 15.0, 8.0, 300.0)
    given = (float(max_risk), float(sl_pips), float(buffer_pips), float(max_exec_ms))
    if any(abs(a - b) > 1e-9 for a, b in zip(given, sample)):
        print("Demo giữ số liệu bảng mẫu. Tham số truyền vào không đổi kịch bản này.")
    plan = build_news_hedge_plan(
        max_risk=375.0, sl_pips=15.0, buffer_pips=8.0, leverage=200.0, max_exec_ms=300.0,
        stop_out=0.0, ask=4200.0, bid=4199.0, equity=375.0, free_margin=375.0,
        contract_size=100.0, volume_step=0.01, volume_min=0.01, volume_max=100.0,
        t_benchmark_ms=45.0, margin_hedged=0.0, hedging=True, digits=2,
    )
    _print_news_hedge_plan(plan, "demo")
    expected_chunks = [0.07, 0.07, 0.07, 0.07, 0.06, 0.06]
    checks = [
        ("V", plan["v"], 0.41),
        ("Loss_per_lot", plan["loss_per_lot"], 900.0),
        ("N_pairs", plan["n_pairs"], 6),
        ("Margin", plan["guard_margin"], 147.0),
        ("BUY SL", plan["buy_sl"], 4185.0),
        ("SELL SL", plan["sell_sl"], 4215.0),
        ("Lỗ thiết kế", plan["designed_loss"], 369.0),
        ("Mất ròng", plan["scenario"]["net"], 369.0),
        ("Hai SL", plan["scenario"]["both_sl_loss"], 1271.0),
    ]
    mismatches = []
    if plan["chunk_lots"] != expected_chunks:
        mismatches.append(f"chunk {plan['chunk_lots']} khác {expected_chunks}")
    for label, got, want in checks:
        if got is None or abs(float(got) - float(want)) > 1e-6:
            mismatches.append(f"{label}={got} khác {want}")
    if mismatches:
        print("Đối chiếu bảng mẫu: lệch.")
        for line in mismatches:
            print(f"- {line}")
        raise RuntimeError("demo-open-2-side-news-multi-auto lệch bảng mẫu")
    print("Đối chiếu bảng mẫu: khớp (V 0.41, chunk 0.07x4 + 0.06x2, lỗ thiết kế 369, hai SL 1271).")
    return plan


def _news_apply_account_cap(plan, account, symbol):
    cap = get_xauusd_max_loss(account) if is_xauusd_symbol(symbol) else None
    plan["xauusd_max_loss"] = cap
    if cap is None or plan["designed_loss"] is None:
        return plan
    if plan["designed_loss"] > float(cap) + 1e-6:
        plan["blockers"].append(
            f"Lỗ thiết kế {_news_fmt_num(plan['designed_loss'])} lớn hơn xauusd_max_loss {_news_fmt_num(cap)}"
        )
    return plan


def _news_read_market(symbol, fast=False):
    if fast:
        tick = mt5.symbol_info_tick(symbol)
        if tick is None or tick.bid <= 0 or tick.ask <= 0 or tick.ask < tick.bid:
            raise RuntimeError(f"Không lấy được tick hợp lệ cho {symbol}")
    else:
        tick = get_current_price(symbol)
    info = mt5.account_info()
    if info is None:
        raise RuntimeError("Không lấy được thông tin tài khoản")
    sym = mt5.symbol_info(symbol)
    if sym is None:
        raise RuntimeError(f"Không lấy được thông tin symbol {symbol}")
    vmin, vmax, step = symbol_volume_limits(symbol)
    hedging_mode = int(getattr(mt5, "ACCOUNT_MARGIN_MODE_RETAIL_HEDGING", 2))
    return {
        "ask": float(tick.ask),
        "bid": float(tick.bid),
        "equity": float(info.equity),
        "free_margin": float(info.margin_free),
        "leverage": float(getattr(info, "leverage", 0) or 0),
        "stop_out": float(getattr(info, "margin_so_so", 0) or 0) / 100.0,
        "contract_size": resolve_contract_size(symbol),
        "volume_step": step,
        "volume_min": vmin,
        "volume_max": vmax,
        "margin_hedged": float(getattr(sym, "margin_hedged", 0) or 0),
        "hedging": int(getattr(info, "margin_mode", -1)) == hedging_mode,
        "digits": int(getattr(sym, "digits", 2) or 2),
        "stops_level": int(getattr(sym, "trade_stops_level", 0) or 0),
        "point": float(getattr(sym, "point", 0) or 0),
    }


def _news_positions(symbol):
    positions = mt5.positions_get(symbol=symbol) or []
    return [p for p in positions if int(getattr(p, "magic", 0) or 0) == NEWS_HEDGE_MAGIC]


def _news_filling_mode(symbol):
    """IOC nếu symbol có. FOK dễ bị từ chối khi spread giãn lúc tin."""
    info = mt5.symbol_info(symbol)
    if info is not None and int(getattr(info, "filling_mode", 0) or 0) & 2:
        return 1
    return get_filling_mode(symbol)


def _news_filled_volume(result, lot):
    if result is None:
        return 0.0
    partial = getattr(mt5, "TRADE_RETCODE_DONE_PARTIAL", 10010)
    if result.retcode not in (mt5.TRADE_RETCODE_DONE, partial):
        return 0.0
    volume = float(getattr(result, "volume", 0) or 0)
    if result.retcode == mt5.TRADE_RETCODE_DONE and volume <= 0:
        return float(lot)
    return volume


def _news_remember(symbol, lot, result, request, status, detail, position=None):
    """Xếp kết quả hedge tin. Chưa ghi file, chưa Telegram."""
    _NEWS_HISTORY_QUEUE.append((symbol, lot, result, request, status, detail, position))


def _news_history_line(symbol, lot, result, request, status, detail):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ticket = getattr(result, "order", None)
    retcode = getattr(result, "retcode", None)
    entry = (
        f"{timestamp} | account={CURRENT_ACCOUNT_NAME or '-'} | symbol={symbol} | lot={lot} | status={status} | "
        f"ticket={ticket if ticket is not None else '-'} | "
        f"retcode={retcode if retcode is not None else '-'} | "
        f"comment={request.get('comment', '') if isinstance(request, dict) else ''}"
    )
    if detail:
        entry += f" | detail={detail}"
    return entry


def _news_send_summary_telegram(queued):
    """Một tin sau khi mọi order_send của hedge tin đã xong. Không đọc history deals."""
    try:
        import telegram_notify
    except Exception:
        return
    opens = []
    modifies = []
    fails = []
    for _symbol, lot, result, request, status, detail, position in queued:
        side = _request_side_label(request, position) or ""
        order_ticket = getattr(result, "order", None) if result is not None else None
        if status == "SUCCESS":
            price = request.get("price") if isinstance(request, dict) else None
            opens.append(f"{side} {lot} giá {price} ticket {order_ticket}")
        elif status == "MODIFY_SUCCESS":
            sl = request.get("sl") if isinstance(request, dict) else None
            pos_ticket = getattr(position, "ticket", None) if position is not None else order_ticket
            modifies.append(f"{side} ticket {pos_ticket} SL {sl}")
        elif status in ("FAILED", "MODIFY_FAILED", "CLOSE_FAILED"):
            fails.append(f"{side} {lot} {status} {detail}".strip())
    if not opens and not modifies and not fails:
        return
    lines = [f"account: {CURRENT_ACCOUNT_NAME or '-'}"]
    if opens:
        lines.append(f"Mở {len(opens)} lệnh")
        lines.extend(opens)
    if modifies:
        lines.append(f"Gán SL {len(modifies)} lệnh")
        lines.extend(modifies)
    if fails:
        lines.append(f"Lỗi {len(fails)}")
        lines.extend(fails)
    title = "HEDGE TIN CÓ LỖI" if fails else "HEDGE TIN"
    try:
        telegram_notify.send_alert(telegram_notify.build_message(title, lines))
    except Exception:
        pass


def _news_flush_history():
    """Ghi lịch sử một lần và gửi một Telegram. Không đi qua save_trade_history."""
    queued = list(_NEWS_HISTORY_QUEUE)
    _NEWS_HISTORY_QUEUE.clear()
    if not queued:
        return
    try:
        import watch_state
    except Exception:
        watch_state = None
    lines = []
    for symbol, lot, result, request, status, detail, _position in queued:
        lines.append(_news_history_line(symbol, lot, result, request, status, detail))
        if status == "SUCCESS" and watch_state is not None and result is not None:
            try:
                watch_state.remember_skip_open_order(getattr(result, "order", None))
            except Exception:
                pass
    block = "\n".join(reversed(lines))
    existing = ""
    if HISTORY_FILE.exists():
        existing = HISTORY_FILE.read_text(encoding="utf-8").strip()
    if existing:
        HISTORY_FILE.write_text(block + "\n" + existing + "\n", encoding="utf-8")
    else:
        HISTORY_FILE.write_text(block + "\n", encoding="utf-8")
    print("Lệnh hedge tin đã xong. Gửi một Telegram tổng.", flush=True)
    _news_send_summary_telegram(queued)


def _news_send(symbol, side, lot):
    tick = mt5.symbol_info_tick(symbol)
    if tick is None or tick.bid <= 0 or tick.ask <= 0:
        print(f"{side.upper()}: không lấy được tick", flush=True)
        return None, 0.0
    price = float(tick.ask if side == "buy" else tick.bid)
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(lot),
        "type": mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL,
        "price": price,
        "deviation": DEFAULT_DEVIATION,
        "magic": NEWS_HEDGE_MAGIC,
        "comment": "news-hedge",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": _news_filling_mode(symbol),
    }
    result = mt5.order_send(request)
    filled = _news_filled_volume(result, lot)
    label = side.upper()
    if result is None:
        err = mt5.last_error()
        print(f"{label}: không có phản hồi từ terminal. {err}", flush=True)
        _news_remember(
            symbol, lot, None, request, "FAILED",
            f"news-hedge | không phản hồi | last_error={err}",
        )
        return None, 0.0
    if filled + 1e-8 < float(lot):
        print(
            f"{label}: khớp {filled} / {lot}. retcode={result.retcode} ({result.comment})",
            flush=True,
        )
        _news_remember(
            symbol, lot, result, request, "FAILED",
            f"news-hedge | filled={filled} | retcode={result.retcode} | {result.comment}",
        )
        return result, filled
    print(f"{label}: khớp {filled} lot. Ticket {result.order}", flush=True)
    _news_remember(symbol, lot, result, request, "SUCCESS", "news-hedge")
    return result, filled


def _close_news_except(symbol, keep_tickets, reason):
    print(reason, flush=True)
    closed = True
    for _ in range(4):
        victims = [p for p in _news_positions(symbol) if int(p.ticket) not in keep_tickets]
        if not victims:
            return True
        closed = False
        for position in victims:
            live = find_position_by_ticket(position.ticket)
            if live is None:
                continue
            if close_position(live, confirm=False) is not None:
                closed = True
        time.sleep(0.05)
    left = [p for p in _news_positions(symbol) if int(p.ticket) not in keep_tickets]
    if left:
        print(f"Còn {len(left)} vị thế magic {NEWS_HEDGE_MAGIC} chưa đóng được.", flush=True)
        return False
    return closed


def _news_execute_pair(symbol, lot):
    """BUY rồi SELL. SELL lỗi thì gửi lại tối đa 2 lần, vẫn hở thì đóng đúng cặp này."""
    before = {int(p.ticket) for p in _news_positions(symbol)}
    _result, buy_filled = _news_send(symbol, "buy", lot)
    if buy_filled + 1e-8 < float(lot):
        print(f"BUY {lot} không khớp đủ. Đóng phần đã mở của cặp này và dừng vòng.", flush=True)
        _close_news_except(symbol, before, "Đóng phần BUY vừa mở.")
        return False
    sell_filled = 0.0
    for attempt in range(3):
        need = round(float(lot) - sell_filled, 8)
        if need <= 1e-8:
            break
        _result, got = _news_send(symbol, "sell", need)
        sell_filled = round(sell_filled + got, 8)
        if sell_filled + 1e-8 >= float(lot):
            return True
        if attempt < 2:
            print(
                f"SELL chưa đủ ({sell_filled}/{lot}). Gửi lại lần {attempt + 1}/2.",
                flush=True,
            )
    print(f"SELL {lot} vẫn hở sau 2 lần gửi lại. Đóng cặp này và dừng vòng.", flush=True)
    _close_news_except(symbol, before, "Đóng cặp vừa hở.")
    return False


def _news_assign_sl(symbol, position, sl_price):
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": symbol,
        "position": int(position.ticket),
        "tp": 0.0,
        "sl": float(sl_price),
        "magic": NEWS_HEDGE_MAGIC,
        "comment": "news-hedge SL",
    }
    result = mt5.order_send(request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        comment = getattr(result, "comment", "") if result is not None else mt5.last_error()
        retcode = getattr(result, "retcode", None)
        print(f"Gán SL ticket {position.ticket} thất bại. retcode={retcode} ({comment})", flush=True)
        _news_remember(
            symbol, position.volume, result, request, "MODIFY_FAILED",
            f"news-hedge SL | ticket={position.ticket} | {comment}",
            position=position,
        )
        return False
    print(f"Gán SL ticket {position.ticket} = {sl_price}", flush=True)
    _news_remember(
        symbol, position.volume, result, request, "MODIFY_SUCCESS",
        f"news-hedge SL | ticket={position.ticket} | sl={sl_price}",
        position=position,
    )
    return True


def _news_finish_sl(symbol, account, params, keep_tickets, market):
    positions = [p for p in _news_positions(symbol) if int(p.ticket) not in keep_tickets]
    buys = [p for p in positions if int(p.type) == mt5.ORDER_TYPE_BUY]
    sells = [p for p in positions if int(p.type) == mt5.ORDER_TYPE_SELL]
    step = market["volume_step"]
    buy_units = sum(_news_round_units(p.volume, step) for p in buys)
    sell_units = sum(_news_round_units(p.volume, step) for p in sells)
    buy_lot = _news_lot_from_units(buy_units, market["volume_step"])
    sell_lot = _news_lot_from_units(sell_units, market["volume_step"])
    print(f"V_actual BUY={_news_fmt_num(buy_lot)} | SELL={_news_fmt_num(sell_lot)}", flush=True)
    if buy_units <= 0 and sell_units <= 0:
        print("Không còn vị thế của lần bắn này.", flush=True)
        return
    if buy_units != sell_units:
        _close_news_except(
            symbol, keep_tickets,
            f"BUY {buy_lot} và SELL {sell_lot} không bằng nhau. Đóng các vị thế của lần bắn này.",
        )
        return

    def _avg(rows):
        volume = sum(float(p.volume) for p in rows)
        return sum(float(p.volume) * float(p.price_open) for p in rows) / volume

    p_ref = _avg(buys)
    sell_avg = _avg(sells)
    s_real = p_ref - sell_avg
    cs = market["contract_size"]
    step = market["volume_step"]
    risk_real = _news_money(params["buffer_pips"] + s_real, buy_units, cs, step)
    buffer_eff = params["buffer_pips"]
    print(
        f"Bước 5: P_ref={p_ref} | S_real={s_real} | Risk_real={_news_fmt_num(risk_real)}",
        flush=True,
    )
    if risk_real > params["max_risk"] + 1e-6:
        buffer_eff = params["max_risk"] / (buy_units * cs * step) - s_real
        print(f"Risk_real vượt MAX_RISK. BUFFER_eff = {_news_fmt_num(buffer_eff)}", flush=True)
    if buffer_eff <= 0:
        _close_news_except(symbol, keep_tickets, "BUFFER_eff <= 0. Đóng hết vị thế của lần bắn này.")
        return
    cap = get_xauusd_max_loss(account) if is_xauusd_symbol(symbol) else None
    held_risk = _news_money(buffer_eff + s_real, buy_units, cs, step)
    if cap is not None and held_risk > float(cap) + 1e-6:
        _close_news_except(
            symbol, keep_tickets,
            f"Lỗ thiết kế {_news_fmt_num(held_risk)} lớn hơn xauusd_max_loss {_news_fmt_num(cap)}. Đóng hết.",
        )
        return

    buy_sl = sltp_price(symbol, p_ref - params["sl_pips"])
    sell_sl = sltp_price(symbol, p_ref + params["sl_pips"])
    if buy_sl <= 0 or sell_sl <= 0:
        _close_news_except(symbol, keep_tickets, "Mức SL không hợp lệ. Đóng hết vị thế của lần bắn này.")
        return
    invalid = []
    for position in buys:
        if buy_sl >= float(position.price_open):
            invalid.append(position.ticket)
    for position in sells:
        if sell_sl <= float(position.price_open):
            invalid.append(position.ticket)
    min_dist = market["stops_level"] * market["point"]
    tick = mt5.symbol_info_tick(symbol)
    too_close = False
    if min_dist > 0 and tick is not None:
        too_close = buy_sl > float(tick.bid) - min_dist or sell_sl < float(tick.ask) + min_dist
    if invalid or too_close:
        why = "SL nằm sai phía giá mở" if invalid else "SL nằm trong stops level của broker"
        _close_news_except(symbol, keep_tickets, f"{why}. Đóng hết vị thế của lần bắn này.")
        return

    failed = False
    for position in buys:
        if not _news_assign_sl(symbol, position, buy_sl):
            failed = True
            break
    if not failed:
        for position in sells:
            if not _news_assign_sl(symbol, position, sell_sl):
                failed = True
                break
    if failed:
        _close_news_except(symbol, keep_tickets, "Gán SL lỗi. Đóng hết vị thế của lần bắn này.")
        return

    print("Đã gán SL. Không theo dõi tiếp.", flush=True)
    _print_news_hedge_outcome(
        "Bước 6 — kịch bản sau khi khớp, bot không can thiệp thêm",
        p_ref, sell_avg, buy_sl, sell_sl, buffer_eff, buy_units, cs, step,
        market["digits"], params["max_risk"],
    )


def _news_guard_margin(symbol, plan, market):
    """Lấy mức ký quỹ một chiều cao hơn giữa công thức và order_calc_margin."""
    lot = plan["chunk_max_lot"]
    formula = plan["guard_margin"]
    calc = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, symbol, float(lot), float(market["ask"]))
    need = formula if formula is not None else 0.0
    if calc is not None and float(calc) > need:
        need = float(calc)
        print(
            f"order_calc_margin chunk {_news_fmt_num(lot)} = {_news_fmt_num(calc)} "
            f"(công thức {_news_fmt_num(formula) if formula is not None else '?'})",
            flush=True,
        )
    return need


def open_news_hedge_multi(account, symbol, max_risk, sl_pips, buffer_pips, max_exec_ms):
    """Bước 1–5. Không đóng đầu còn lại khi giá quay về mức đệm."""
    params = {
        "max_risk": _news_require_positive("max_risk", max_risk),
        "sl_pips": _news_require_positive("sl_pips", sl_pips),
        "buffer_pips": _news_require_positive("buffer_pips", buffer_pips),
        "max_exec_ms": _news_require_positive("max_exec_ms", max_exec_ms),
    }
    symbol = select_symbol(symbol, account)
    _NEWS_HISTORY_QUEUE.clear()
    print("open-2-side-news-multi-auto: bỏ qua lot. V tính từ MAX_RISK. Không copy.")
    market = _news_read_market(symbol, fast=False)
    plan = build_news_hedge_plan(
        leverage=market["leverage"], stop_out=market["stop_out"], ask=market["ask"], bid=market["bid"],
        equity=market["equity"], free_margin=market["free_margin"], contract_size=market["contract_size"],
        volume_step=market["volume_step"], volume_min=market["volume_min"], volume_max=market["volume_max"],
        t_benchmark_ms=None, margin_hedged=market["margin_hedged"], hedging=market["hedging"],
        digits=market["digits"], **params,
    )
    _news_apply_account_cap(plan, account, symbol)
    _print_news_hedge_plan(plan, "preview")
    if plan["blockers"]:
        print("Đã hủy open-2-side-news-multi-auto.")
        return None
    if not confirm_action("Bắn BUY/SELL xen kẽ theo kế hoạch hedge tin? SL gán sau khi khớp."):
        print("Đã hủy open-2-side-news-multi-auto.")
        return None

    market = _news_read_market(symbol, fast=True)
    plan = build_news_hedge_plan(
        leverage=market["leverage"], stop_out=market["stop_out"], ask=market["ask"], bid=market["bid"],
        equity=market["equity"], free_margin=market["free_margin"], contract_size=market["contract_size"],
        volume_step=market["volume_step"], volume_min=market["volume_min"], volume_max=market["volume_max"],
        t_benchmark_ms=None, margin_hedged=market["margin_hedged"], hedging=market["hedging"],
        digits=market["digits"], **params,
    )
    _news_apply_account_cap(plan, account, symbol)
    if plan["blockers"]:
        print("Giá vừa đọc lại không còn đủ điều kiện:")
        for blocker in plan["blockers"]:
            print(f"- {blocker}")
        print("Đã hủy open-2-side-news-multi-auto.")
        return None

    filling = _news_filling_mode(symbol)
    filling_name = {0: "FOK", 1: "IOC", 2: "RETURN"}.get(filling, str(filling))
    print(f"Filling: {filling_name}. Magic {NEWS_HEDGE_MAGIC}.", flush=True)
    preexisting = {int(p.ticket) for p in _news_positions(symbol)}
    if preexisting:
        print(f"Đang có {len(preexisting)} vị thế magic này từ trước. Lần bắn này không đụng đến chúng.")

    print(
        f"Bước 2: BUY {_news_fmt_num(plan['bench_lot'])} rồi SELL {_news_fmt_num(plan['bench_lot'])}.",
        flush=True,
    )
    started = time.perf_counter()
    locked_units = plan["v_units"]
    bench_ok = _news_execute_pair(symbol, plan["bench_lot"])
    t_benchmark_ms = (time.perf_counter() - started) * 1000.0
    print(f"T_benchmark = {t_benchmark_ms:.1f} ms", flush=True)
    if not bench_ok:
        print("Cặp mẫu thất bại. Dừng.", flush=True)
        return None

    info = mt5.account_info()
    if info is not None:
        market["free_margin"] = float(info.margin_free)
        market["equity"] = float(info.equity)
    tick = mt5.symbol_info_tick(symbol)
    if tick is not None and tick.ask > 0 and tick.bid > 0:
        market["ask"] = float(tick.ask)
        market["bid"] = float(tick.bid)
    plan = build_news_hedge_plan(
        leverage=market["leverage"], stop_out=market["stop_out"], ask=market["ask"], bid=market["bid"],
        equity=market["equity"], free_margin=market["free_margin"], contract_size=market["contract_size"],
        volume_step=market["volume_step"], volume_min=market["volume_min"], volume_max=market["volume_max"],
        t_benchmark_ms=t_benchmark_ms, margin_hedged=market["margin_hedged"], hedging=market["hedging"],
        digits=market["digits"], locked_units=locked_units, **params,
    )
    _print_news_hedge_plan(plan, "live")
    if plan["blockers"] or plan["chunk_lots"] is None:
        _close_news_except(symbol, preexisting, "Điều kiện sau cặp mẫu không đạt. Đóng cặp mẫu.")
        return None
    if plan["chunk_lots"]:
        need = _news_guard_margin(symbol, plan, market)
        if need > market["free_margin"] + 1e-6:
            _close_news_except(
                symbol, preexisting,
                f"Margin Guardrail không đạt ({_news_fmt_num(need)} > Free Margin "
                f"{_news_fmt_num(market['free_margin'])}). Đóng cặp mẫu.",
            )
            return None

    loop_started = time.perf_counter()
    for lot in plan["chunk_lots"]:
        elapsed = (time.perf_counter() - loop_started) * 1000.0
        if elapsed > params["max_exec_ms"]:
            print(
                f"Hết MAX_EXEC_TIME {params['max_exec_ms']} ms (đã {elapsed:.1f} ms). "
                f"Dừng trước cặp {_news_fmt_num(lot)}.",
                flush=True,
            )
            break
        print(f"Cặp {_news_fmt_num(lot)}: BUY rồi SELL", flush=True)
        if not _news_execute_pair(symbol, lot):
            break

    _news_finish_sl(symbol, account, params, preexisting, market)
    return True


def _print_open_duration(started):
    elapsed = time.perf_counter() - started
    print(f"Thời gian mở 1 lệnh: {elapsed:.3f} giây")


def run_action_on_account(account, args, lot):
    global _ACTIVE_XAUUSD_MAX_LOSS
    _ACTIVE_XAUUSD_MAX_LOSS = account.get("xauusd_max_loss")
    # action=open: đo từ lúc nối terminal đến lúc ngắt, gồm tính TP/SL và order_send.
    open_started = time.perf_counter() if args.action == "open" else None
    try:
        connect_mt5(account)
        if args.action == "open":
            open_trade(account, args.symbol, args.side, lot, args.tp_price, args.sl_price, args.comment)
            mt5.shutdown()
            _print_open_duration(open_started)
            open_started = None
        elif args.action == "open-2-side":
            open_two_side(account, args.symbol, lot, args.tp_price, args.sl_price, args.comment)
        elif args.action == NEWS_HEDGE_ACTION:
            open_news_hedge_multi(
                account, args.symbol, args.max_risk, args.sl_pips, args.buffer_pips, args.max_exec_ms,
            )
        elif args.action == "pending":
            open_pending_trade(
                account, args.symbol, args.side, args.pending_type, args.price, lot,
                args.tp_price, args.sl_price, args.comment,
            )
        elif args.action == "cancel-pending":
            cancel_all_pending_orders()
        elif args.action == "close":
            close_positions_volume(account, args.symbol, args.side, lot)
        elif args.action == "close-all":
            close_all_positions()
        elif args.action == "modify-all":
            if args.tp_price is None and args.sl_price is None:
                raise RuntimeError("Cần cung cấp ít nhất --tp-price hoặc --sl-price để thay đổi")
            modify_all_positions_tp_sl(args.tp_price, args.sl_price)
        elif args.action == "modify-all-if":
            register_modify_all_if(
                account, args.symbol, args.sl_price, args.tp_price,
                price=getattr(args, "price", None),
                zone_low=getattr(args, "zone_low", None),
                zone_high=getattr(args, "zone_high", None),
            )
        elif args.action == "cancel-modify-if":
            cancel_modify_if_jobs(account)
        elif args.action == "status":
            print_account_info()
            print_open_positions()
            print_pending_orders()
            _print_modify_if_jobs(account["name"])
        else:
            raise RuntimeError(f"Action không hỗ trợ: {args.action!r}.")
    finally:
        if open_started is not None:
            mt5.shutdown()
            _print_open_duration(open_started)
        _ACTIVE_XAUUSD_MAX_LOSS = _UNSET_MAX_LOSS


def execute_request(account_name, action, symbol="XAUUSD", side="buy", lot=0.01,
                     tp_price=None, sl_price=None, comment="Python trader test",
                     no_ask=False, copy_names=None, price=None, pending_type="limit",
                     zone_low=None, zone_high=None,
                     max_risk=375.0, sl_pips=15.0, buffer_pips=8.0, max_exec_ms=300.0):
    """Thực thi 1 hành động cho account_name,
    kèm copy sang các account trong copy_names nếu action cho phép.

    copy_names=None (không truyền gì) -> tự lấy theo cấu hình auto_copy_enabled/
    auto_copy_targets của account trong xml/accounts.xml. Truyền list cụ thể
    (kể cả []) sẽ override, không dùng cấu hình auto-copy.
    """
    global NO_ASK, TELEGRAM_IS_COPY
    NO_ASK = no_ask
    TELEGRAM_IS_COPY = False

    primary_account = get_account(account_name)

    auto_copy_used = False
    if copy_names is None:
        copy_names = get_auto_copy_targets(primary_account)
        auto_copy_used = bool(copy_names)
    else:
        copy_names = list(copy_names)

    class _Args:
        pass

    args = _Args()
    args.action = action
    args.symbol = symbol
    args.side = side
    args.tp_price = tp_price
    args.sl_price = sl_price
    args.comment = comment
    args.price = price
    args.pending_type = (pending_type or "limit").lower()
    args.zone_low = zone_low
    args.zone_high = zone_high
    args.max_risk = max_risk
    args.sl_pips = sl_pips
    args.buffer_pips = buffer_pips
    args.max_exec_ms = max_exec_ms

    lot_scale_actions = {"open", "open-2-side", "pending", "close"}

    try:
        if action == NEWS_HEDGE_DEMO_ACTION:
            print_news_hedge_demo(max_risk, sl_pips, buffer_pips, max_exec_ms)
            if copy_names:
                print("Demo không copy và không nối MT5.")
            return
        run_action_on_account(primary_account, args, lot)

        if auto_copy_used and action in COPYABLE_ACTIONS:
            print(f"[AUTO-COPY] Tài khoản '{account_name}' được cấu hình tự động copy sang: {', '.join(copy_names)}")

        if copy_names and action not in COPYABLE_ACTIONS:
            print(
                f"Lưu ý: copy chỉ áp dụng cho action open/open-2-side/pending/cancel-pending/close/close-all/"
                f"modify-all/modify-all-if/cancel-modify-if, bỏ qua sao chép cho action '{action}'."
            )
        elif copy_names:
            for copy_name in copy_names:
                print(f"\n--- [COPY] Đang thực thi sang tài khoản {copy_name} ---")
                TELEGRAM_IS_COPY = True
                try:
                    source_copy = get_account(copy_name)
                    copy_account = dict(source_copy)
                    own_max_loss = _optional_max_loss(source_copy.get("xauusd_max_loss"))
                    inherited_max_loss = resolve_copy_xauusd_max_loss(copy_account, primary_account)
                    copy_account["xauusd_max_loss"] = inherited_max_loss
                    mt5.shutdown()
                    multi = get_account_multi(copy_account)
                    lot_for_copy = lot * multi if action in lot_scale_actions else lot
                    if action in lot_scale_actions and lot_for_copy != lot:
                        print(f"Lot gốc: {lot} → Lot copy ({copy_name}, MULTI={multi}): {lot_for_copy}")
                    if own_max_loss is None and inherited_max_loss is not None:
                        primary_loss = _optional_max_loss(primary_account.get("xauusd_max_loss"))
                        print(
                            f"[COPY] xauusd_max_loss kế thừa từ '{account_name}': "
                            f"{primary_loss} × multi {multi} = {inherited_max_loss}"
                        )
                    elif inherited_max_loss is None:
                        print(f"[COPY] xauusd_max_loss: không giới hạn (gốc và đích đều bỏ trống)")
                    run_action_on_account(copy_account, args, lot_for_copy)
                except Exception as copy_exc:
                    print(f"[COPY LỖI - {copy_name}] {copy_exc}")
                finally:
                    TELEGRAM_IS_COPY = False
    except Exception as exc:
        print(exc)
    finally:
        _news_flush_history()
        mt5.shutdown()


def main():
    parser = argparse.ArgumentParser(description="MT5 trader demo")
    parser.add_argument(
        "--account",
        choices=[acc["name"] for acc in ACCOUNTS],
        required=True,
        help="Bắt buộc: chọn tài khoản chính theo name khai báo trong accounts.xml (vd: prop_demo, prop_1, real, fake)",
    )
    parser.add_argument(
        "--action",
        choices=[
            "open", "open-2-side", NEWS_HEDGE_ACTION, NEWS_HEDGE_DEMO_ACTION,
            "pending", "cancel-pending", "close", "close-all", "modify-all",
            "modify-all-if", "cancel-modify-if", "status",
        ],
        required=True,
    )
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--side", choices=["buy", "sell"], default="buy")
    parser.add_argument("--lot", type=float, default=0.01)
    parser.add_argument("--tp-price", type=float, default=None)
    parser.add_argument("--sl-price", type=float, default=None)
    parser.add_argument("--price", type=float, default=None, help="Giá chờ pending, hoặc mức kích hoạt modify-all-if")
    parser.add_argument("--zone-low", type=float, default=None, help="Cạnh dưới vùng kích hoạt modify-all-if")
    parser.add_argument("--zone-high", type=float, default=None, help="Cạnh trên vùng kích hoạt modify-all-if")
    parser.add_argument(
        "--pending-type", choices=["limit", "stop"], default="limit",
        help="Loại lệnh chờ: limit hoặc stop (mặc định limit)",
    )
    parser.add_argument("--comment", default="Python trader test")
    parser.add_argument("--max-risk", type=float, default=375.0, help="USD tối đa cho hedge tin (mặc định 375)")
    parser.add_argument("--sl-pips", type=float, default=15.0, help="Khoảng cách SL hedge tin, tính bằng giá (mặc định 15)")
    parser.add_argument("--buffer-pips", type=float, default=8.0, help="Đệm sau khi một đầu cháy, tính bằng giá (mặc định 8)")
    parser.add_argument("--max-exec-ms", type=float, default=300.0, help="Trần thời gian bắn các cặp sau cặp mẫu, ms (mặc định 300)")
    parser.add_argument(
        "--no-ask", action="store_true",
        help="Bắt buộc phải có để thực thi lệnh thật. Nếu không truyền, chương trình chỉ in thông báo xem trước và không gửi lệnh nào, kể cả copy.",
    )
    parser.add_argument(
        "--copy", default=None,
        help="Danh sách account name cần copy lệnh sang, phân tách bằng dấu phẩy, ví dụ: prop_demo,prop_1. "
             "Không truyền --copy sẽ tự dùng cấu hình auto_copy_enabled/auto_copy_targets của account trong accounts.xml (nếu có). "
             'Truyền --copy "" để tắt hẳn copy (bỏ qua cả auto-copy).',
    )

    args = parser.parse_args()

    if args.action == "open" and args.sl_price is None:
        parser.error("action=open bắt buộc phải có --sl-price (stop loss); --tp-price tùy chọn")
    if args.action in (NEWS_HEDGE_ACTION, NEWS_HEDGE_DEMO_ACTION):
        if args.max_risk <= 0 or args.sl_pips <= 0 or args.buffer_pips <= 0 or args.max_exec_ms <= 0:
            parser.error("hedge tin: --max-risk, --sl-pips, --buffer-pips, --max-exec-ms đều phải > 0")
    if args.action == "open-2-side":
        if args.sl_price is None or args.sl_price <= 0:
            parser.error(
                "action=open-2-side bắt buộc --sl-price là khoảng cách > 0 (ví dụ 10), "
                "không phải mức giá tuyệt đối; --tp-price là khoảng cách tùy chọn (ví dụ 50)"
            )
        if args.tp_price is not None and args.tp_price <= 0:
            parser.error("action=open-2-side: --tp-price phải là khoảng cách > 0, hoặc bỏ trống")
    if args.action == "close" and (args.lot is None or args.lot <= 0):
        parser.error("action=close bắt buộc --lot > 0 (số lot muốn đóng, cho phép nhỏ hơn vị thế)")
    if args.action == "pending":
        if args.price is None:
            parser.error("action=pending bắt buộc phải có --price (giá chờ)")
        if args.sl_price is None:
            parser.error("action=pending bắt buộc phải có --sl-price (stop loss); --tp-price tùy chọn")

    if args.action == "modify-all-if":
        if args.sl_price is None:
            parser.error("action=modify-all-if bắt buộc phải có --sl-price; --tp-price tùy chọn")
        if args.price is None and args.zone_low is None and args.zone_high is None:
            parser.error("action=modify-all-if cần --price hoặc --zone-low/--zone-high")

    copy_names = None
    if args.copy is not None:
        copy_names = [t.strip() for t in args.copy.split(",") if t.strip()]

    execute_request(
        args.account, args.action, args.symbol, args.side, args.lot,
        args.tp_price, args.sl_price, args.comment, args.no_ask, copy_names,
        price=args.price, pending_type=args.pending_type,
        zone_low=args.zone_low, zone_high=args.zone_high,
        max_risk=args.max_risk, sl_pips=args.sl_pips,
        buffer_pips=args.buffer_pips, max_exec_ms=args.max_exec_ms,
    )


if __name__ == "__main__":
    main()
