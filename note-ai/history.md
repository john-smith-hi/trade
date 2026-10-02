# History journal (`history/`)

Trang **phân tích CSV lệnh đã đóng** — khác `mt5/history/` (bảng `history_mt5.txt`).

| URL | File | Việc |
|-----|------|------|
| `/history/` | `history/index.html` + `app.js` + `analyze.js` | Import CSV/JSON, lọc, thống kê trên trình duyệt |

Lên WAMP: `python copy_www.py history` (xóa folder đích rồi copy cả cây). Không cần API. Dữ liệu import nằm IndexedDB trình duyệt, không ghi vào folder web.

CSS/JS: `ver.php` + `?v=filemtime`. Thêm file JS/CSS mới thì ghi vào list trong `history/ver.php`. Theme key `mt5-theme`. Favicon: `history/favicon.ico` (tab title `History`). CSP `img-src 'self'` để trình duyệt tải icon (trước đây `'none'`).

Bộ lọc (symbol, side, lý do đóng, file, đóng từ/đến) + ô tìm lệnh lưu `localStorage` key `history-journal-filters` — còn sau khi đóng tab. Phiên cũ dùng `sessionStorage` thì lần lưu sau chuyển sang local. Nút **Xóa lọc** ghi đè bản lưu.

## Ô ngày

Bốn ô: **Từ / Đến** (link orders) và **Đóng từ / Đóng đến** (bộ lọc).

- Ô hiện là `type="text"`, mask `dd/mm/yyyy` (không đổi sang `type="date"` — Chrome hiện `yyyy-mm-dd`).
- Bên cạnh mỗi ô có nút lịch. `input type="date"` phủ lên nút (indicator WebKit full ô) để bấm chuột mở lịch gốc; bàn phím vẫn dùng nút + `showPicker()`. Ngày chọn ghi lại `dd/mm/yyyy`.
- `input type="date"` ẩn **không** `display:none` (showPicker sẽ lỗi). Đặt absolute trong `.cal-hit`, `opacity: 0`.
- CSP `script-src 'self'` — không dùng thư viện lịch ngoài.

`parseDisplayDate` nhận cả `dd/mm/yyyy` và ISO `yyyy-mm-dd`.
