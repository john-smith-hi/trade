# Web UI (`D:\wamp64\www\mt5\`)

UI **không** nằm trong git repo `trade`. Sửa trực tiếp trên WAMP; đồng bộ tay nếu đổi máy.

## Trang

| URL | Thư mục | Việc |
|-----|---------|------|
| `http://localhost/mt5/` | `index.html` + `app.js` | Ra lệnh (status/open/close-all/modify-all) |
| `http://localhost/mt5/account/` | `account/` | Thêm + sửa account (không xóa; không sửa login/password/server) |
| `http://localhost/mt5/path/` | `path/` | Thêm + sửa path terminal (`name` → `exe`) |
| `http://localhost/mt5/history/` | `history/` | Bảng lịch sử từ `history_mt5.txt` |

Menu chung: **Ra lệnh | Accounts | Path | Lịch sử**.

Shared: `style.css`, `common.js`, `proxy.php`, `ver.php`.

## Cache CSS/JS — luôn `?v=` (không dùng `?t=` / không tắt query)

**Đã chốt:** không bao giờ load URL trần (`common.js`), không gắn `Date.now()` mỗi F5, không có trang “Cài đặt chung” bật/tắt.

Cơ chế hiện tại:

1. Mỗi trang load sync `ver.php` (hoặc `../ver.php`) — header `Cache-Control: no-store`.
2. `ver.php` set `window.MT5_ASSET_VER` = **max `filemtime`** của `style.css`, `common.js`, `app.js`, `account/account.js`, `path/path.js`, `history/history.js`.
3. CSS/JS load bằng `document.write(...?v=' + MT5_ASSET_VER)`.

Hệ quả:

- Sửa file → mtime đổi → `?v=` đổi → trình duyệt tải bản mới.
- Không sửa file → cùng `?v=` → dùng cache trình duyệt (nhanh).
- Tránh lỗi cũ: tắt `?t=` rồi load URL trần → kẹt bản cache rất cũ.

Khi thêm file JS/CSS mới: **thêm vào list trong `ver.php`**.

## `common.js` — API + UX tải

- Proxy: set `window.MT5_PROXY` trước khi load (`"proxy.php"` hoặc `"../proxy.php"`).
- GET cache ~15s + dedupe in-flight.
- Busy bar; overlay chỉ khi `withBusy(..., { block: true })`.
- Fetch abort timeout ~12s; busy watchdog ~20s → `clearBusyHard` nếu treo.
- `markApiError` luôn hard-clear busy (tránh UI đứng).
- Focus / visibility refresh throttle ~20s.
- Theme sáng/tối: `localStorage` key `mt5-theme`.

## Hành vi từng trang (đã tối ưu)

- **Accounts**: `Promise.all` paths + accounts; load song song.
- **Trade (`app.js`)**:
  - Layout tham số: Symbol|Side → Lot (riêng dòng) → TP|SL (cùng dòng) → Comment (riêng) → Copy.
  - Chọn **open** → `GET /api/quote` điền TP/SL = giá entry (ask/bid theo side); đổi symbol/side/account thì lấy lại.
  - Chọn **modify-all** / **close-all** → `GET /api/positions` kiểm tra lệnh mở.
    - **Không có lệnh mở** → báo vô nghĩa, khóa nút Xem trước / Xác nhận.
    - modify-all có lệnh → điền TP/SL; close-all có lệnh → hiện tóm tắt số lệnh sẽ đóng.
  - Lần load đầu không block overlay; action timeout ~60s.
- **History**: bảng cột time / account / symbol / lot / status / ticket / retcode / comment / detail.

## Validation TP/SL (backend)

- **open**: so với giá vào (entry) — `validate_tp_sl`.
- **modify-all**: **không** so với giá hiện tại / giá mở — chỉ `validate_tp_sl_modify`:
  - BUY: cần `SL < TP` (khi cả hai có)
  - SELL: cần `TP < SL`
  - Giá > 0
- `xauusd_max_loss` vẫn ước tính theo `price_open` của từng lệnh khi modify.

## Quy ước load script

Dùng `document.write` parse-time (sau `ver.php`). **Không** dùng chuỗi `createElement` + `onload` — nếu script lỗi thì `onload` không chạy → trang đứng im.

## Lịch sử thử nghiệm cache (đừng lặp)

1. `?t=Date.now()` mỗi lần — luôn fresh nhưng không cache.
2. `sessionStorage` giữ một `t` / session — vẫn dễ lệch khi sửa file.
3. Toggle localStorage bật/tắt `?t=` — **tắt về URL trần = lấy bản cache cũ nhất** → đã bỏ.
4. Hiện tại: chỉ `?v=filemtime` qua `ver.php`.
