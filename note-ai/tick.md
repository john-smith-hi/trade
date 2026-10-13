# Tick Bid/Ask (`tick/`)

Trang **xem giá mua/bán theo tick CSV** — khác `history/` (CSV lệnh đã đóng) và `mt5/history/` (`history_mt5.txt`).

| URL | File | Việc |
|-----|------|------|
| `/tick/` | `tick/index.html` + `app.js` | Nạp CSV, tìm theo giờ Việt Nam, bảng + đồ thị Bid/Ask |

Lên WAMP: `python copy_www.py tick`. Folder đích xóa code cũ **nhưng giữ `*.csv`**. Dữ liệu nằm ngay `www/tick` (cùng chỗ trang). File tháng cũ trong `data/GOLD/tick/` vẫn được API đọc nếu chưa copy sang www.

Nạp: `tick/save.php` ghi vào folder trang. File lớn cắt **1 MB/khối** rồi ghép `.part` → `.csv` (không phụ thuộc giới hạn 64 MB). Nếu API chạy và file đã có trong `www/tick` hoặc `data/GOLD/tick/` (cùng tên + dung lượng) thì `POST /api/tick/adopt` — không gửi lại nội dung. Dán CSV tối đa 8 MB.

Tìm cần API (`start_server.bat`) + `proxy.php`. Timeout proxy 180s.

CSS/JS: `ver.php` + `?v=filemtime`. Theme `mt5-theme`. CSP `connect-src 'self'`.

## CSV

```
"Exness","Symbol","Timestamp","Bid","Ask"
"exness","XAUUSDm","2026-09-01 00:00:00.065Z",4452.22,4452.48
```

Timestamp **UTC**. UI/API **giờ Việt Nam UTC+7**. Bid = giá bán, Ask = giá mua.

## Tìm

Ô ngày giống `history/`: `dd/mm/yyyy` + nút lịch. Giờ `HH:MM:SS`. Bấm **Tìm**. Bộ lọc `localStorage` key `tick-filters` (chỉ bộ lọc, không phải CSV).

`GET /api/tick/query` binary-search file đã sort.

## API (không lấy lock MT5)

| Method | Path | Việc |
|--------|------|------|
| GET | `/api/tick/files` | List CSV trong `www/tick` (+ `data/GOLD/tick/` nếu có) |
| POST | `/api/tick/adopt` | Dùng file đã có trên đĩa (`filename` + `size`) |
| POST | `/api/tick/upload` | Lưu CSV vào `www/tick` (UI dùng `save.php` từng khối) |
| DELETE | `/api/tick/files/<name>` | Xóa file trong `www/tick` (không xóa bản nguồn `data/GOLD/tick/`) |
| GET | `/api/tick/query?from=&to=` | Tick giờ VN + chart |

Logic: `tick_data.py`.
