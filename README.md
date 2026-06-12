# VNSTOCK API & GLOBAL MARKET ANALYZER

Bộ công cụ phân tích thị trường tài chính đa năng, tích hợp dữ liệu từ **Vnstock (KBS)**, **Yahoo Finance** và **TradingView**. Chương trình hỗ trợ theo dõi cổ phiếu Việt Nam, chỉ số thế giới, tiền điện tử và hàng hóa (Vàng, Dầu).

## 1. Tính năng nổi bật
- **Đa tài sản**: Cổ phiếu VN (HOSE, HNX, UPCOM), Crypto (BTC, ETH, BNB), Chỉ số (NAS100), Hàng hóa (WTI, BRENT, GOLD).
- **Múi giờ Việt Nam**: Tự động chuyển đổi tất cả dữ liệu quốc tế sang giờ Việt Nam (UTC+7).
- **Lọc phiên Mỹ ('M')**: Hỗ trợ lọc nhanh các khung giờ biến động mạnh của thị trường Mỹ (20:00 - 03:00 VN).
- **Hiển thị đầy đủ**: Cấu hình Pandas hiển thị toàn bộ dữ liệu, không bị cắt bới (...).
- **Khung thời gian linh hoạt**: Hỗ trợ từ 1 phút (`1m`) đến 1 tháng (`1M`).

## 2. Cài đặt môi trường
Yêu cầu Python >= 3.7 và các thư viện hỗ trợ:
```bash
pip install vnstock yfinance tvDatafeed pandas<3.0.0 pytz
```

## 3. Cách chạy chương trình
Cấu trúc lệnh:
```bash
python stock.py "<DANH_SÁCH_MÃ>" <SỐ_PHIÊN> <INTERVAL> [MINIMAL_MODE] [-o OUTPUT_FILE]
```

### Các tham số:
1.  **DANH_SÁCH_MÃ**: Mã cổ phiếu (VNM, FPT), Crypto (BTC), Hàng hóa (GOLD, WTI, BRENT) hoặc Index (NAS100).
    - Thêm hậu tố **'M'** để chỉ lấy dữ liệu trong phiên Mỹ (20:00 - 03:00). Ví dụ: `NAS100M`.
2.  **SỐ_PHIÊN**: Số lượng nến/thanh dữ liệu muốn xem (Mặc định: 20).
3.  **INTERVAL**: Khung thời gian (Ví dụ: `1m`, `1h`, `1H`, `1D`, `1W`, `1M`).
4.  **MINIMAL_MODE**: (Tùy chọn) 
    - `1`: Chỉ hiển thị bảng lịch sử giá (Mặc định).
    - `0`: Hiển thị đầy đủ báo cáo tài chính (chỉ cho mã VN).
5.  **-o / --output**: (Tùy chọn) Đường dẫn file để lưu kết quả. Dữ liệu sẽ được lưu với mã hóa UTF-8 chuẩn.

## 4. Ví dụ sử dụng

### Xem giá Vàng (XAUUSD) từ TradingView
```bash
python stock.py GOLD 10 1H
```

### Xem Nasdaq 100 phiên Mỹ (20:00 - 03:00 VN)
```bash
python stock.py NAS100M 100 1H
```

### Xem dầu thô WTI và BRENT
```bash
python stock.py "WTI BRENT" 20 1D
```

### Xem nhiều mã Crypto cùng lúc
```bash
python stock.py BTC,ETH,BNB 20 1H
```

60: Chức năng này sẽ quét toàn bộ sàn HOSE và lọc ra các mã đạt tiêu chuẩn về thanh khoản, xu hướng (Price > SMA20/50) và điểm nổ (Breakout). Kết quả lưu tại `result.txt`.
61: 
62: ### Lấy tất cả mã của một sàn (HOSE, HNX, UPCOM)
63: ```bash
64: python stock.py HOSE -all-code
65: ```
66: Lệnh này sẽ liệt kê toàn bộ các mã chứng khoán đang niêm yết trên sàn tương ứng.
67: 

## 5. Danh sách mã đặc biệt hỗ trợ
| Mã | Mô tả | Nguồn |
|---|---|---|
| `GOLD` | Giá Vàng (XAUUSD) | TradingView |
| `WTI` | Dầu thô WTI (CL=F) | Yahoo Finance |
| `BRENT` | Dầu thô Brent (BZ=F) | Yahoo Finance |
| `NAS100` | Chỉ số Nasdaq 100 (NQ=F) | Yahoo Finance |
| `BTC/ETH/BNB` | Tiền điện tử | Yahoo Finance |

---
**Lưu ý**: Dữ liệu có thể bị trễ vài phút tùy thuộc vào API nguồn. Đối với dữ liệu phút/giờ, chương trình tự động bù đắp các khoảng trống dữ liệu để đảm bảo timeline liên tục.
