"""
Backtest chiến lược: Only Buy at 21:30 (theo giờ Việt Nam UTC+7)
- Đọc dữ liệu từ file data/NAS100M/1600_15m.txt
- Xét theo từng ngày, nếu nến 21:30 là nến TĂNG (close > open) thì mua
- Nếu giá quay đầu giảm 100 điểm so với giá mua → đóng lệnh stoploss, đợi hôm sau
- Giữ lệnh tới giá ĐÓNG CỬA nến 23:30 → đóng lệnh take profit / exit
- Vốn ban đầu: 10,000 USD. Giá trị: 1 điểm = 1 USD (mỗi thay đổi 1 điểm = +/-1$)
- Thống kê: tỷ lệ thắng, tổng tiền cuối kỳ
"""

import re
from datetime import datetime, time


DATA_FILE = "data/NAS100M/1600_15m.txt"

# Tham số
INITIAL_CAPITAL = 10_000
STOP_LOSS_POINTS = 100
DOLLAR_PER_POINT = 1  # 1 điểm giá = 1$

# Thời điểm cần xét (giờ VN = UTC+7, nhưng data đang dùng giờ gì?)
# Từ dữ liệu: 2026-04-01 21:30:00 → nến 21h30 (giờ VN)
ENTRY_HOUR = 21
ENTRY_MINUTE = 30
EXIT_HOUR = 23
EXIT_MINUTE = 30


def parse_price(price_str):
    """Chuyển chuỗi giá '24,066.50' thành float 24066.50"""
    return float(price_str.replace(',', '').strip())


def parse_data(filepath):
    """
    Đọc file và trả về danh sách candle:
    [{"time": datetime, "open": float, "high": float, "low": float, "close": float}, ...]
    """
    candles = []
    # Regex khớp dòng dữ liệu: index  datetime  symbol  open  high  low  close  ...
    pattern = re.compile(
        r'^\s*\d+\s+'
        r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+'
        r'\S+\s+'          # symbol
        r'([\d,]+\.\d+)\s+'  # open
        r'([\d,]+\.\d+)\s+'  # high
        r'([\d,]+\.\d+)\s+'  # low
        r'([\d,]+\.\d+)'     # close
    )
    with open(filepath, encoding='utf-8') as f:
        for line in f:
            m = pattern.match(line)
            if m:
                dt = datetime.strptime(m.group(1).strip(), '%Y-%m-%d %H:%M:%S')
                candles.append({
                    'time': dt,
                    'open': parse_price(m.group(2)),
                    'high': parse_price(m.group(3)),
                    'low':  parse_price(m.group(4)),
                    'close': parse_price(m.group(5)),
                })
    return candles


def group_by_date(candles):
    """Nhóm candles theo ngày (date)"""
    days = {}
    for c in candles:
        d = c['time'].date()
        days.setdefault(d, []).append(c)
    return days


def find_candle(candles_of_day, hour, minute):
    """Tìm nến tại giờ:phút trong ngày"""
    target = time(hour, minute)
    for c in candles_of_day:
        if c['time'].time() == target:
            return c
    return None


def run_backtest(candles):
    capital = INITIAL_CAPITAL
    trades = []

    days = group_by_date(candles)
    sorted_dates = sorted(days.keys())

    for date in sorted_dates:
        day_candles = sorted(days[date], key=lambda x: x['time'])

        # Tìm nến 21:30
        entry_candle = find_candle(day_candles, ENTRY_HOUR, ENTRY_MINUTE)
        if entry_candle is None:
            continue

        # Điều kiện vào lệnh: nến TĂNG (close > open)
        if entry_candle['close'] <= entry_candle['open']:
            continue

        buy_price = entry_candle['close']  # Mua ở giá close nến 21:30

        # Tìm nến 23:30 để lấy giá exit
        exit_candle = find_candle(day_candles, EXIT_HOUR, EXIT_MINUTE)

        # Kiểm tra stoploss giữa 21:30 và 23:30
        # Chỉ xét các nến từ sau 21:30 đến trước/tại 23:30
        candles_in_range = [
            c for c in day_candles
            if c['time'].time() > time(ENTRY_HOUR, ENTRY_MINUTE)
            and c['time'].time() <= time(EXIT_HOUR, EXIT_MINUTE)
        ]

        stop_price = buy_price - STOP_LOSS_POINTS
        stopped_out = False
        stop_exit_price = None

        for c in candles_in_range:
            # Nếu low của bất kỳ nến nào chạm stoploss
            if c['low'] <= stop_price:
                stopped_out = True
                stop_exit_price = stop_price  # Giả định đóng đúng giá SL
                break

        if stopped_out:
            pnl = stop_exit_price - buy_price  # = -100
            result = 'LOSS (SL)'
        else:
            if exit_candle is None:
                # Không tìm thấy nến 23:30, bỏ qua ngày này
                continue
            exit_price = exit_candle['close']
            pnl = exit_price - buy_price
            result = 'WIN' if pnl > 0 else ('LOSS' if pnl < 0 else 'BREAK EVEN')

        capital += pnl * DOLLAR_PER_POINT
        trades.append({
            'date': date,
            'buy_price': buy_price,
            'exit_price': stop_exit_price if stopped_out else exit_candle['close'],
            'pnl_points': pnl,
            'pnl_usd': pnl * DOLLAR_PER_POINT,
            'capital': capital,
            'result': result,
        })

    return trades, capital


def print_report(trades, final_capital):
    print("\n" + "=" * 70)
    print(f"{'BACKTEST: ONLY BUY AT 21:30 (NẾN TĂNG)':^70}")
    print("=" * 70)
    print(f"{'Ngày':<12} {'Mua':>10} {'Thoát':>10} {'PnL (đ)':>10} {'PnL ($)':>10} {'Vốn ($)':>12} {'Kết quả'}")
    print("-" * 70)

    wins = 0
    losses = 0
    total_win_points = 0
    total_loss_points = 0

    for t in trades:
        print(
            f"{str(t['date']):<12} "
            f"{t['buy_price']:>10.2f} "
            f"{t['exit_price']:>10.2f} "
            f"{t['pnl_points']:>+10.2f} "
            f"{t['pnl_usd']:>+10.2f} "
            f"{t['capital']:>12.2f} "
            f"{t['result']}"
        )
        if t['pnl_usd'] > 0:
            wins += 1
            total_win_points += t['pnl_points']
        elif t['pnl_usd'] < 0:
            losses += 1
            total_loss_points += t['pnl_points']

    total_trades = len(trades)
    win_rate = wins / total_trades * 100 if total_trades > 0 else 0

    print("=" * 70)
    print(f"\n📊 THỐNG KÊ TỔNG QUAN")
    print(f"  Tổng số lệnh     : {total_trades}")
    print(f"  Thắng            : {wins}")
    print(f"  Thua             : {losses}")
    print(f"  Tỷ lệ thắng      : {win_rate:.1f}%")
    print(f"  Vốn ban đầu      : ${INITIAL_CAPITAL:,.2f}")
    print(f"  Vốn cuối kỳ      : ${final_capital:,.2f}")
    profit = final_capital - INITIAL_CAPITAL
    print(f"  Lợi nhuận        : ${profit:+,.2f} ({profit/INITIAL_CAPITAL*100:+.1f}%)")
    print(f"  Avg win (điểm)   : {total_win_points/wins:.2f}" if wins else "  Avg win (điểm)   : N/A")
    print(f"  Avg loss (điểm)  : {total_loss_points/losses:.2f}" if losses else "  Avg loss (điểm)  : N/A")
    print()


def main():
    import os
    # Hỗ trợ chạy từ thư mục gốc hoặc thư mục backtest
    filepath = DATA_FILE
    if not os.path.exists(filepath):
        filepath = os.path.join(os.path.dirname(__file__), '..', DATA_FILE)

    print(f"📂 Đọc dữ liệu từ: {filepath}")
    candles = parse_data(filepath)
    print(f"✅ Đọc được {len(candles)} nến")

    trades, final_capital = run_backtest(candles)
    print_report(trades, final_capital)


if __name__ == '__main__':
    main()