# Setup UI (`setup/`)

UI checklist nằm trong repo `trade/setup/`. Lên WAMP bằng `python copy_www.py setup` (xóa folder đích rồi copy cả cây, gồm `fibo/` và `timer/`).

Menu: **Setup | Fibo | Timer**.

| URL | File | Việc |
|-----|------|------|
| `/setup/` | `index.html` + `app.js` | Checklist tuần, chấm điểm setup |
| `/setup/fibo/` | `fibo/index.html` + `fibo/fibo.js` | Fibonacci hồi từ đỉnh/đáy |
| `/setup/timer/` | `timer/` | Báo thức vùng giá |

CSS/JS: `ver.php` + `?v=filemtime`. Thêm file JS mới thì ghi vào list trong `setup/ver.php`. Favicon: `setup/favicon.ico`; Fibo/Timer trỏ `../favicon.ico`.

## Fibo

Tính bảng/vùng trên trình duyệt (`setup/fibo/calc.js`). **Đỉnh/đáy + side** lưu server qua `GET/PUT /api/setup/fibo` → `xml/fibo.xml` (gitignore; mẫu `fibo.example.xml`). Tự lưu ~400ms sau khi gõ; **không** ghi XML khi chỉ mở trang. PUT xong **không** ghi đè ô đang nhập. Lần đầu nếu server trống mà còn `localStorage` key `setup-fibo` thì đẩy lên server rồi xóa local.

Cần `start_server.bat` + `proxy.php`. Theme key `mt5-theme`. Load `common.js` (có poll Timer nền — giống trang Timer).

Công thức, `range = đỉnh − đáy`:

- **SELL** (sóng giảm): `giá = đáy + range × mức`. 100% = đỉnh, 0% = đáy.
- **BUY** (sóng tăng): `giá = đỉnh − range × mức`. 100% = đáy, 0% = đỉnh.

Mức: 0, 0.236, 0.382, 0.500, 0.618, 0.786, 1. Làm tròn half-up sau khi ổn định float (`toFixed` thêm 6 số) — 50% của 4300 / 4110.87 ra **4205.44**, khớp bảng mẫu.

Ba vùng (SELL):

- Premium 50%–78.6%: ưu tiên Sell
- Scalp 23.6%–38.2%
- Dưới 23.6%: hạn chế Sell đuổi; chỉ Sell khi đóng nến đục thủng đáy

BUY đảo vai: Discount 50%–78.6% là vùng ưu tiên Buy; trên 23.6% (sát đỉnh) là hạn chế Buy đuổi.
