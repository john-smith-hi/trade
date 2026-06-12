"""
Backtest chiến lược: Buy Filter at 21:30 (theo giờ Việt Nam UTC+7)
- Đọc dữ liệu từ file data/NAS100M/1600_15m.txt
- Quy ước U là giá nến tăng, D là giá nến giảm
  Ví dụ UDUU = nến 21:00(U) 21:15(D) 21:30(U) 21:45(U)
- Test chiến thuật nếu UDU, UUDU, DDU thì mua ; UDD,UUUD, UUDD thì bán
- Nếu giá quay đầu 100 điểm so với giá vào lệnh → đóng lệnh stoploss, đợi hôm sau
- Giữ lệnh tới giá MỞ CỬA nến 23:30 → đóng lệnh take profit / exit
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

# Các nến để xác định pattern (21:00, 21:15, 21:30, 21:45)
PATTERN_CANDLES = [(21, 0), (21, 15), (21, 30), (21, 45)]

# Vào lệnh tại close của nến 21:45
ENTRY_HOUR, ENTRY_MINUTE = 21, 45

# Thoát lệnh tại giá mở cửa (open) nến 23:30
EXIT_HOUR, EXIT_MINUTE = 23, 30

# Pattern BUY và SELL
BUY_PATTERNS  = ['UDU', 'UUDU', 'DDU']
SELL_PATTERNS = ['UDD', 'UUUD', 'UUDD']


# ── Helpers ──────────────────────────────────────────────────────────────────

def parse_price(s):
    return float(s.replace(',', '').strip())


def parse_data(filepath):
    candles = []
    pat = re.compile(
        r'^\s*\d+\s+'
        r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+'
        r'\S+\s+'
        r'([\d,]+\.\d+)\s+'  # open
        r'([\d,]+\.\d+)\s+'  # high
        r'([\d,]+\.\d+)\s+'  # low
        r'([\d,]+\.\d+)'     # close
    )
    with open(filepath, encoding='utf-8') as f:
        for line in f:
            m = pat.match(line)
            if m:
                dt = datetime.strptime(m.group(1).strip(), '%Y-%m-%d %H:%M:%S')
                candles.append({
                    'time':  dt,
                    'open':  parse_price(m.group(2)),
                    'high':  parse_price(m.group(3)),
                    'low':   parse_price(m.group(4)),
                    'close': parse_price(m.group(5)),
                })
    return candles


def group_by_date(candles):
    days = {}
    for c in candles:
        days.setdefault(c['time'].date(), []).append(c)
    return days


def find_candle(day_candles, hour, minute):
    t = time(hour, minute)
    for c in day_candles:
        if c['time'].time() == t:
            return c
    return None


def candle_dir(c):
    return 'U' if c['close'] > c['open'] else 'D'


def matches_pattern(day_candles, target_pattern):
    """
    Kiểm tra xem day_candles có khớp với target_pattern hay không.
    - Pattern độ dài 3: 21:00, 21:15, 21:30
    - Pattern độ dài 4: 21:00, 21:15, 21:30, 21:45
    """
    length = len(target_pattern)
    times_needed = PATTERN_CANDLES[:length]
    
    dirs = []
    for h, m in times_needed:
        c = find_candle(day_candles, h, m)
        if c is None: return False
        dirs.append(candle_dir(c))
    
    return "".join(dirs) == target_pattern


# ── Backtest core ─────────────────────────────────────────────────────────────

def run_backtest_for_pattern(days, sorted_dates, pattern, direction):
    """
    direction: 'BUY' hoặc 'SELL'
    Entry: Close của nến cuối cùng trong pattern.
    Exit: Open của 23:30.
    """
    capital = INITIAL_CAPITAL
    trades = []
    
    # Xác định nến entry dựa trên độ dài pattern
    # 3 nến -> entry 21:30, 4 nến -> entry 21:45
    pat_len = len(pattern)
    entry_h, entry_m = PATTERN_CANDLES[pat_len - 1]

    for date in sorted_dates:
        day_candles = sorted(days[date], key=lambda x: x['time'])

        if not matches_pattern(day_candles, pattern):
            continue

        entry_candle = find_candle(day_candles, entry_h, entry_m)
        if entry_candle is None:
            continue

        entry_price = entry_candle['close']
        exit_candle  = find_candle(day_candles, EXIT_HOUR, EXIT_MINUTE)

        # Nến cần scan stoploss: ngay sau entry đến hết 23:30
        scan_candles = [
            c for c in day_candles
            if c['time'].time() > time(entry_h, entry_m)
            and c['time'].time() <= time(EXIT_HOUR, EXIT_MINUTE)
        ]

        stopped_out = False
        sl_price = None

        if direction == 'BUY':
            stop_level = entry_price - STOP_LOSS_POINTS
            for c in scan_candles:
                if c['low'] <= stop_level:
                    stopped_out = True
                    sl_price = stop_level
                    break
        else:  # SELL
            stop_level = entry_price + STOP_LOSS_POINTS
            for c in scan_candles:
                if c['high'] >= stop_level:
                    stopped_out = True
                    sl_price = stop_level
                    break

        if stopped_out:
            pnl = -STOP_LOSS_POINTS
            result = 'LOSS (SL)'
        else:
            if exit_candle is None:
                continue
            ep = exit_candle['open']
            if direction == 'BUY':
                pnl = ep - entry_price
            else:
                pnl = entry_price - ep
            result = 'WIN' if pnl > 0 else ('LOSS' if pnl < 0 else 'BREAK EVEN')

        capital += pnl * DOLLAR_PER_POINT
        trades.append({
            'date':        date,
            'direction':   direction,
            'entry_time':  f"{entry_h:02d}:{entry_m:02d}",
            'entry_price': entry_price,
            'exit_price':  sl_price if stopped_out else exit_candle['open'],
            'pnl_points':  pnl,
            'pnl_usd':     pnl * DOLLAR_PER_POINT,
            'capital':     capital,
            'result':      result,
        })

    return trades, capital


# ── Reporting ─────────────────────────────────────────────────────────────────

def print_pattern_report(pattern, direction, trades, final_capital):
    W = 76
    dir_label = '📈 MUA (BUY)' if direction == 'BUY' else '📉 BÁN (SELL)'
    entry_example = "(21:00 21:15 21:30)" if len(pattern) == 3 else "(21:00 21:15 21:30 21:45)"
    print("\n" + "=" * W)
    print(f"  {dir_label}  |  Pattern: {pattern}  {entry_example}".center(W))
    print("=" * W)

    if not trades:
        print("  Không có lệnh nào khớp pattern này trong dữ liệu.")
        print("=" * W)
        return

    print(f"{'Ngày':<12} {'Giờ In':<8} {'Vào lệnh':>10} {'Thoát':>10} {'PnL (đ)':>10} {'PnL ($)':>9} {'Vốn ($)':>12}")
    print("-" * W)

    wins = losses = 0
    win_pts = lose_pts = 0.0

    for t in trades:
        print(
            f"{str(t['date']):<12} "
            f"{t['entry_time']:<8} "
            f"{t['entry_price']:>10.2f} "
            f"{t['exit_price']:>10.2f} "
            f"{t['pnl_points']:>+10.2f} "
            f"{t['pnl_usd']:>+9.2f} "
            f"{t['capital']:>12.2f}  "
            f"{t['result']}"
        )
        if t['pnl_usd'] > 0:
            wins += 1;  win_pts  += t['pnl_points']
        else:
            losses += 1; lose_pts += t['pnl_points']

    total    = len(trades)
    win_rate = wins / total * 100 if total else 0
    print("=" * W)
    print(f"  Lệnh: {total}  |  Thắng: {wins}  |  Thua: {losses}  |  Win rate: {win_rate:.1f}%")
    profit = final_capital - INITIAL_CAPITAL
    print(f"  Vốn cuối: ${final_capital:,.2f}  |  Lợi nhuận: ${profit:+,.2f} ({profit/INITIAL_CAPITAL*100:+.1f}%)")
    parts = []
    if wins:   parts.append(f"Avg win: +{win_pts/wins:.2f} đ")
    if losses: parts.append(f"Avg loss: {lose_pts/losses:.2f} đ")
    if parts:  print("  " + "  |  ".join(parts))


def print_summary(results):
    W = 80
    print("\n" + "=" * W)
    print("  TỔNG HỢP SO SÁNH TẤT CẢ PATTERN".center(W))
    print("=" * W)
    print(f"  {'Hướng':<6} {'Pattern':<8} {'Lệnh':>5} {'Thắng':>6} {'Thua':>5} {'Win%':>6}  {'Lợi nhuận ($)':>14}  {'Vốn cuối ($)':>13}")
    print("-" * W)
    for direction, pattern, trades, final_cap in results:
        if not trades:
            lbl = '📈' if direction == 'BUY' else '📉'
            print(f"  {lbl} {pattern:<8}  {'(không có lệnh)'}")
            continue
        wins = sum(1 for t in trades if t['pnl_usd'] > 0)
        losses = len(trades) - wins
        wr = wins / len(trades) * 100
        profit = final_cap - INITIAL_CAPITAL
        lbl = '📈' if direction == 'BUY' else '📉'
        print(
            f"  {lbl} {pattern:<8} {len(trades):>5} {wins:>6} {losses:>5} {wr:>5.1f}%"
            f"  {profit:>+14.2f}  {final_cap:>13.2f}"
        )
    print("=" * W)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import os
    filepath = DATA_FILE
    if not os.path.exists(filepath):
        filepath = os.path.join(os.path.dirname(__file__), '..', DATA_FILE)

    print(f"📂 Đọc dữ liệu từ: {filepath}")
    candles = parse_data(filepath)
    print(f"✅ Đọc được {len(candles)} nến")

    days         = group_by_date(candles)
    sorted_dates = sorted(days.keys())

    # Chạy backtest
    results = []
    print("\n──── BUY PATTERNS ────")
    for pat in BUY_PATTERNS:
        trades, cap = run_backtest_for_pattern(days, sorted_dates, pat, 'BUY')
        results.append(('BUY', pat, trades, cap))
        print_pattern_report(pat, 'BUY', trades, cap)

    print("\n──── SELL PATTERNS ────")
    for pat in SELL_PATTERNS:
        trades, cap = run_backtest_for_pattern(days, sorted_dates, pat, 'SELL')
        results.append(('SELL', pat, trades, cap))
        print_pattern_report(pat, 'SELL', trades, cap)

    print_summary(results)


if __name__ == '__main__':
    main()