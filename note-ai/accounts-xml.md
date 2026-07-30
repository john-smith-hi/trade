# Cấu hình `xml/accounts.xml`

## Quy tắc

- File thật: `xml/accounts.xml` — **không commit** (đã trong `.gitignore`).
- Mẫu: `xml/accounts.example.xml` — commit được.
- Sửa bằng tay (Notepad / VS Code / Cursor) là cách chính; `mt5.save_accounts()` cũng ghi được.

## Các trường mỗi `<account>`

| Tag | Ý nghĩa |
|-----|---------|
| `name` | Tên dùng trong `--account` / API (unique) |
| `login` / `password` / `server` | Đăng nhập MT5 |
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
