# Kiến trúc hệ thống

## Luồng chạy

```
start_api.bat
  → python api.py          (Flask, 127.0.0.1:5001)
      → import mt5.py      (logic MT5 + đọc xml/accounts.xml)
```

Web UI (không nằm trong repo trade):

- Thư mục: `D:\wamp64\www\mt5\`
- Trang ra lệnh: `index.html`, `app.js`, `proxy.php`, `style.css` → `http://localhost/mt5/`
- Trang quản lý account: `account/index.html`, `account/account.js` → `http://localhost/mt5/account/`
- Trình duyệt → `proxy.php` → `http://127.0.0.1:5001/...`
- Lý do có proxy: `api.py` chỉ bind localhost; máy khác / ngrok không gọi thẳng được.

## File trong repo `trade`

| File | Vai trò |
|------|---------|
| `mt5.py` | CLI + toàn bộ logic giao dịch, load/save accounts, copy trade |
| `api.py` | HTTP mỏng bọc `mt5.execute_request`, CORS, lock thread |
| `start_api.bat` | Khởi động API |
| `xml/accounts.xml` | Config account thật (**gitignore**, không commit) |
| `xml/accounts.example.xml` | Mẫu an toàn để commit |
| `history_mt5.txt` | Lịch sử lệnh (text) |
| `stock.py` | Công cụ riêng (không phải API MT5) |

## Endpoint API

- `GET  /api/accounts` — danh sách account (không có password)
- `POST /api/reload-accounts` — ép nạp lại XML
- `POST /api/action` — status / open / close-all / modify-all
- `GET  /api/history?limit=50`

## State toàn cục trong `mt5.py` (quan trọng)

- `ACCOUNTS` — list account trong RAM (đọc từ XML lúc import / reload)
- `CURRENT_ACCOUNT_NAME` — account đang connect
- `_ACTIVE_XAUUSD_MAX_LOSS` — giới hạn đang áp dụng cho action hiện tại
- `NO_ASK` — `True` mới gửi lệnh thật; không có thì chỉ preview
- Kết nối MT5: mỗi action gọi `connect_mt5` → `mt5.shutdown()` ở finally

Hai request web không được chạy song song vào MT5 → `api.py` dùng `threading.Lock()`.
