# Auto-reload (.py và .xml)

## Mục tiêu đã thống nhất

Sửa **bất kỳ `.py` hoặc `.xml`** trong project → nội dung phải được làm mới, không cần restart tay `start_api.bat` lâu dài (process tự restart).

## Cách triển khai hiện tại (`api.py`)

1. Flask `use_reloader=True`
2. `extra_files=_watch_extra_files()` theo dõi:
   - mọi `*.py` ở root project
   - mọi `*.xml` (rglob)
   - luôn gồm `xml/accounts.xml`
3. Lớp phụ: `mt5.ensure_accounts_fresh()` — so `mtime` file, nạp lại `ACCOUNTS` trước
   `GET /api/accounts` và `POST /api/action` (không chờ reloader ~1s).

## Web UI (`D:\wamp64\www\mt5\app.js`)

Backend reload ≠ UI cập nhật. Đã bổ sung:

- `loadAccounts()` trước mỗi `submitAction`
- reload khi tab hiện lại / window focus
- nút **Tải lại danh sách** → `POST /api/reload-accounts`

## Lưu ý lịch sử (đừng lặp lại)

Commit `2f04728` chỉ soft-reload XML theo mtime + watch `*.py` — **không** watch XML, **không** sửa UI → user vẫn thấy config cũ.
Đã sửa: XML cũng nằm trong `extra_files`.

## Sau khi đổi code `api.py` lần đầu

Vẫn cần **restart một lần** `start_api.bat` để process nhận logic watch mới.
