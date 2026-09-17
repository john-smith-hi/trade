"""
VNSTOCK & Global Market Analyzer

Cách sử dụng:
  python stock.py "<MÃ>" [SỐ_PHIÊN] [INTERVAL] [-s PHIÊN] [-o OUTPUT_FILE]

Tham số:
  MÃ          Mã cần xem (FPT, VNM, VNINDEX, BTC, GOLD, WTI, BRENT, NAS100, ...)
              Nhiều mã: "FPT VNM" hoặc "BTC,ETH,BNB"
  SỐ_PHIÊN    Số nến hiển thị (mặc định: 20)
  INTERVAL    Khung thời gian: 1m, 5m, 15m, 1H, 1D, 1W, 1M (mặc định: 1D)
  -s PHIÊN    Lọc theo phiên giao dịch (giờ Việt Nam):
                A   = Phiên Á   05:00 – 14:00
                Au  = Phiên Âu  14:00 – 20:00
                M   = Phiên Mỹ  20:00 – 03:00 (sáng hôm sau)
  -o FILE     Xuất kết quả ra file UTF-8

Ví dụ:
  python stock.py FPT
  python stock.py FPT 30 1H
  python stock.py "GOLD WTI" 20 1D
  python stock.py GOLD 100 1H -s M
  python stock.py BTC 100 1H -s A
  python stock.py NAS100 50 1H -s Au
  python stock.py BTC,ETH,BNB 20 1H -o out.txt
"""

import sys
import pandas as pd
from datetime import datetime, timedelta
import os
import time
import re
import io
import argparse

# Cố gắng import các thư viện phụ nếu có
try:
    from tvDatafeed import TvDatafeed, Interval
except ImportError:
    TvDatafeed = None
    
try:
    import yfinance as yf
except ImportError:
    yf = None

# Đảm bảo đầu ra (stdout) luôn sử dụng UTF-8 (fix lỗi Unicode trên Windows)
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Mapping cấu hình
TV_MAPPING = {
    'GOLD': ('XAUUSD', 'OANDA', 'Gold / USD (TradingView)'),
    'WTI': ('USOIL', 'TVC', 'WTI Crude Oil'),
    'BRENT': ('UKOIL', 'TVC', 'Brent Crude Oil'),
    'NAS100': ('BLACKBULL:NAS100', '', 'Nasdaq 100 CFD (BlackBull)')
}

YF_MAPPING = {
    'BTC': ('BTC-USD', 'Bitcoin / USD'),
    'ETH': ('ETH-USD', 'Ethereum / USD'),
    'BNB': ('BNB-USD', 'Binance Coin / USD'),
    'NAS100': ('NQ=F', 'Nasdaq 100 Futures')
}

# Chỉ số VN (dài >= 4) — phải đi vnstock, không fallback Yahoo
VN_INDICES = {
    'VNINDEX', 'VN30', 'VN100', 'VNMID', 'VNSML',
    'HNX', 'HNXINDEX', 'HNX30', 'UPCOM',
}

# Định nghĩa các phiên giao dịch (giờ VN, UTC+7)
# Giá trị: tập hợp các giờ (hour) thuộc phiên đó
SESSION_HOURS = {
    'A':  set(range(5, 14)),          # 05:00 – 13:59  (Phiên Á)
    'Au': set(range(14, 20)),         # 14:00 – 19:59  (Phiên Âu)
    'M':  {20, 21, 22, 23, 0, 1, 2, 3},  # 20:00 – 03:59  (Phiên Mỹ)
}

SESSION_LABELS = {
    'A':  'Phiên Á',
    'Au': 'Phiên Âu',
    'M':  'Phiên Mỹ',
}

def parse_interval(interval_str):
    """Phân tích chuỗi interval thành (giá trị, đơn vị)."""
    match = re.match(r"(\d+)([mMhHdDwW])", interval_str)
    if match:
        value, unit = int(match.group(1)), match.group(2)
        # Chuẩn hóa
        unit_map = {'h': 'H', 'd': 'D', 'w': 'W'}
        return value, unit_map.get(unit, unit)
    return 1, 'D'

def clean_data(df):
    """Chuẩn hóa cấu trúc dữ liệu cho tất cả các nguồn."""
    if df is None or df.empty:
        return pd.DataFrame()
    
    df = df.copy()
    
    # Chuẩn hóa tên cột thời gian
    time_cols = ['datetime', 'Date', 'Datetime', 'time', 'date']
    for col in time_cols:
        if col in df.columns:
            df.rename(columns={col: 'time'}, inplace=True)
            break
            
    if 'time' not in df.columns and isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index().rename(columns={df.index.name or 'index': 'time'})

    # Chuẩn hóa tên cột OHLCV
    col_map = {
        'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume',
        'open': 'open', 'high': 'high', 'low': 'low', 'close': 'close', 'volume': 'volume'
    }
    df.rename(columns={k: v for k, v in col_map.items() if k in df.columns}, inplace=True)
    
    # Chuyển đổi kiểu dữ liệu
    df['time'] = pd.to_datetime(df['time'])
    numeric_cols = ['open', 'high', 'low', 'close', 'volume']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
    # Sắp xếp và xóa trùng
    df = df.sort_values('time').drop_duplicates('time', keep='last')
    return df

def resample_data(df, target_interval):
    """Resample dataframe sang khung thời gian đích."""
    df = clean_data(df)
    if df.empty: return df
    
    value, unit = parse_interval(target_interval)
    pd_unit = {'m': 'min', 'M': 'ME'}.get(unit, unit)
    rule = f"{value}{pd_unit}"
    
    df = df.set_index('time')
    
    ohlc_dict = {
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
    }
    # Giữ lại các cột khác nếu có
    for col in df.columns:
        if col not in ohlc_dict: ohlc_dict[col] = 'last'
            
    resampled = df.resample(rule, label='left', closed='left').agg(ohlc_dict)
    return resampled.dropna(subset=['close']).reset_index()

def print_header(sym, full_name, interval):
    print(f"\n" + "="*50)
    print(f"      PHÂN TÍCH MÃ: {sym} {f'({full_name})' if full_name else ''} ")
    if interval:
        print(f"      Khung thời gian: {interval}")
    print("="*50)

def format_and_display_data(df, sym, limit, unit, session=None):
    """Hiển thị bảng dữ liệu đã được xử lý."""
    df = clean_data(df)
    if df.empty:
        print(f"Không tìm thấy dữ liệu cho mã {sym}.")
        return

    # Tính toán giờ Việt Nam (UTC+7)
    if df['time'].dt.tz is not None:
        df['time_vn'] = df['time'].dt.tz_convert('Asia/Ho_Chi_Minh').dt.tz_localize(None)
    else:
        df['time_vn'] = df['time']
        
    # Lọc theo phiên nếu có
    if session and session in SESSION_HOURS:
        hours = SESSION_HOURS[session]
        df = df[df['time_vn'].dt.hour.isin(hours)]
    
    df['change'] = df['close'].diff().fillna(0.0)
    # Thân / râu nến: thân = C-O (âm nếu giảm); trên = high - max(O,C); dưới = min(O,C) - low
    body_top = df[['open', 'close']].max(axis=1)
    body_bot = df[['open', 'close']].min(axis=1)
    df['body'] = df['close'] - df['open']
    df['wick_up'] = df['high'] - body_top
    df['wick_dn'] = body_bot - df['low']
    
    fmt = '%Y-%m-%d %H:%M:%S' if unit in ['m', 'H'] else '%Y-%m-%d'
    pd.options.display.float_format = '{:,.2f}'.format
    pd.options.display.max_rows = None
    pd.options.display.max_columns = None
    pd.options.display.width = None
    pd.options.display.max_colwidth = None
    
    session_label = f"({SESSION_LABELS[session]})" if session and session in SESSION_LABELS else ''
    print(f"\n--- [ LỊCH SỬ GIÁ {sym} {session_label} ] ---")
    
    show_df = df.tail(limit).copy()
    show_df['time'] = show_df['time_vn'].dt.strftime(fmt)
    
    cols = ['time', 'symbol', 'open', 'high', 'low', 'close', 'change', 'wick_up', 'body', 'wick_dn', 'volume']
    cols_available = [c for c in cols if c in show_df.columns]
    
    print(show_df[cols_available].reset_index(drop=True))

def fetch_tv_df(sym, tv_config, interval, limit, value, unit, session=None):
    """Lấy OHLC từ TradingView, trả về DataFrame đã clean (có thể rỗng)."""
    tv_sym, tv_exc, _full_name = tv_config
    if not TvDatafeed:
        raise RuntimeError(f"Thư viện tvDatafeed chưa được cài đặt (mã {sym}).")

    tv = TvDatafeed()
    tv_interval = Interval.in_daily
    if unit == 'm':
        m_map = {1: Interval.in_1_minute, 3: Interval.in_3_minute, 5: Interval.in_5_minute,
                 15: Interval.in_15_minute, 30: Interval.in_30_minute, 45: Interval.in_45_minute}
        tv_interval = next((v for k, v in m_map.items() if value <= k), Interval.in_1_hour)
    elif unit == 'H':
        h_map = {1: Interval.in_1_hour, 2: Interval.in_2_hour, 4: Interval.in_4_hour}
        tv_interval = h_map.get(value, Interval.in_daily)
    elif unit == 'D':
        tv_interval = Interval.in_daily
    elif unit == 'W':
        tv_interval = Interval.in_weekly
    elif unit == 'M':
        tv_interval = Interval.in_monthly

    fetch_limit = limit * 5 if session else limit + 5
    df = None
    for _ in range(3):
        df = tv.get_hist(
            symbol=tv_sym,
            exchange=tv_exc if tv_exc else None,
            interval=tv_interval,
            n_bars=fetch_limit,
        )
        if df is not None and not df.empty:
            break
        time.sleep(1)

    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df['symbol'] = sym
    return clean_data(df)


def fetch_yf_df(sym, yf_config, interval, limit, value, unit, session=None):
    """Lấy OHLC từ Yahoo Finance, trả về DataFrame đã clean (có thể rỗng)."""
    if yf_config:
        yf_sym, _full_name = yf_config
    else:
        yf_sym = sym

    if not yf:
        raise RuntimeError(f"Thư viện yfinance chưa được cài đặt (mã {sym}).")

    yf_interval = "1d"
    if unit == 'm':
        yf_interval = f"{value if value in [1, 2, 5, 15, 30, 60, 90] else 1}m"
    elif unit == 'H':
        yf_interval = "1h"
    elif unit == 'D':
        yf_interval = "5d" if value == 5 else "1d"
    elif unit == 'W':
        yf_interval = "1wk"
    elif unit == 'M':
        yf_interval = "3mo" if value == 3 else "1mo"

    period = "max"
    if unit == 'm':
        period = "7d" if value == 1 else "60d"
    elif unit == 'H':
        period = "730d"

    df = yf.download(tickers=yf_sym, interval=yf_interval, period=period, progress=False)
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]
    df = df.copy()
    df['symbol'] = sym
    if not (yf_interval == f"{value}{unit.lower()}" or (unit == 'H' and yf_interval == '1h' and value == 1)):
        df = resample_data(df, interval)
    return clean_data(df)


def fetch_vnstock_df(sym, limit, interval, value, unit, session=None):
    """Lấy OHLC từ vnstock, trả về DataFrame đã clean (có thể rỗng)."""
    from vnstock.api.quote import Quote
    q = Quote(symbol=sym, source='KBS')

    offset_map = {'m': 5, 'H': 10, 'D': 6, 'W': 12, 'M': 60}
    days_offset = (limit * value * offset_map.get(unit, 2))

    if unit == 'm':
        days_offset = max(7, int(value * limit / 100) + 5)
    elif unit == 'H':
        days_offset = max(10, int(value * limit / 4) + 7)
    elif unit == 'D':
        days_offset = max(30, days_offset)

    start_date = (datetime.now() - timedelta(days=int(days_offset))).strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')

    vn_base = '1D'
    if unit == 'm':
        for b in ['30m', '15m', '5m', '1m']:
            if value % int(b[:-1]) == 0:
                vn_base = b
                break
    elif unit == 'H':
        vn_base = '1H'

    df = q.history(start=start_date, end=end_date, interval=vn_base)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.sort_values('time')
    if interval.upper() != vn_base.upper():
        df = resample_data(df, interval)
    df = df.copy()
    df['symbol'] = sym
    return clean_data(df)


def fetch_stock_df(sym, limit=20, interval='1D', session=None):
    """
    Lấy OHLC cho một mã, trả về DataFrame đã clean (không in ra console).
    Router giống analyze_stock. DataFrame rỗng nếu nguồn không trả dữ liệu.
    """
    value, unit = parse_interval(interval)
    sym = sym.upper()

    if sym in TV_MAPPING:
        return fetch_tv_df(sym, TV_MAPPING[sym], interval, limit, value, unit, session=session)
    if sym in YF_MAPPING:
        return fetch_yf_df(sym, YF_MAPPING[sym], interval, limit, value, unit, session=session)
    if sym in VN_INDICES:
        return fetch_vnstock_df(sym, limit, interval, value, unit, session=session)
    if len(sym) >= 4 or sym in ['AMD', 'IBM', 'INTC', 'KO', 'DIS', 'NKE']:
        return fetch_yf_df(sym, None, interval, limit, value, unit, session=session)
    return fetch_vnstock_df(sym, limit, interval, value, unit, session=session)


def analyze_tv(sym, tv_config, interval, limit, value, unit, session=None):
    tv_sym, tv_exc, full_name = tv_config
    if not TvDatafeed:
        print(f"Bỏ qua {sym}: Thư viện tvDatafeed chưa được cài đặt.")
        return

    print_header(sym, full_name, interval)
    try:
        df = fetch_tv_df(sym, tv_config, interval, limit, value, unit, session=session)
        if not df.empty:
            format_and_display_data(df, sym, limit, unit, session=session)
            return True
        print(f"Không nhận được dữ liệu từ TradingView cho {sym}.")
        return False
    except Exception as e:
        print(f"Lỗi TradingView cho {sym}: {e}")
        return False

def analyze_yf(sym, yf_config, interval, limit, value, unit, session=None):
    if yf_config:
        yf_sym, full_name = yf_config
    else:
        yf_sym, full_name = sym, f"{sym} (Yahoo Finance)"

    if not yf:
        print(f"Bỏ qua {sym}: Thư viện yfinance chưa được cài đặt.")
        return

    print_header(sym, full_name, interval)
    try:
        df = fetch_yf_df(sym, yf_config, interval, limit, value, unit, session=session)
        if not df.empty:
            format_and_display_data(df, sym, limit, unit, session=session)
    except Exception as e:
        print(f"Lỗi yfinance cho {sym}: {e}")

def analyze_vnstock(sym, limit, interval, value, unit, session=None):
    print_header(sym, "", interval)
    try:
        df = fetch_vnstock_df(sym, limit, interval, value, unit, session=session)
        if not df.empty:
            format_and_display_data(df, sym, limit, unit, session=session)
        else:
            print(f"Không tìm thấy dữ liệu cho {sym}.")
    except Exception as e:
        print(f"Lỗi vnstock cho {sym}: {e}")

def analyze_stock(sym, limit, interval='1D', session=None):
    """
    Hàm phân tích một mã cổ phiếu cụ thể với hỗ trợ khung thời gian linh hoạt.
    Bộ điều hướng (Router) cho các loại tài sản khác nhau.
    """
    try:
        value, unit = parse_interval(interval)

        if sym in TV_MAPPING:
            analyze_tv(sym, TV_MAPPING[sym], interval, limit, value, unit, session=session)
        elif sym in YF_MAPPING:
            analyze_yf(sym, YF_MAPPING[sym], interval, limit, value, unit, session=session)
        elif sym in VN_INDICES:
            analyze_vnstock(sym, limit, interval, value, unit, session=session)
        elif len(sym) >= 4 or sym in ['AMD', 'IBM', 'INTC', 'KO', 'DIS', 'NKE']:  # Global stocks fallback
            analyze_yf(sym, None, interval, limit, value, unit, session=session)
        else:
            analyze_vnstock(sym, limit, interval, value, unit, session=session)

    except Exception as e:
        print(f"\nLỗi khởi tạo phân tích cho mã {sym}: {e}")

def main():
    parser = argparse.ArgumentParser(description="VNSTOCK & Global Market Analyzer")
    parser.add_argument("symbols", nargs="?", default="FPT", help="Danh sách mã (ví dụ: FPT,VNM hoặc GOLD, NAS100)")
    parser.add_argument("limit", type=int, nargs="?", default=20, help="Số lượng phiên (mặc định: 20)")
    parser.add_argument("interval", nargs="?", default="1D", help="Khung thời gian (1m, 1H, 1D, ...)")
    parser.add_argument(
        "-s", "--session",
        choices=list(SESSION_HOURS.keys()),
        default=None,
        help="Lọc phiên: A = Phiên Á (05-14h), Au = Phiên Âu (14-20h), M = Phiên Mỹ (20-03h)"
    )
    parser.add_argument("-o", "--output", help="Đường dẫn file để xuất kết quả")
    
    args = parser.parse_args()

    symbols_list = args.symbols.replace(',', ' ').split()
    limit = args.limit
    interval = args.interval
    session = args.session  # None | 'A' | 'Au' | 'M'

    # Backward-compat: strip hậu tố 'm'/'M' khỏi tên mã nếu user vẫn dùng cú pháp cũ
    # (chỉ cảnh báo, không lỗi)
    cleaned_symbols = []
    for sym in symbols_list:
        if len(sym) > 1 and sym.endswith('m'):
            print(f"[CẢNH BÁO] Hậu tố 'm' trong '{sym}' đã lỗi thời. Dùng '-s M' thay thế.")
            sym = sym[:-1]
            if session is None:
                session = 'M'
        elif len(sym) > 1 and sym.endswith('M'):
            base = sym[:-1].upper()
            if base in TV_MAPPING or base in YF_MAPPING:
                print(f"[CẢNH BÁO] Hậu tố 'M' trong '{sym}' đã lỗi thời. Dùng '-s M' thay thế.")
                sym = base
                if session is None:
                    session = 'M'
        cleaned_symbols.append(sym)
    symbols_list = cleaned_symbols

    # Redirect stdout sang file nếu có tham số -o
    original_stdout = sys.stdout
    f_output = None
    if args.output:
        output_dir = os.path.dirname(args.output)
        if output_dir: os.makedirs(output_dir, exist_ok=True)
        f_output = open(args.output, 'w', encoding='utf-8')
        sys.stdout = f_output

    try:
        session_label = f" | {SESSION_LABELS[session]}" if session and session in SESSION_LABELS else ''
        print("="*50)
        print(f"      VNSTOCK 4.x OPTIMIZED ANALYZER")
        print(f"      Danh sách: {', '.join(symbols_list)}")
        print(f"      Khung: {interval}, Số lượng: {limit}{session_label}")
        print("="*50)

        for sym in symbols_list:
            if not sym: continue
            analyze_stock(sym.upper(), limit, interval, session=session)

        print("\n" + "="*50)
        print("      HOÀN THÀNH PHÂN TÍCH          ")
        print("="*50)
    finally:
        if f_output is not None:
            sys.stdout = original_stdout
            f_output.close()
            print(f"Kết quả lưu tại: {args.output}")

if __name__ == "__main__":
    main()
