# Auto-reload (.py và .xml)

## Mục tiêu đã thống nhất

Sửa **bất kỳ `.py` hoặc `.xml`** trong project → nội dung được làm mới, không cần restart tay `start_server.bat` lâu dài (process tự restart / soft-reload).

## Cách triển khai hiện tại

`start_server.bat` đặt `TRADE_SERVER=1`. **Không** dùng Flask/Werkzeug reloader: trên Windows reloader dễ để 2 process `LISTEN` cùng cổng 5001 (TCP nối được, không trả HTTP → UI timeout 12s).

1. Một process gọi `make_server` và giữ cổng.
2. Thread poll ~0.4s, chữ ký mtime+size của:
   - mọi `*.py` ở root project
   - mọi `*.xml` (rglob) — gồm `accounts.xml` và `paths.xml`
   - loại XML đổi liên tục: tuần checklist, timer, fibo, modify-if, telegram, watch
3. File đổi và yên ~0.5s → đợi lock MT5 tối đa 8s (rồi nhả lock) → `os._exit(3)` ngay. Không `server.shutdown()` + ngủ: socket đóng mà process không chết thì bat không chạy lại, API tắt hẳn.
4. `start_server.bat` thấy mã 3 thì chạy `python api.py` lại ngay (import bản mới). Mã khác (crash) thì đợi 5 giây.
5. Soft-reload trong `mt5.py` (không chờ restart):
   - `ensure_paths_fresh()` — mtime `paths.xml` → nạp lại `PATHS`
   - `ensure_accounts_fresh()` — mtime accounts (+ gọi paths fresh) → nạp lại `ACCOUNTS`
6. Gọi soft-reload trước các endpoint đọc/ghi account, path, action.

`python api.py` không qua bat vẫn dùng Werkzeug reloader (`USE_RELOADER`). Đừng bật reloader đó trong `start_server.bat`.

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

## Sau khi gắn cơ chế thoát mã 3 lần đầu

Process đang chạy bằng bản `api.py` cũ **không** tự nạp cơ chế mới. Tắt rồi mở `start_server.bat` **một lần**. Những lần sửa `.py` / `.xml` sau đó bat tự chạy lại.
