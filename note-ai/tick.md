# Tick Bid/Ask (`tick/`)

Trang **xem giá mua/bán theo tick CSV** — khác `history/` (CSV lệnh đã đóng) và `mt5/history/` (`history_mt5.txt`).

| URL | File | Việc |
|-----|------|------|
| `/tick/` | `tick/index.html` + `app.js` | Nạp CSV, tìm theo giờ Việt Nam, bảng + đồ thị Bid/Ask |

Lên WAMP: `python copy_www.py tick`. Folder đích xóa code cũ **nhưng giữ `*.csv`**. Dữ liệu nằm ngay `www/tick` (cùng chỗ trang). File tháng cũ trong `data/GOLD/tick/` vẫn được API đọc nếu chưa copy sang www.

Nạp/dán nhỏ: `tick/save.php` ghi vào folder trang. File > 64 MB: không upload — nếu trùng tên với file đã có trên đĩa thì dùng file đó; không thì copy tay vào `www/tick`.

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
| POST | `/api/tick/upload` | Lưu CSV vào `www/tick` (UI ưu tiên `save.php`) |
| DELETE | `/api/tick/files/<name>` | Xóa file trong `www/tick` (không xóa bản nguồn `data/GOLD/tick/`) |
| GET | `/api/tick/query?from=&to=` | Tick giờ VN + chart |

Logic: `tick_data.py`.
