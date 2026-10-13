# Tick Bid/Ask (`tick/`)

Trang **xem giá mua/bán theo tick CSV** — khác `history/` (CSV lệnh đã đóng) và `mt5/history/` (`history_mt5.txt`).

| URL | File | Việc |
|-----|------|------|
| `/tick/` | `tick/index.html` + `app.js` | Nạp CSV, tìm theo giờ Việt Nam, bảng + đồ thị Bid/Ask |

Lên WAMP: `python copy_www.py tick` (xóa folder đích rồi copy UI). **Không** copy file `.csv`.

Nạp/dán CSV → `localStorage` key `tick-imports` (trình duyệt, tối đa ~4 MB/file). Không ghi server. File tháng (trăm MB) vẫn đọc từ `data/GOLD/tick/` qua API khi bấm Tìm.

Tìm file trình duyệt không cần API. Tìm file tháng trên đĩa cần `start_server.bat` + `proxy.php`. Timeout proxy 180s.

CSS/JS: `ver.php` + `?v=filemtime`. Thêm file JS/CSS mới thì ghi vào list trong `tick/ver.php`. Theme key `mt5-theme`. Favicon: `tick/favicon.ico`. CSP `connect-src 'self'` (chỉ proxy cùng origin).

## CSV

```
"Exness","Symbol","Timestamp","Bid","Ask"
"exness","XAUUSDm","2026-09-01 00:00:00.065Z",4452.22,4452.48
```

Timestamp trong file là **UTC**. UI/API dùng **giờ Việt Nam UTC+7** (không DST). Bid = giá bán, Ask = giá mua.

Nạp/dán tối đa ~4 MB (hạn localStorage). File tháng copy vào `data/GOLD/tick/` (không nạp qua UI).

## Tìm

Ô ngày giống `history/`: `dd/mm/yyyy` + nút lịch. Thêm giờ `HH:MM:SS`. Bấm **Tìm** (không tự quét cả file khi gõ). Bộ lọc lưu `localStorage` key `tick-filters`.

Kết quả: KPI, canvas Bid/Ask (không thư viện ngoài), bảng phân trang 100 dòng. File localStorage lọc trên trình duyệt. File đĩa: `GET /api/tick/query` (binary-search).

## API (không lấy lock MT5) — chỉ file trên đĩa

| Method | Path | Việc |
|--------|------|------|
| GET | `/api/tick/files` | List CSV trong `data/GOLD/tick/` |
| DELETE | `/api/tick/files/<name>` | Xóa 1 file trên đĩa |
| GET | `/api/tick/query?from=&to=` | Tick giờ VN trên đĩa + chart |

`POST /api/tick/upload` còn đó nhưng UI không dùng (nạp đi localStorage). Logic đĩa: `tick_data.py`.
