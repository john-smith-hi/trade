# Cấu hình `xml/accounts.xml`

## Quy tắc

- File thật: `xml/accounts.xml` — **không commit** (đã trong `.gitignore`).
- Mẫu: `xml/accounts.example.xml` — commit được.
- Sửa bằng tay (Notepad / VS Code / Cursor) hoặc qua trang web độc lập:
  **`http://localhost/mt5/account/`** (folder `D:\wamp64\www\mt5\account\`).
- Trang ra lệnh: `http://localhost/mt5/` — không còn form sửa XML trên trang này.
- `mt5.save_accounts()` ghi lại toàn bộ file (comment XML đầu file có thể mất sau lần lưu từ UI).

## API quản lý account (qua `api.py` / proxy.php)

| Method | Path | Việc |
|--------|------|------|
| `GET` | `/api/accounts` | List (có `path`, **không** có password) |
| `POST` | `/api/accounts` | Thêm account mới (cần name, login, password, server) |
| `PUT` | `/api/accounts/<name>` | Sửa path/suffix/multi/xauusd_max_loss/auto_copy_* |
| `POST` | `/api/reload-accounts` | Ép nạp lại XML |

**PUT không được** gửi `login` / `password` / `server` / `name` (đổi tên). Không có API xóa.

## Các trường mỗi `<account>`

| Tag | Ý nghĩa |
|-----|---------|
| `name` | Tên dùng trong `--account` / API (unique) |
| `login` / `password` / `server` | Đăng nhập MT5 (chỉ set lúc thêm; UI sửa không đổi) |
| `path` | Đường dẫn `terminal64.exe` của broker (Exness / FTMO khác nhau) |
| `suffix` | Hậu tố symbol: Exness = `m`, FTMO = `""` → `XAUUSD` → `XAUUSDm` |
| `multi` | Hệ số nhân lot khi **account này là đích copy** |
| `xauusd_max_loss` | Giới hạn \|lỗ SL\| ước tính cho XAUUSD — xem `xauusd-max-loss.md` |
| `auto_copy_enabled` | `true`/`false` |
| `auto_copy_targets` | Danh sách `name` đích, phân tách bằng dấu phẩy |

## Copy trade

- Không truyền `copy` trên API / không truyền `--copy` trên CLI → dùng `auto_copy_*` của account gốc (nếu bật).
- Truyền `copy: ""` / `--copy ""` → tắt hẳn copy.
- Lot copy (action `open`) = `lot_gốc × multi` của account đích.

## Path terminal

Khi chuyển broker (Exness ↔ FTMO), `connect_mt5` luôn `mt5.shutdown()` trước rồi `initialize(path=...)`.
Sai `path` → login/terminal không khớp account.
