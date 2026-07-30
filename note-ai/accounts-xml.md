# Cấu hình `xml/accounts.xml` + `xml/paths.xml`

## Quy tắc

- File account thật: `xml/accounts.xml` — **không commit** (đã trong `.gitignore`).
- File path: `xml/paths.xml` — khai báo `name` → `exe` (`terminal64.exe`).
- Mẫu commit được: `accounts.example.xml`, `paths.example.xml`.
- UI: `http://localhost/mt5/account/` và `http://localhost/mt5/path/` (xem `web-ui.md`).

## Path vs Account

- Trong `accounts.xml`, thẻ `<path>` là **tên** (`exness`, `ftmo`, …), **không** ghi full path filesystem.
- Full path nằm ở `paths.xml` → `<exe>`.
- `mt5.resolve_terminal_path(account)` resolve tên → exe trước khi `initialize`.
- Public API account trả thêm `path_exe` (đã resolve) để UI hiển thị.

## API

| Method | Path | Việc |
|--------|------|------|
| `GET` | `/api/paths` | List name + exe |
| `POST` | `/api/paths` | Thêm `{name, exe}` |
| `PUT` | `/api/paths/<name>` | Sửa `exe` (không đổi name) |
| `GET` | `/api/accounts` | List (có `path` = tên, `path_exe` = resolve) |
| `POST` | `/api/accounts` | Thêm account (login/password/server + field khác) |
| `PUT` | `/api/accounts/<name>` | Sửa field editable; path phải là tên trong paths.xml |

**PUT account — bị khóa cứng trong `api.py`:**

- Không đổi `name`, `login`, `password`, `server` (server giữ nguyên bản đã lưu dù client gửi).
- Không có API **xóa** account / path.

Field editable (PUT/POST): `path`, `suffix`, `multi`, `xauusd_max_loss`, `auto_copy_enabled`, `auto_copy_targets` (+ login/password/server chỉ lúc POST).

## Các trường mỗi `<account>`

| Tag | Ý nghĩa |
|-----|---------|
| `name` | Tên account (unique) |
| `login` / `password` / `server` | Đăng nhập MT5 — chỉ set lúc **thêm** |
| `path` | Tên trong `paths.xml` (`exness`, `ftmo`, …) |
| `suffix` | Exness = `m`, FTMO = `""` |
| `multi` | Hệ số lot khi là đích copy (mặc định 1.0) |
| `xauusd_max_loss` | Giới hạn lỗ XAUUSD — xem `xauusd-max-loss.md` |
| `auto_copy_enabled` / `auto_copy_targets` | Auto-copy |

## Copy trade

- Không truyền `copy` trên action → dùng `auto_copy_*` của account gốc (nếu bật).
- Lot copy (`open`) = `lot_gốc × multi` của đích.
- `xauusd_max_loss` khi copy: xem `xauusd-max-loss.md`.
