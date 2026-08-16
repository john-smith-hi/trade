# trade

Bộ công cụ local: giao dịch MetaTrader 5 (CLI + web), checklist vào lệnh theo tuần, và phân tích giá cổ phiếu / hàng hóa / crypto.

Web UI chạy trên WAMP (`D:\wamp64\www`). API Python chỉ lắng nghe `127.0.0.1:5001`.

## Cấu trúc

| File / thư mục | Việc |
|----------------|------|
| `mt5.py` | CLI + logic MT5 (mở lệnh, pending, copy trade, XML accounts/paths) |
| `api.py` | HTTP API Flask bọc `mt5.py` và `day_trade.py` |
| `start_api.bat` | Khởi động API |
| `copy_www.py` | Xóa folder đích rồi copy UI `mt5/` / `setup/` sang `D:\wamp64\www` (không dùng tên `copy.py`) |
| `mt5/` | Giao diện ra lệnh / account / path / lịch sử |
| `setup/` | Giao diện checklist vào lệnh theo tuần |
| `day_trade.py` | Chấm điểm setup, đọc/ghi `xml/day_trade_week.xml` |
| `stock.py` | Phân tích giá (vnstock / Yahoo / TradingView) |
| `xml/` | Cấu hình account, path terminal, checklist tuần |
| `note-ai/` | Ghi chú kiến trúc cho lần sửa sau |

`xml/accounts.xml`, `xml/paths.xml`, `xml/day_trade_week.xml` **không commit** (đã `.gitignore`). Lấy mẫu từ các file `*.example.xml`.

---

## Cài đặt

Python trên Windows. MT5 cần cài sẵn terminal (Exness / FTMO / …).

```bash
python -m pip install MetaTrader5 flask flask-cors
```

`stock.py` (tùy chọn):

```bash
python -m pip install vnstock yfinance tvDatafeed pandas pytz
```

Lần đầu chạy `mt5.py` / `api.py`: nếu chưa có `xml/accounts.xml` hoặc `xml/paths.xml`, script tự copy từ file example. Điền login/password/server và đường dẫn `terminal64.exe` thật vào đó.

---

## 1. MetaTrader 5 (`mt5.py`)

Gửi lệnh thật **chỉ khi** có `--no-ask`. Không có cờ này thì chỉ xem trước.

### Action

| Action | Việc |
|--------|------|
| `status` | Balance, lệnh mở, lệnh chờ |
| `open` | Lệnh thị trường (bắt buộc TP + SL) |
| `pending` | Lệnh chờ tại giá (`limit` hoặc `stop`) |
| `cancel-pending` | Hủy toàn bộ lệnh chờ |
| `close-all` | Đóng hết lệnh mở |
| `modify-all` | Sửa TP/SL tất cả lệnh mở |

### Pending

- Buy Limit: giá chờ **&lt;** ask · Buy Stop: giá chờ **&gt;** ask
- Sell Limit: giá chờ **&gt;** bid · Sell Stop: giá chờ **&lt;** bid
- Bắt buộc `--price`, `--tp-price`, `--sl-price`

### Copy trade

- Không truyền `--copy` → dùng `auto_copy_enabled` / `auto_copy_targets` của account (nếu bật)
- `--copy "prop_demo,prop_1"` → copy đúng danh sách đó
- `--copy ""` → tắt copy lần chạy đó
- Lot đích = lot gốc × `multi` của account đích (với `open` và `pending`)
- `xauusd_max_loss`: account đích bỏ trống thì lấy của gốc × `multi`

### Ví dụ CLI

```bash
python mt5.py --account fake --action status

python mt5.py --account fake --action open --symbol XAUUSD --side buy --lot 0.01 --tp-price 60000 --sl-price 58000 --no-ask

python mt5.py --account fake --action pending --symbol XAUUSD --side buy --pending-type limit --price 2500 --lot 0.01 --tp-price 2550 --sl-price 2480 --no-ask

python mt5.py --account fake --action cancel-pending --no-ask
```

Lịch sử gửi lệnh: `history_mt5.txt` (dòng mới nhất ở đầu).

### XML account / path

Trong `accounts.xml`, thẻ `<path>` là **tên** (`exness`, `ftmo`, …), không phải đường dẫn file. Đường dẫn `terminal64.exe` nằm ở `paths.xml`.

| Tag account | Ý nghĩa |
|-------------|---------|
| `name` | Tên dùng với `--account` |
| `login` / `password` / `server` | Đăng nhập MT5 |
| `path` | Tên trong `paths.xml` |
| `suffix` | Hậu tố symbol (Exness = `m`, FTMO = rỗng) |
| `multi` | Hệ số lot khi là đích copy |
| `xauusd_max_loss` | Trần lỗ ước tính XAUUSD (trống = không giới hạn) |
| `auto_copy_enabled` / `auto_copy_targets` | Tự copy sang account khác |

PUT account trên web **không** đổi `name` / `login` / `password` / `server`. Không có API xóa account/path.

---

## 2. API + Web UI

```bash
python api.py
# hoặc start_api.bat
```

API: `http://127.0.0.1:5001` (chỉ localhost). Sửa `.py` hoặc `.xml` → process tự restart.

### Đưa UI lên WAMP

```bash
python copy_www.py              # xóa www/mt5 + www/setup rồi copy lại
python copy_www.py mt5          # chỉ giao diện ra lệnh
python copy_www.py setup        # chỉ checklist
python copy_www.py --dest E:\www
```

Sau đó:

- Ra lệnh: http://localhost/mt5/
- Accounts: http://localhost/mt5/account/
- Path terminal: http://localhost/mt5/path/
- Lịch sử: http://localhost/mt5/history/
- Checklist tuần: http://localhost/setup/

Trình duyệt gọi `proxy.php` → `127.0.0.1:5001` (cần API đang chạy). CSS/JS gắn `?v=` từ `ver.php` (mtime) để cache đúng.

Trang ra lệnh: **Xem trước** không gửi lệnh; **Xác nhận gửi lệnh thật** = `--no-ask`.

### Endpoint chính

| Method | Path | Việc |
|--------|------|------|
| GET/POST/PUT | `/api/paths` | Path terminal |
| GET/POST/PUT | `/api/accounts` | Account (GET không trả password) |
| POST | `/api/reload-accounts` | Nạp lại XML |
| POST | `/api/action` | status / open / pending / cancel-pending / close-all / modify-all |
| GET | `/api/quote` | bid / ask / entry |
| GET | `/api/positions` | Lệnh đang mở |
| GET | `/api/orders` | Lệnh chờ |
| GET | `/api/history` | `history_mt5.txt` đã parse |
| GET/PUT | `/api/setup/week` | Tuần checklist |
| POST/PUT/DELETE | `/api/setup/setups` | Setup trong tuần |

Hai request MT5 không chạy song song (`threading.Lock` trong `api.py`).

---

## 3. Checklist vào lệnh (`setup/` + `day_trade.py`)

Theo `day_trade_mindset.txt`. Dữ liệu: `xml/day_trade_week.xml`.

- Tuần T2–T6 (giờ VN): tuần `active`, ghi được
- Thứ 2: chỉ quan sát, không vào lệnh
- Qua T6: tuần `closed`
- Thứ 2 tuần sau: tạo tuần mới

Không gửi lệnh MT5 — chỉ chấm điểm setup thủ công.

---

## 4. Phân tích giá (`stock.py`)

```bash
python stock.py "<MÃ>" [SỐ_NẾN] [INTERVAL] [-o FILE]
```

- Cổ phiếu VN: `FPT`, `VNM`, `VNINDEX`, …
- Global: `GOLD`, `WTI`, `BRENT`, `NAS100`, `BTC`, `ETH`, `BNB`
- Nhiều mã: `"GOLD WTI"` hoặc `BTC,ETH,BNB`
- Hậu tố `m`: lọc phiên Mỹ 20:00–03:00 VN (ví dụ `GOLDm`, `NAS100M`)
- Interval: `1m`, `5m`, `15m`, `1H`, `1D`, `1W`, `1M` (mặc định `1D`)

```bash
python stock.py GOLD 10 1H
python stock.py NAS100M 100 1H
python stock.py BTC,ETH,BNB 20 1H -o out.txt
```

---

## An toàn

- `api.py` không bind ra mạng ngoài.
- Không có `--no-ask` / không bấm xác nhận trên web → không gửi lệnh.
- `xml/accounts.xml` chứa mật khẩu thật — giữ ngoài git.
- Ghi chú chi tiết: `note-ai/`.
