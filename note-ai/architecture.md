# Kiến trúc hệ thống

## Luồng chạy

```
start_api.bat
  → python api.py          (Flask, 127.0.0.1:5001)
      → import mt5.py      (logic MT5 + đọc xml/accounts.xml, xml/paths.xml)
```

Web UI (không nằm trong repo trade):

- Thư mục: `D:\wamp64\www\mt5\`
- Chi tiết trang / cache / JS: xem `web-ui.md`
- Trình duyệt → `proxy.php` → `http://127.0.0.1:5001/...`
- Lý do có proxy: `api.py` chỉ bind localhost; máy khác / ngrok không gọi thẳng được.

## File trong repo `trade`

| File | Vai trò |
|------|---------|
| `mt5.py` | CLI + logic giao dịch, load/save accounts + paths, copy trade |
| `api.py` | HTTP mỏng bọc `mt5.execute_request`, CORS, lock thread, CRUD accounts/paths, history |
| `start_api.bat` | Khởi động API |
| `xml/accounts.xml` | Config account thật (**gitignore**, không commit) |
| `xml/paths.xml` | Map tên path (`exness` / `ftmo` / …) → `terminal64.exe` |
| `xml/accounts.example.xml` / `paths.example.xml` | Mẫu an toàn để commit |
| `history_mt5.txt` | Lịch sử lệnh (text, parse thành bảng trên web) |
| `stock.py` | Công cụ riêng (không phải API MT5) |

## Endpoint API

| Method | Path | Việc |
|--------|------|------|
| `GET` | `/api/paths` | List path `{name, exe}` |
| `POST` | `/api/paths` | Thêm path `{name, exe}` |
| `PUT` | `/api/paths/<name>` | Sửa `exe` (không đổi name) |
| `GET` | `/api/accounts` | List account (không password; có `path` + `path_exe`) |
| `POST` | `/api/accounts` | Thêm account (gồm login/password/server) |
| `PUT` | `/api/accounts/<name>` | Sửa cấu hình — **không** đổi login/password/server/name |
| `POST` | `/api/reload-accounts` | Ép nạp lại XML accounts (+ paths fresh) |
| `POST` | `/api/action` | status / open / close-all / modify-all |
| `GET` | `/api/quote?account=&symbol=&side=` | bid / ask / entry — UI điền TP/SL khi **open** |
| `GET` | `/api/positions?account=` | Lệnh mở JSON — UI điền TP/SL khi **modify-all** |
| `GET` | `/api/history?limit=50` | `{ lines, rows }` — raw + parse bảng |

**Không có** API xóa account / path.

## State toàn cục trong `mt5.py` (quan trọng)

- `ACCOUNTS` — list account trong RAM
- `PATHS` — list path trong RAM (`name` → `exe`)
- `CURRENT_ACCOUNT_NAME` — account đang connect
- `_ACTIVE_XAUUSD_MAX_LOSS` — giới hạn đang áp dụng cho action hiện tại
- `NO_ASK` — `True` mới gửi lệnh thật; không có thì chỉ preview
- Kết nối MT5: `connect_mt5` dùng `resolve_terminal_path(account)` → exe từ `paths.xml`
- Mỗi action: `connect_mt5` → `mt5.shutdown()` ở finally
- Soft reload: `ensure_accounts_fresh()` / `ensure_paths_fresh()` theo mtime XML

Hai request web không được chạy song song vào MT5 → `api.py` dùng `threading.Lock()`.
