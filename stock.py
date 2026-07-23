"""
VNSTOCK & Global Market Analyzer

Cách sử dụng:
  python stock.py "<MÃ>" [SỐ_PHIÊN] [INTERVAL] [-o OUTPUT_FILE]

Tham số:
  MÃ          Mã cần xem (FPT, VNM, BTC, GOLD, WTI, BRENT, NAS100, ...)
              Nhiều mã: "FPT VNM" hoặc "BTC,ETH,BNB"
              Hậu tố m (chữ thường): lọc phiên Mỹ 20:00-03:00 VN
              (vd: GOLDm, BTCm, NAS100m — áp dụng cho bất kỳ mã nào)
              Hậu tố M (chữ hoa, tương thích cũ): NAS100M cũng lọc phiên Mỹ
              nếu base thuộc Global Assets (không ảnh hưởng mã VN như VNM)
  SỐ_PHIÊN    Số nến hiển thị (mặc định: 20)
  INTERVAL    Khung thời gian: 1m, 5m, 15m, 1H, 1D, 1W, 1M (mặc định: 1D)
  -o FILE     Xuất kết quả ra file UTF-8

Ví dụ:
  python stock.py FPT
  python stock.py FPT 30 1H
  python stock.py "GOLD WTI" 20 1D
  python stock.py GOLDm 100 1H
  python stock.py NAS100M 100 1H
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

def format_and_display_data(df, sym, limit, unit, us_only=False):
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
        
    # Lọc phiên Mỹ (20:00 tới 03:00 sáng hôm sau giờ VN)
    if us_only:
        df = df[df['time_vn'].dt.hour.isin([20, 21, 22, 23, 0, 1, 2, 3])]
    
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
    
    print(f"\n--- [ LỊCH SỬ GIÁ {sym} {'(Phiên Mỹ)' if us_only else ''} ] ---")
    
    show_df = df.tail(limit).copy()
    show_df['time'] = show_df['time_vn'].dt.strftime(fmt)
    
    cols = ['time', 'symbol', 'open', 'high', 'low', 'close', 'change', 'wick_up', 'body', 'wick_dn', 'volume']
    cols_available = [c for c in cols if c in show_df.columns]
    
    print(show_df[cols_available].reset_index(drop=True))

def analyze_tv(sym, tv_config, interval, limit, value, unit, us_only=False):
    tv_sym, tv_exc, full_name = tv_config
    if not TvDatafeed:
        print(f"Bỏ qua {sym}: Thư viện tvDatafeed chưa được cài đặt.")
        return
        
    print_header(sym, full_name, interval)
    try:
        tv = TvDatafeed()
        # Mapping interval
        tv_interval = Interval.in_daily
        if unit == 'm':
            m_map = {1: Interval.in_1_minute, 3: Interval.in_3_minute, 5: Interval.in_5_minute, 
                     15: Interval.in_15_minute, 30: Interval.in_30_minute, 45: Interval.in_45_minute}
            tv_interval = next((v for k, v in m_map.items() if value <= k), Interval.in_1_hour)
        elif unit == 'H':
            h_map = {1: Interval.in_1_hour, 2: Interval.in_2_hour, 4: Interval.in_4_hour}
            tv_interval = h_map.get(value, Interval.in_daily)
        elif unit == 'D': tv_interval = Interval.in_daily
        elif unit == 'W': tv_interval = Interval.in_weekly
        elif unit == 'M': tv_interval = Interval.in_monthly
        
        fetch_limit = limit * 5 if us_only else limit + 5
        df = None
        for _ in range(3):
            df = tv.get_hist(symbol=tv_sym, exchange=tv_exc if tv_exc else None, interval=tv_interval, n_bars=fetch_limit)
            if df is not None and not df.empty: break
            time.sleep(1)
            
        if df is not None and not df.empty:
            df['symbol'] = sym
            format_and_display_data(df, sym, limit, unit, us_only=us_only)
            return True
        else:
            print(f"Không nhận được dữ liệu từ TradingView cho {sym}.")
            return False
    except Exception as e:
        print(f"Lỗi TradingView cho {sym}: {e}")
        return False

def analyze_yf(sym, yf_config, interval, limit, value, unit, us_only=False):
    if yf_config:
        yf_sym, full_name = yf_config
    else:
        yf_sym, full_name = sym, f"{sym} (Yahoo Finance)"
    
    if not yf:
        print(f"Bỏ qua {sym}: Thư viện yfinance chưa được cài đặt.")
        return
        
    print_header(sym, full_name, interval)
    try:
        yf_interval = "1d"
        if unit == 'm': yf_interval = f"{value if value in [1,2,5,15,30,60,90] else 1}m"
        elif unit == 'H': yf_interval = "1h"
        elif unit == 'D': yf_interval = "5d" if value == 5 else "1d"
        elif unit == 'W': yf_interval = "1wk"
        elif unit == 'M': yf_interval = "3mo" if value == 3 else "1mo"
        
        # Tự động tính period
        period = "max"
        if unit == 'm': period = "7d" if value == 1 else "60d"
        elif unit == 'H': period = "730d"
        
        df = yf.download(tickers=yf_sym, interval=yf_interval, period=period, progress=False)
        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]
            df['symbol'] = sym
            if not (yf_interval == f"{value}{unit.lower()}" or (unit == 'H' and yf_interval == '1h' and value == 1)):
                df = resample_data(df, interval)
            format_and_display_data(df, sym, limit, unit, us_only=us_only)
    except Exception as e:
        print(f"Lỗi yfinance cho {sym}: {e}")

def analyze_vnstock(sym, limit, interval, value, unit, us_only=False):
    print_header(sym, "", interval)
    try:
        from vnstock.api.quote import Quote
        q = Quote(symbol=sym, source='KBS')
        
        # Tính toán offset ngày (Lookback window)
        # Tăng hệ số để đảm bảo lấy đủ số nến cho cả các mã thanh khoản thấp
        offset_map = {'m': 5, 'H': 10, 'D': 6, 'W': 12, 'M': 60}
        days_offset = (limit * value * offset_map.get(unit, 2))
        
        # Điều chỉnh cho các khung thời gian ngắn hoặc yêu cầu quá ít
        if unit == 'm': days_offset = max(7, int(value * limit / 100) + 5)
        elif unit == 'H': days_offset = max(10, int(value * limit / 4) + 7)
        elif unit == 'D': days_offset = max(30, days_offset) # Tối thiểu 30 ngày cho khung D

        start_date = (datetime.now() - timedelta(days=int(days_offset))).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        # Mapping interval cho vnstock
        vn_base = '1D'
        if unit == 'm':
            for b in ['30m', '15m', '5m', '1m']:
                if value % int(b[:-1]) == 0:
                    vn_base = b
                    break
        elif unit == 'H': vn_base = '1H'
        
        df = q.history(start=start_date, end=end_date, interval=vn_base)
        if not df.empty:
            df = df.sort_values('time')
            if interval.upper() != vn_base.upper():
                df = resample_data(df, interval)
            format_and_display_data(df, sym, limit, unit, us_only=us_only)
        else:
            print(f"Không tìm thấy dữ liệu cho {sym}.")
    except Exception as e:
        print(f"Lỗi vnstock cho {sym}: {e}")

def analyze_stock(sym, limit, interval='1D', us_only=False):
    """
    Hàm phân tích một mã cổ phiếu cụ thể với hỗ trợ khung thời gian linh hoạt.
    Bộ điều hướng (Router) cho các loại tài sản khác nhau.
    """
    try:
        value, unit = parse_interval(interval)
        
        if sym in TV_MAPPING:
            analyze_tv(sym, TV_MAPPING[sym], interval, limit, value, unit, us_only=us_only)
        elif sym in YF_MAPPING:
            analyze_yf(sym, YF_MAPPING[sym], interval, limit, value, unit, us_only=us_only)
        elif len(sym) >= 4 or sym in ['AMD', 'IBM', 'INTC', 'KO', 'DIS', 'NKE']: # Global stocks fallback
            analyze_yf(sym, None, interval, limit, value, unit, us_only=us_only)
        else:
            analyze_vnstock(sym, limit, interval, value, unit, us_only=us_only)
            
    except Exception as e:
        print(f"\nLỗi khởi tạo phân tích cho mã {sym}: {e}")

def main():
    parser = argparse.ArgumentParser(description="VNSTOCK & Global Market Analyzer")
    parser.add_argument("symbols", nargs="?", default="FPT", help="Danh sách mã (ví dụ: FPT,VNM hoặc GOLDm, NAS100M)")
    parser.add_argument("limit", type=int, nargs="?", default=20, help="Số lượng phiên (mặc định: 20)")
    parser.add_argument("interval", nargs="?", default="1D", help="Khung thời gian (1m, 1H, 1D, ...)")
    parser.add_argument("-o", "--output", help="Đường dẫn file để xuất kết quả")
    
    args = parser.parse_args()

    symbols_list = args.symbols.replace(',', ' ').split()
    limit = args.limit
    interval = args.interval
    
    # Redirect stdout sang file nếu có tham số -o
    original_stdout = sys.stdout
    f_output = None
    if args.output:
        output_dir = os.path.dirname(args.output)
        if output_dir: os.makedirs(output_dir, exist_ok=True)
        f_output = open(args.output, 'w', encoding='utf-8')
        sys.stdout = f_output

    try:
        print("="*50)
        print(f"      VNSTOCK 4.x OPTIMIZED ANALYZER")
        print(f"      Danh sách: {', '.join(symbols_list)}")
        print(f"      Khung: {interval}, Số lượng: {limit}")
        print("="*50)

        for sym in symbols_list:
            if not sym: continue
            us_only = False
            # Hậu tố 'm' (chữ thường): bất kỳ mã nào cũng lọc phiên Mỹ (vd: GOLDm, BTCm)
            if len(sym) > 1 and sym.endswith('m'):
                sym, us_only = sym[:-1], True
            # Hậu tố 'M' (chữ hoa, tương thích cũ): chỉ strip nếu base thuộc Global Assets
            # để không làm hỏng mã VN như VNM
            elif len(sym) > 1 and sym.endswith('M'):
                base = sym[:-1].upper()
                if base in TV_MAPPING or base in YF_MAPPING:
                    sym, us_only = base, True

            analyze_stock(sym.upper(), limit, interval, us_only=us_only)

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
