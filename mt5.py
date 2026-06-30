# HƯỚNG DẪN SỬ DỤNG
# 1. Cài đặt thư viện cần thiết bằng câu lệnh: python -m pip install MetaTrader5 pandas
# 2. Điền đúng số tài khoản, mật khẩu và server MT5 của bạn vào các biến ACCOUNT_REAL, ACCOUNT_FAKE, PASSWORD, SERVER_REAL, SERVER_FAKE.
#    Mặc định hệ thống sử dụng tài khoản FAKE. Sử dụng tham số --real để chạy trên tài khoản REAL, hoặc --fake cho tài khoản FAKE.
# 3. Mở lệnh thử nghiệm BTC bằng câu lệnh: python mt5.py --action open --symbol BTCUSDm --side buy --lot 0.01 --tp-price 60000 --sl-price 58000 --fake
#    Trong đó TP/SL là mức giá cụ thể, không phải số điểm. Ví dụ BUY có TP cao hơn giá mở, SL thấp hơn giá mở; SELL có TP thấp hơn giá mở, SL cao hơn giá mở.
# 4. Xem giá hiện tại của symbol bằng câu lệnh: python mt5.py --action price --symbol BTCUSDm --fake
# 5. Đóng lệnh bằng câu lệnh: python mt5.py --action close --ticket 123456 --fake
# 6. Thay đổi TP/SL của lệnh cũ bằng câu lệnh: python mt5.py --action modify --ticket 123456 --tp-price 60000 --sl-price 58000 --fake
#    Có thể chỉ thay đổi TP: python mt5.py --action modify --ticket 123456 --tp-price 60000 --fake
#    Hoặc chỉ thay đổi SL: python mt5.py --action modify --ticket 123456 --sl-price 58000 --fake
# 7. Thay đổi TP/SL của tất cả các lệnh đang mở: python mt5.py --action modify-all --tp-price 60000 --sl-price 58000 --fake
#    Cũng có thể chỉ thay đổi TP hoặc SL cho tất cả lệnh.
# 8. Đóng toàn bộ lệnh đang mở bằng câu lệnh: python mt5.py --action close-all --fake
# 9. Xem trạng thái tài khoản và lệnh đang mở bằng câu lệnh: python mt5.py --action status --fake
# 10. Mỗi lần thực thi lệnh sẽ tự động ghi lịch sử vào file history_mt5.txt ở đầu file, theo thứ tự thời gian giảm dần.

# REAL
# 201967146
# Exness-MT5Real18

# FAKE
# 463579382
# Exness-MT5Trial17

import argparse
from datetime import datetime
from pathlib import Path

import MetaTrader5 as mt5

HISTORY_FILE = Path(__file__).with_name("history_mt5.txt")

def detect_account_type(server_name: str) -> str:
    server_lower = server_name.lower()
    if "real" in server_lower:
        return "REAL"
    if "trial" in server_lower or "demo" in server_lower:
        return "FAKE"
    return "UNKNOWN"

ACCOUNT_REAL = 201967146
ACCOUNT_FAKE = 463579382
PASSWORD = "753159@Lmnnml."
SERVER_REAL = "Exness-MT5Real18"
SERVER_FAKE = "Exness-MT5Trial17"
ACCOUNT = ACCOUNT_FAKE
SERVER = SERVER_FAKE
ACCOUNT_TYPE = "FAKE"
NO_ASK = False
DEFAULT_MAGIC = 234567
DEFAULT_DEVIATION = 20
DEFAULT_SYMBOLS = ["BTCUSD", "BTCUSDm", "XAUUSDm", "XAUUSD"]


def save_trade_history(symbol, lot, result, request, status, detail=""):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ticket = getattr(result, "order", None)
    retcode = getattr(result, "retcode", None)

    entry = (
        f"{timestamp} | symbol={symbol} | lot={lot} | status={status} | "
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
    if NO_ASK:
        return True
    answer = input(f"{message} (y/n): ").strip().lower()
    return answer in {"y", "yes"}


def connect_mt5():
    if not mt5.initialize(login=ACCOUNT, password=PASSWORD, server=SERVER, timeout=60000):
        raise RuntimeError(f"Không thể kết nối vào MT5, lỗi: {mt5.last_error()}")

    if mt5.terminal_info() is None:
        mt5.shutdown()
        raise RuntimeError("MetaTrader 5 chưa mở hoặc không thể lấy thông tin.")

    login_success = mt5.login(login=ACCOUNT, password=PASSWORD, server=SERVER)
    if not login_success:
        mt5.shutdown()
        raise RuntimeError(f"Đăng nhập thất bại, mã lỗi: {mt5.last_error()}")

    print(f"Đang sử dụng tài khoản {ACCOUNT_TYPE}: {ACCOUNT} | server: {SERVER}")
    print("Đăng nhập MT5 thành công!")


def select_symbol(symbol):
    candidates = [symbol] if symbol else DEFAULT_SYMBOLS
    for candidate in candidates:
        if mt5.symbol_select(candidate, True):
            return candidate
    raise RuntimeError(f"Không tìm thấy symbol nào phù hợp: {candidates}")


def get_current_price(symbol):
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise RuntimeError(f"Không lấy được tick cho symbol {symbol}")
    return tick


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


def validate_tp_sl(side, entry_price, tp_price, sl_price):
    if tp_price is not None and tp_price <= 0:
        raise RuntimeError("TP phải lớn hơn 0")
    if sl_price is not None and sl_price <= 0:
        raise RuntimeError("SL phải lớn hơn 0")

    if side == "buy":
        if tp_price is not None and tp_price <= entry_price:
            raise RuntimeError(f"TP mua không hợp lệ: {tp_price} phải lớn hơn giá mở {entry_price}")
        if sl_price is not None and sl_price >= entry_price:
            raise RuntimeError(f"SL mua không hợp lệ: {sl_price} phải nhỏ hơn giá mở {entry_price}")
    else:
        if tp_price is not None and tp_price >= entry_price:
            raise RuntimeError(f"TP bán không hợp lệ: {tp_price} phải nhỏ hơn giá mở {entry_price}")
        if sl_price is not None and sl_price <= entry_price:
            raise RuntimeError(f"SL bán không hợp lệ: {sl_price} phải lớn hơn giá mở {entry_price}")


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


def calculate_position_pnl(position):
    symbol_info = mt5.symbol_info(position.symbol)
    if symbol_info is None:
        raise RuntimeError(f"Không lấy được thông tin symbol {position.symbol}")

    tick = get_current_price(position.symbol)
    contract_size = getattr(symbol_info, "trade_contract_size", 1) or 1
    current_price = tick.bid if position.type == mt5.ORDER_TYPE_BUY else tick.ask

    if position.type == mt5.ORDER_TYPE_BUY:
        pnl_formula = (current_price - position.price_open) * position.volume * contract_size
    else:
        pnl_formula = (position.price_open - current_price) * position.volume * contract_size

    return pnl_formula, current_price, contract_size


def estimate_tp_sl_pnl(side, entry_price, tp_price, sl_price, volume, contract_size):
    estimated = {}
    if tp_price is not None:
        if side == "buy":
            estimated["tp"] = (tp_price - entry_price) * volume * contract_size
        else:
            estimated["tp"] = (entry_price - tp_price) * volume * contract_size
    if sl_price is not None:
        if side == "buy":
            estimated["sl"] = (sl_price - entry_price) * volume * contract_size
        else:
            estimated["sl"] = (entry_price - sl_price) * volume * contract_size
    return estimated


def open_trade(symbol, side, lot, tp_price=None, sl_price=None, comment="Python trader test"):
    symbol = select_symbol(symbol)
    print(f"Sẽ mở lệnh {side.upper()} trên {symbol} với khối lượng {lot} lot")
    print(f"TP: {tp_price if tp_price is not None else 'không đặt'} | SL: {sl_price if sl_price is not None else 'không đặt'}")

    symbol_info = mt5.symbol_info(symbol)
    contract_size = getattr(symbol_info, "trade_contract_size", 1) or 1
    entry_price = get_current_price(symbol).ask if side == "buy" else get_current_price(symbol).bid
    estimated = estimate_tp_sl_pnl(side, entry_price, tp_price, sl_price, lot, contract_size)
    if estimated:
        if "tp" in estimated:
            print(f"Ước tính lời TP: {estimated['tp']:.8f}")
        if "sl" in estimated:
            print(f"Ước tính lỗ SL: {estimated['sl']:.8f}")

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
    pnl_value, current_price, _ = calculate_position_pnl(position)
    print(f"Lệnh hiện tại: ticket={position.ticket} | symbol={position.symbol}")
    print(f"Loại: {'BUY' if position.type == mt5.ORDER_TYPE_BUY else 'SELL'}")
    print(f"Giá vào: {position.price_open} | Giá hiện tại: {current_price}")
    print(f"Lãi/lỗ hiện tại: {pnl_value:.6f} ({position.profit} theo MT5)")

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


def close_trade(ticket):
    positions = mt5.positions_get(ticket=ticket)
    if not positions:
        raise RuntimeError(f"Không tìm thấy vị thế có ticket {ticket}")
    position = positions[0]
    return close_position(position, confirm=True)


def close_all_positions():
    positions = mt5.positions_get()
    if not positions:
        print("Không có lệnh nào đang mở.")
        return []

    print(f"Tìm thấy {len(positions)} lệnh đang mở. Đang chuẩn bị đóng toàn bộ...")
    for position in positions:
        print(f"- Ticket: {position.ticket} | Symbol: {position.symbol} | Type: {'BUY' if position.type == mt5.ORDER_TYPE_BUY else 'SELL'}")

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

    for position in positions:
        pnl_formula, current_price, contract_size = calculate_position_pnl(position)
        estimated = estimate_tp_sl_pnl(
            "buy" if position.type == mt5.ORDER_TYPE_BUY else "sell",
            position.price_open,
            getattr(position, "tp", None),
            getattr(position, "sl", None),
            position.volume,
            contract_size,
        )

        print(f"- Ticket: {position.ticket} | Symbol: {position.symbol}")
        print(f"  Type: {'BUY' if position.type == mt5.ORDER_TYPE_BUY else 'SELL'}")
        print(f"  Volume: {position.volume}")
        print(f"  Giá mở cửa: {position.price_open}")
        print(f"  Giá hiện tại: {current_price}")
        print(f"  Stop Loss: {getattr(position, 'sl', 'chưa đặt')}")
        print(f"  Take Profit: {getattr(position, 'tp', 'chưa đặt')}")
        if pnl_formula > 0:
            pnl_status = f"ĐANG LÃI {pnl_formula:.6f}"
        elif pnl_formula < 0:
            pnl_status = f"ĐANG LỖ {abs(pnl_formula):.6f}"
        else:
            pnl_status = "HÒA"
        print(f"  Trạng thái: {pnl_status}")
        print(f"  P/L hiện tại: {position.profit} (công thức: {pnl_formula:.6f})")
        if estimated:
            if "tp" in estimated:
                print(f"  Ước tính lời TP: {estimated['tp']:.8f}")
            if "sl" in estimated:
                print(f"  Ước tính lỗ SL: {estimated['sl']:.8f}")


def print_pending_orders():
    orders = mt5.orders_get()
    print("Các lệnh chờ:")
    if not orders:
        print("- Không có lệnh chờ nào")
        return

    for order in orders:
        print(f"- Ticket: {order.ticket} | Symbol: {order.symbol} | Type: {order.type} | Price: {order.price}")


def modify_position_tp_sl(ticket, tp_price=None, sl_price=None):
    """Thay đổi take profit và stop loss của lệnh đang mở"""
    positions = mt5.positions_get(ticket=ticket)
    if not positions:
        raise RuntimeError(f"Không tìm thấy vị thế có ticket {ticket}")
    position = positions[0]
    
    side = "buy" if position.type == mt5.ORDER_TYPE_BUY else "sell"
    print(f"Lệnh hiện tại: ticket={ticket} | symbol={position.symbol} | type={side.upper()}")
    print(f"Giá vào: {position.price_open}")
    print(f"TP cũ: {position.tp if position.tp > 0 else 'chưa đặt'} → TP mới: {tp_price if tp_price is not None else position.tp if position.tp > 0 else 'chưa đặt'}")
    print(f"SL cũ: {position.sl if position.sl > 0 else 'chưa đặt'} → SL mới: {sl_price if sl_price is not None else position.sl if position.sl > 0 else 'chưa đặt'}")
    
    # Validate TP/SL
    if tp_price is not None:
        validate_tp_sl(side, position.price_open, tp_price, None)
    if sl_price is not None:
        validate_tp_sl(side, position.price_open, None, sl_price)
    
    if not confirm_action("Bạn có muốn thực hiện thay đổi này không?"):
        print("Đã hủy thay đổi TP/SL.")
        return None
    
    # Sử dụng giá trị cũ nếu không có giá trị mới
    new_tp = tp_price if tp_price is not None else position.tp
    new_sl = sl_price if sl_price is not None else position.sl
    
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": position.symbol,
        "position": ticket,
        "tp": new_tp if new_tp > 0 else 0,
        "sl": new_sl if new_sl > 0 else 0,
        "magic": DEFAULT_MAGIC,
        "comment": "Modified TP/SL",
    }
    
    result = mt5.order_send(request)
    if result is None:
        print("Thay đổi TP/SL thất bại! Không nhận được phản hồi.")
        return None
    
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Thay đổi TP/SL thất bại! Mã lỗi: {result.retcode} ({result.comment})")
        save_trade_history(position.symbol, position.volume, result, request, "MODIFY_FAILED", f"ticket={ticket} | {result.comment}")
        return None
    
    print(f"Thay đổi TP/SL thành công!")
    save_trade_history(position.symbol, position.volume, result, request, "MODIFY_SUCCESS", f"ticket={ticket}")
    return result


def modify_all_positions_tp_sl(tp_price=None, sl_price=None):
    """Thay đổi take profit và stop loss của tất cả các lệnh đang mở"""
    positions = mt5.positions_get()
    if not positions:
        print("Không có lệnh nào đang mở để thay đổi.")
        return []
    
    print(f"Tìm thấy {len(positions)} lệnh đang mở. Đang chuẩn bị thay đổi TP/SL cho tất cả...")
    for position in positions:
        side = "buy" if position.type == mt5.ORDER_TYPE_BUY else "sell"
        print(f"- Ticket: {position.ticket} | Symbol: {position.symbol} | Type: {side.upper()}")
        print(f"  Giá vào: {position.price_open} | TP cũ: {position.tp if position.tp > 0 else 'chưa đặt'} | SL cũ: {position.sl if position.sl > 0 else 'chưa đặt'}")
        if tp_price is not None:
            print(f"  → TP mới: {tp_price}")
        if sl_price is not None:
            print(f"  → SL mới: {sl_price}")
    
    if not confirm_action("Bạn có muốn thay đổi TP/SL cho tất cả các lệnh này không?"):
        print("Đã hủy thay đổi TP/SL cho tất cả lệnh.")
        return []
    
    results = []
    for position in positions:
        side = "buy" if position.type == mt5.ORDER_TYPE_BUY else "sell"
        
        # Validate TP/SL
        if tp_price is not None:
            validate_tp_sl(side, position.price_open, tp_price, None)
        if sl_price is not None:
            validate_tp_sl(side, position.price_open, None, sl_price)
        
        # Sử dụng giá trị cũ nếu không có giá trị mới
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


def print_current_price(symbol):
    symbol = select_symbol(symbol)
    tick = get_current_price(symbol)
    print(f"Giá hiện tại của {symbol}:")
    print(f"- Bid: {tick.bid}")
    print(f"- Ask: {tick.ask}")
    print(f"- Last: {tick.last}")


def main():
    global ACCOUNT, SERVER, ACCOUNT_TYPE, NO_ASK

    parser = argparse.ArgumentParser(description="MT5 trader demo")
    parser.add_argument("--action", choices=["open", "close", "close-all", "modify", "modify-all", "status", "price"], default="status")
    parser.add_argument("--symbol", default="BTCUSD")
    parser.add_argument("--side", choices=["buy", "sell"], default="buy")
    parser.add_argument("--lot", type=float, default=0.01)
    parser.add_argument("--tp-price", type=float, default=None)
    parser.add_argument("--sl-price", type=float, default=None)
    parser.add_argument("--ticket", type=int, default=None)
    parser.add_argument("--comment", default="Python trader test")
    parser.add_argument("--no-ask", action="store_true", help="Bỏ qua xác nhận y/n")
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--fake", action="store_true", help="Sử dụng tài khoản FAKE")
    group.add_argument("--real", action="store_true", help="Sử dụng tài khoản REAL")
    
    args = parser.parse_args()

    NO_ASK = args.no_ask

    if args.real:
        ACCOUNT = ACCOUNT_REAL
        SERVER = SERVER_REAL
        ACCOUNT_TYPE = "REAL"
    else:
        ACCOUNT = ACCOUNT_FAKE
        SERVER = SERVER_FAKE
        ACCOUNT_TYPE = "FAKE"

    try:
        connect_mt5()
        if args.action == "open":
            open_trade(args.symbol, args.side, args.lot, args.tp_price, args.sl_price, args.comment)
        elif args.action == "close":
            if args.ticket is None:
                raise RuntimeError("Cần cung cấp --ticket để đóng lệnh")
            close_trade(args.ticket)
        elif args.action == "modify":
            if args.ticket is None:
                raise RuntimeError("Cần cung cấp --ticket để thay đổi TP/SL")
            if args.tp_price is None and args.sl_price is None:
                raise RuntimeError("Cần cung cấp ít nhất --tp-price hoặc --sl-price để thay đổi")
            modify_position_tp_sl(args.ticket, args.tp_price, args.sl_price)
        elif args.action == "modify-all":
            if args.tp_price is None and args.sl_price is None:
                raise RuntimeError("Cần cung cấp ít nhất --tp-price hoặc --sl-price để thay đổi")
            modify_all_positions_tp_sl(args.tp_price, args.sl_price)
        elif args.action == "price":
            print_current_price(args.symbol)
        elif args.action == "close-all":
            close_all_positions()
        else:
            print_account_info()
            print_open_positions()
            print_pending_orders()
    except Exception as exc:
        print(exc)
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()