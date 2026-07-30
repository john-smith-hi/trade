# Auto-reload (.py và .xml)

## Mục tiêu đã thống nhất

Sửa **bất kỳ `.py` hoặc `.xml`** trong project → nội dung được làm mới, không cần restart tay `start_api.bat` lâu dài (process tự restart / soft-reload).

## Cách triển khai hiện tại (`api.py`)

1. Flask `use_reloader=True`
2. `extra_files=_watch_extra_files()` theo dõi:
   - mọi `*.py` ở root project
   - mọi `*.xml` (rglob) — gồm `accounts.xml` và `paths.xml`
3. Soft-reload trong `mt5.py` (không chờ reloader ~1s):
   - `ensure_paths_fresh()` — mtime `paths.xml` → nạp lại `PATHS`
   - `ensure_accounts_fresh()` — mtime accounts (+ gọi paths fresh) → nạp lại `ACCOUNTS`
4. Gọi soft-reload trước các endpoint đọc/ghi account, path, action.

## Web UI

Backend reload ≠ UI cập nhật. UI (`common.js` / từng trang):

- Cache GET ~15s — nút **Tải lại** / `useCache: false` khi cần data mới ngay.
- Reload khi tab hiện lại / window focus (throttle ~20s).
- Accounts / Path: nút tải lại danh sách.
- Trade: không block UI mỗi lần action nếu list account đã có.

Chi tiết cache asset CSS/JS: `web-ui.md` (`ver.php` + `?v=`).

## Lưu ý lịch sử (đừng lặp lại)

Commit cũ chỉ soft-reload XML theo mtime + watch `*.py` — **không** watch XML → user sửa XML vẫn thấy config cũ trên process chưa restart.
Đã sửa: XML cũng nằm trong `extra_files` + soft-reload mtime.

## Sau khi đổi code `api.py` lần đầu

Vẫn cần **restart một lần** `start_api.bat` để process nhận logic watch mới.
