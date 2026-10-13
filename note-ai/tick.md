# Tick Bid/Ask (`tick/`)

Trang **xem giá mua/bán theo tick CSV** — khác `history/` (CSV lệnh đã đóng) và `mt5/history/` (`history_mt5.txt`).

| URL | File | Việc |
|-----|------|------|
| `/tick/` | `tick/index.html` + `app.js` | Nạp CSV, tìm theo giờ Việt Nam, bảng + đồ thị Bid/Ask |

Lên WAMP: `python copy_www.py tick` (xóa folder đích rồi copy UI). **Không** copy file `.csv`. Dữ liệu nằm `data/GOLD/tick/` trên máy chạy `api.py` (gitignore `data/`).

Cần API (`start_server.bat`) + `proxy.php` → `127.0.0.1:5001`. Timeout proxy 180s vì file tháng có hàng triệu dòng.

CSS/JS: `ver.php` + `?v=filemtime`. Thêm file JS/CSS mới thì ghi vào list trong `tick/ver.php`. Theme key `mt5-theme`. Favicon: `tick/favicon.ico`. CSP `connect-src 'self'` (chỉ proxy cùng origin).

## CSV

```
"Exness","Symbol","Timestamp","Bid","Ask"
"exness","XAUUSDm","2026-09-01 00:00:00.065Z",4452.22,4452.48
```

Timestamp trong file là **UTC**. UI/API dùng **giờ Việt Nam UTC+7** (không DST). Bid = giá bán, Ask = giá mua.

Upload qua web tối đa 64 MB; dán tối đa 8 MB. File tháng (trăm MB) copy thẳng vào `data/GOLD/tick/` rồi Tải lại danh sách.

## Tìm

Ô ngày giống `history/`: `dd/mm/yyyy` + nút lịch. Thêm giờ `HH:MM:SS`. Bấm **Tìm** (không tự quét cả file khi gõ). Bộ lọc lưu `localStorage` key `tick-filters`.

Kết quả: KPI, canvas Bid/Ask (không thư viện ngoài), bảng phân trang 100 dòng. `GET /api/tick/query` binary-search file đã sort rồi đọc tuần tự trong khoảng.

## API (không lấy lock MT5)

| Method | Path | Việc |
|--------|------|------|
| GET | `/api/tick/files` | List CSV + `dir` |
| POST | `/api/tick/upload` | Multipart `file` hoặc JSON `{filename, csv}` |
| DELETE | `/api/tick/files/<name>` | Xóa 1 file trong `data/GOLD/tick/` |
| GET | `/api/tick/query?from=&to=` | `from`/`to` giờ VN `YYYY-MM-DDTHH:MM:SS`; optional `symbol`, `file`, `offset`, `limit` |

Logic: `tick_data.py`.
