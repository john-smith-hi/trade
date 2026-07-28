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
#   - path   : đường dẫn terminal64.exe (Exness và FTMO dùng terminal riêng).
#   - suffix : hậu tố symbol theo broker — Exness = "m", FTMO = "".
#              Ví dụ --symbol XAUUSD → XAUUSDm (Exness) hoặc XAUUSD (FTMO).
#   - multi  : hệ số nhân lot khi copy lệnh sang tài khoản đó.
#   - auto_copy_enabled/auto_copy_targets : bật thì account đó sẽ TỰ ĐỘNG copy
#     lệnh sang các account trong auto_copy_targets mỗi khi chạy (không cần
#     truyền --copy). Ví dụ: account "real" auto_copy_targets=prop_demo,prop_1.
#   - xml/accounts.xml chứa mật khẩu thật nên đã nằm trong .gitignore, không bị commit.
#   - Xem xml/accounts.example.xml để biết mẫu cấu trúc.
#
# THAM SỐ BẮT BUỘC
#   --account   tên account khai báo trong xml/accounts.xml (vd: fake, real, prop_demo)
#   --action    status | open | close-all | modify-all
#
# THAM SỐ KHÁC
#   --symbol --side --lot --tp-price --sl-price --comment --copy --no-ask
#   (Không có --no-ask → chỉ xem trước, KHÔNG gửi lệnh thật.)
#   TP/SL là mức giá cụ thể (không phải số điểm).
#   action=open BẮT BUỘC có cả --tp-price và --sl-price.
#     BUY : SL < giá mở < TP
#     SELL: TP < giá mở < SL
#   Không truyền --copy → tự dùng auto_copy_enabled/auto_copy_targets của account (nếu có).
#   Truyền --copy "tên1,tên2" → copy đúng danh sách này (override auto-copy).
#   Truyền --copy "" → tắt hẳn copy cho lần chạy đó (bỏ qua cả auto-copy).
#
# VÍ DỤ
#   # Xem trạng thái tài khoản
#   python mt5.py --account prop_demo --action status
#
#   # Mở lệnh (xem trước) — bắt buộc TP + SL đúng hướng
#   python mt5.py --account fake --action open --symbol XAUUSD --side buy --lot 0.01 --tp-price 60000 --sl-price 58000
#
#   # Mở lệnh thật
#   python mt5.py --account fake --action open --symbol XAUUSD --side buy --lot 0.01 --tp-price 60000 --sl-price 58000 --no-ask
#
#   # Sửa TP/SL tất cả lệnh đang mở (hiện ước tính lời/lỗ so giá mở)
#   python mt5.py --account fake --action modify-all --tp-price 60000 --sl-price 58000 --no-ask
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
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import MetaTrader5 as mt5

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

COPYABLE_ACTIONS = {"open", "close-all", "modify-all"}
NO_ASK = False
DEFAULT_MAGIC = 234567
DEFAULT_DEVIATION = 20
CURRENT_ACCOUNT_NAME = None


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


def load_accounts():
    """Đọc danh sách tài khoản từ accounts.xml.

    Nếu accounts.xml chưa tồn tại, tự tạo từ accounts.example.xml (hoặc file rỗng
    nếu không có mẫu) để lần đầu chạy không bị lỗi thiếu file.
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

        accounts.append({
            "name": name,
            "login": login,
            "password": _xml_text(node, "password"),
            "server": _xml_text(node, "server"),
            "path": _xml_text(node, "path") or None,
            "suffix": _xml_text(node, "suffix"),
            "multi": multi,
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
        ET.SubElement(node, "path").text = str(acc.get("path") or "")
        ET.SubElement(node, "suffix").text = str(acc.get("suffix", ""))
        ET.SubElement(node, "multi").text = str(acc.get("multi", 1.0))
        ET.SubElement(node, "auto_copy_enabled").text = "true" if acc.get("auto_copy_enabled") else "false"
        ET.SubElement(node, "auto_copy_targets").text = ",".join(acc.get("auto_copy_targets") or [])

    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")
    tree.write(ACCOUNTS_FILE, encoding="UTF-8", xml_declaration=True)


ACCOUNTS = load_accounts()


def reload_accounts():
    """Nạp lại ACCOUNTS từ accounts.xml (dùng sau khi sửa file hoặc lưu qua GUI)."""
    global ACCOUNTS
    ACCOUNTS = load_accounts()
    return ACCOUNTS


def get_account(account_name):
    for acc in ACCOUNTS:
        if acc["name"] == account_name:
            return acc
    raise RuntimeError(f"Không tìm thấy cấu hình account tên: {account_name}")


def get_account_multi(account):
    return account.get("multi", 1.0)


def get_auto_copy_targets(account):
    """Danh sách tài khoản tự động copy lệnh sang, cấu hình theo từng account
    trong xml/accounts.xml (auto_copy_enabled + auto_copy_targets)."""
    if not account.get("auto_copy_enabled"):
        return []
    return list(account.get("auto_copy_targets") or [])


def save_trade_history(symbol, lot, result, request, status, detail=""):
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


def confirm_action(message):
    """Xác nhận hành động. Không có --no-ask → chỉ xem trước, KHÔNG gửi lệnh thật.
    Các bước in thông tin / ước tính lời-lỗ phía trước vẫn luôn chạy.
    """
    if NO_ASK:
        return True
    print(f"[XEM TRƯỚC] {message}")
    print("[XEM TRƯỚC] Chưa truyền --no-ask nên KHÔNG có lệnh nào được thực thi thật (kể cả copy).")
    return False


def connect_mt5(account):
    global CURRENT_ACCOUNT_NAME

    terminal_path = account.get("path")
    if terminal_path and "CHANGE_ME" in str(terminal_path):
        raise RuntimeError(
            f"Chưa cấu hình đường dẫn terminal MT5 cho account '{account['name']}'. "
            f"Điền trường \"path\" trong ACCOUNTS trỏ tới terminal64.exe do broker cấp (VD: FTMO)."
        )

    # Ngắt phiên MT5 cũ trước khi gắn terminal khác (Exness -> FTMO Demo -> FTMO Server).
    # Nếu không shutdown, tick/symbol có thể còn cache từ terminal trước -> giá vào sai.
    mt5.shutdown()

    # Với các broker/prop-firm khác (VD: FTMO), phải chỉ định "path" tới terminal MT5 riêng của họ,
    # vì terminal MT5 mặc định (thường là bản Exness) không có server tương ứng nên sẽ bị IPC timeout.
    init_kwargs = {
        "login": account["login"],
        "password": account["password"],
        "server": account["server"],
        "timeout": 60000,
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
            f"(mong đợi login {account['login']}). Kiểm tra trường \"path\" trong accounts.xml."
        )

    CURRENT_ACCOUNT_NAME = account["name"]
    terminal_label = terminal_path or "(terminal mặc định đang chạy)"
    print(f"Đang sử dụng tài khoản {account['name']}: {account['login']} | server: {account['server']}")
    print(f"Terminal: {terminal_label}")
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


def print_open_tp_sl_estimate(symbol, side, entry_price, tp_price, sl_price, lot):
    """In ước tính lời/lỗ tại TP/SL. Luôn chạy ở chế độ xem trước (kể cả khi chưa --no-ask)."""
    if tp_price is None and sl_price is None:
        print("Không có TP/SL để ước tính lời/lỗ.", flush=True)
        return

    try:
        contract_size = resolve_contract_size(symbol)
        estimated = estimate_tp_sl_pnl(side, entry_price, tp_price, sl_price, lot, contract_size)
        # Luôn in rõ — không phụ thuộc --no-ask (confirm_action chỉ chặn gửi lệnh thật).
        if "tp" in estimated:
            print(f"Ước tính lời TP: {estimated['tp']:.8f}", flush=True)
        if "sl" in estimated:
            print(f"Ước tính lỗ SL: {estimated['sl']:.8f}", flush=True)
        if not estimated:
            print("Không ước tính được lời/lỗ (thiếu TP/SL).", flush=True)
    except Exception as exc:
        # Fallback tính thô nếu lấy contract_size từ MT5 lỗi
        try:
            estimated = estimate_tp_sl_pnl(side, entry_price, tp_price, sl_price, lot, 1.0)
            print(f"(fallback contract_size=1) Không lấy được contract size: {exc}", flush=True)
            if "tp" in estimated:
                print(f"Ước tính lời TP: {estimated['tp']:.8f}", flush=True)
            if "sl" in estimated:
                print(f"Ước tính lỗ SL: {estimated['sl']:.8f}", flush=True)
        except Exception as exc2:
            print(f"Không ước tính được lời/lỗ: {exc2}", flush=True)


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
    """Kiểm tra hướng TP/SL. is_modification chỉ cho phép truyền None (không đổi field đó)."""
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


def build_trade_request(symbol, side, lot, tp_price=None, sl_price=None, comment="Python trader test"):
    tick = get_current_price(symbol)
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        raise RuntimeError(f"Không lấy được thông tin symbol {symbol}")

    price = tick.ask if side == "buy" else tick.bid
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
    if tp_price is None or sl_price is None:
        raise RuntimeError("Lệnh open bắt buộc phải có --tp-price và --sl-price")

    symbol = select_symbol(symbol, account)
    entry_price = get_entry_price(symbol, side)
    validate_tp_sl(side, entry_price, tp_price, sl_price)

    print(f"Sẽ mở lệnh {side.upper()} trên {symbol} với khối lượng {lot} lot")
    print(f"Giá vào dự kiến: {entry_price}")
    print(f"TP: {tp_price} | SL: {sl_price}")

    # Ước tính luôn in ở chế độ xem trước — --no-ask chỉ quyết định có gửi lệnh thật hay không.
    contract_size = resolve_contract_size(symbol)
    estimated = estimate_tp_sl_pnl(side, entry_price, tp_price, sl_price, lot, contract_size)
    print(f"Ước tính lời TP: {estimated.get('tp', 0):.8f}")
    print(f"Ước tính lỗ SL: {estimated.get('sl', 0):.8f}")

    if not confirm_action("Bạn có muốn thực hiện hành động này không?"):
        print("Đã hủy mở lệnh.")
        return None

    request = build_trade_request(symbol, side, lot, tp_price, sl_price, comment)
    result = mt5.order_send(request)

    if result is None:
        print(f"Đặt lệnh thất bại nặng! Không nhận được phản hồi từ terminal. Lỗi hệ thống: {mt5.last_error()}")
        return None

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Đặt lệnh thất bại! Mã lỗi: {result.retcode} ({result.comment})")
        save_trade_history(symbol, lot, result, request, "FAILED", f"retcode={result.retcode} | {result.comment}")
        return None

    print(f"Đặt lệnh thành công! Ticket ID: {result.order}")
    save_trade_history(symbol, lot, result, request, "SUCCESS")
    return result


def build_close_request(position):
    symbol = position.symbol
    tick = get_current_price(symbol)
    close_type = mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    close_price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
    filling_policy = get_filling_mode(symbol)

    return {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": position.volume,
        "type": close_type,
        "position": position.ticket,
        "price": close_price,
        "deviation": DEFAULT_DEVIATION,
        "magic": DEFAULT_MAGIC,
        "comment": "Close position",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling_policy,
    }


def close_position(position, confirm=True):
    print(f"Lệnh hiện tại: ticket={position.ticket} | symbol={position.symbol}")
    print(f"Loại: {'BUY' if position.type == mt5.ORDER_TYPE_BUY else 'SELL'}")
    print(f"Giá vào: {position.price_open}")
    print_position_pnl_lines(position, indent="")

    if confirm and not confirm_action(f"Bạn có muốn đóng lệnh {position.ticket} này không?"):
        print("Đã hủy đóng lệnh.")
        return None

    request = build_close_request(position)
    result = mt5.order_send(request)
    if result is None:
        print("Đóng lệnh thất bại! Không nhận được phản hồi.")
        return None

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Đóng lệnh thất bại! Mã lỗi: {result.retcode} ({result.comment})")
        save_trade_history(position.symbol, position.volume, result, request, "CLOSE_FAILED", f"ticket={position.ticket} | {result.comment}")
        return None

    print(f"Đóng lệnh thành công! Ticket ID: {result.order}")
    save_trade_history(position.symbol, position.volume, result, request, "CLOSE_SUCCESS", f"ticket={position.ticket}")
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
        sl = getattr(position, "sl", 0) or 0
        tp = getattr(position, "tp", 0) or 0
        print(f"- Ticket: {position.ticket} | Symbol: {position.symbol}")
        print(f"  Type: {'BUY' if position.type == mt5.ORDER_TYPE_BUY else 'SELL'}")
        print(f"  Volume: {position.volume}")
        print(f"  Giá mở cửa: {position.price_open}")
        print(f"  Stop Loss: {sl if sl > 0 else 'chưa đặt'}")
        print(f"  Take Profit: {tp if tp > 0 else 'chưa đặt'}")
        info = print_position_pnl_lines(position)
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
        print(f"- Ticket: {order.ticket} | Symbol: {order.symbol} | Type: {order.type} | Price: {order.price}")



def modify_all_positions_tp_sl(tp_price=None, sl_price=None):
    """Thay đổi take profit và stop loss của tất cả các lệnh đang mở"""
    positions = mt5.positions_get()
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
        print_tp_sl_warnings(side, position.price_open, new_tp, new_sl, indent="  ")
        print_open_tp_sl_estimate(position.symbol, side, position.price_open, new_tp, new_sl, position.volume)

    if not confirm_action("Bạn có muốn thay đổi TP/SL cho tất cả các lệnh này không?"):
        print("Đã hủy thay đổi TP/SL cho tất cả lệnh.")
        return []

    results = []
    for position in positions:
        side = "buy" if position.type == mt5.ORDER_TYPE_BUY else "sell"

        if tp_price is not None:
            validate_tp_sl(side, position.price_open, tp_price, None, is_modification=True)
        if sl_price is not None:
            validate_tp_sl(side, position.price_open, None, sl_price, is_modification=True)

        new_tp = tp_price if tp_price is not None else position.tp
        new_sl = sl_price if sl_price is not None else position.sl

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": position.symbol,
            "position": position.ticket,
            "tp": new_tp if new_tp > 0 else 0,
            "sl": new_sl if new_sl > 0 else 0,
            "magic": DEFAULT_MAGIC,
            "comment": "Modified TP/SL",
        }

        result = mt5.order_send(request)
        if result is None:
            print(f"Thay đổi TP/SL cho ticket {position.ticket} thất bại! Không nhận được phản hồi.")
            results.append(None)
            continue

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"Thay đổi TP/SL cho ticket {position.ticket} thất bại! Mã lỗi: {result.retcode} ({result.comment})")
            save_trade_history(position.symbol, position.volume, result, request, "MODIFY_FAILED", f"ticket={position.ticket} | {result.comment}")
        else:
            print(f"Thay đổi TP/SL cho ticket {position.ticket} thành công!")
            save_trade_history(position.symbol, position.volume, result, request, "MODIFY_SUCCESS", f"ticket={position.ticket}")

        results.append(result)

    return results


def run_action_on_account(account, args, lot):
    connect_mt5(account)
    if args.action == "open":
        open_trade(account, args.symbol, args.side, lot, args.tp_price, args.sl_price, args.comment)
    elif args.action == "close-all":
        close_all_positions()
    elif args.action == "modify-all":
        if args.tp_price is None and args.sl_price is None:
            raise RuntimeError("Cần cung cấp ít nhất --tp-price hoặc --sl-price để thay đổi")
        modify_all_positions_tp_sl(args.tp_price, args.sl_price)
    else:
        print_account_info()
        print_open_positions()
        print_pending_orders()


def execute_request(account_name, action, symbol="XAUUSD", side="buy", lot=0.01,
                     tp_price=None, sl_price=None, comment="Python trader test",
                     no_ask=False, copy_names=None):
    """Thực thi 1 hành động (status/open/close-all/modify-all) cho account_name,
    kèm copy sang các account trong copy_names nếu action cho phép.

    copy_names=None (không truyền gì) -> tự lấy theo cấu hình auto_copy_enabled/
    auto_copy_targets của account trong xml/accounts.xml. Truyền list cụ thể
    (kể cả []) sẽ override, không dùng cấu hình auto-copy.
    """
    global NO_ASK
    NO_ASK = no_ask

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

    try:
        run_action_on_account(primary_account, args, lot)

        if auto_copy_used and action in COPYABLE_ACTIONS:
            print(f"[AUTO-COPY] Tài khoản '{account_name}' được cấu hình tự động copy sang: {', '.join(copy_names)}")

        if copy_names and action not in COPYABLE_ACTIONS:
            print(f"Lưu ý: copy chỉ áp dụng cho action open/close-all/modify-all, bỏ qua sao chép cho action '{action}'.")
        elif copy_names:
            for copy_name in copy_names:
                print(f"\n--- [COPY] Đang thực thi sang tài khoản {copy_name} ---")
                try:
                    copy_account = get_account(copy_name)
                    mt5.shutdown()
                    time.sleep(0.5)
                    lot_for_copy = lot * get_account_multi(copy_account) if action == "open" else lot
                    if action == "open" and lot_for_copy != lot:
                        print(f"Lot gốc: {lot} → Lot copy ({copy_name}, MULTI={get_account_multi(copy_account)}): {lot_for_copy}")
                    run_action_on_account(copy_account, args, lot_for_copy)
                except Exception as copy_exc:
                    print(f"[COPY LỖI - {copy_name}] {copy_exc}")
    except Exception as exc:
        print(exc)
    finally:
        mt5.shutdown()


def main():
    parser = argparse.ArgumentParser(description="MT5 trader demo")
    parser.add_argument(
        "--account",
        choices=[acc["name"] for acc in ACCOUNTS],
        required=True,
        help="Bắt buộc: chọn tài khoản chính theo name khai báo trong accounts.xml (vd: prop_demo, prop_1, real, fake)",
    )
    parser.add_argument("--action", choices=["open", "close-all", "modify-all", "status"], required=True)
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--side", choices=["buy", "sell"], default="buy")
    parser.add_argument("--lot", type=float, default=0.01)
    parser.add_argument("--tp-price", type=float, default=None)
    parser.add_argument("--sl-price", type=float, default=None)
    parser.add_argument("--comment", default="Python trader test")
    parser.add_argument("--no-ask", action="store_true", help="Bắt buộc phải có để thực thi lệnh thật (open/close-all/modify-all). Nếu không truyền, chương trình chỉ in thông báo xem trước và không gửi lệnh nào, kể cả copy.")
    parser.add_argument(
        "--copy", default=None,
        help="Danh sách account name cần copy lệnh sang, phân tách bằng dấu phẩy, ví dụ: prop_demo,prop_1. "
             "Không truyền --copy sẽ tự dùng cấu hình auto_copy_enabled/auto_copy_targets của account trong accounts.xml (nếu có). "
             'Truyền --copy "" để tắt hẳn copy (bỏ qua cả auto-copy).',
    )

    args = parser.parse_args()

    if args.action == "open" and (args.tp_price is None or args.sl_price is None):
        parser.error("action=open bắt buộc phải có cả --tp-price và --sl-price")

    copy_names = None
    if args.copy is not None:
        copy_names = [t.strip() for t in args.copy.split(",") if t.strip()]

    execute_request(
        args.account, args.action, args.symbol, args.side, args.lot,
        args.tp_price, args.sl_price, args.comment, args.no_ask, copy_names,
    )


if __name__ == "__main__":
    main()
