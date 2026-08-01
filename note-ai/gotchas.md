# Gotchas / lỗi đã gặp

## 1. `NameError: DEFAULT_XAUUSD_MAX_LOSS is not defined`

Xảy ra khi xóa hằng mặc định nhưng `load_accounts` vẫn còn nhánh cũ / process API cũ.
Hiện tại: trống → `None`. Nếu gặp lại: grep còn sót tên hằng và **restart** `start_api.bat`.

## 2. Sửa `accounts.xml` / `paths.xml` mà web vẫn hiện config cũ

- Soft-reload + Flask reloader đã có — xem `auto-reload.md`.
- UI còn GET cache ~15s → bấm **Tải lại danh sách** hoặc đợi / focus tab.
- Process API rất cũ (trước khi có watch XML) → restart `start_api.bat` một lần.

## 3. Không commit secrets

- `xml/accounts.xml` có password thật → gitignore.
- Chỉ commit `*.example.xml`.
- Không paste login/password vào note-ai hoặc commit message.

## 4. `--no-ask` / `no_ask`

Không có → chỉ xem trước, **không** gửi lệnh thật (kể cả copy).
Web: nút **Xác nhận gửi lệnh thật** mới gửi `no_ask: true`.

## 5. Symbol suffix

Exness cần `suffix=m`. FTMO để trống. Sai suffix → không chọn được symbol / giá sai.

## 6. Lock API

Mọi thao tác MT5 đi qua một lock trong `api.py`. Đừng bỏ lock khi thêm endpoint mới.

## 7. Web UI ngoài repo

Sửa file tại `D:\wamp64\www\mt5\` — **không** nằm trong git `trade`. Nhớ đồng bộ tay nếu làm việc máy khác.

## 8. `<path>` trong accounts là tên, không phải đường dẫn

Ghi full `C:\...\terminal64.exe` vào accounts → resolve lỗi.
Đúng: `paths.xml` giữ exe; accounts chỉ ghi `exness` / `ftmo`.

## 9. Không sửa login/password/server trên UI edit

`PUT /api/accounts/<name>` cố ý giữ nguyên credentials. Muốn đổi login → phải sửa XML tay (hoặc xóa+thêm ngoài UI — UI không có xóa).

## 10. Cache CSS/JS — đừng quay lại URL trần hoặc `?t=` mỗi F5

- URL trần sau khi từng dùng `?t=` → trình duyệt lấy bản cache **cũ nhất**.
- `?t=Date.now()` mỗi lần → không tận dụng cache, dễ làm rối debug.
- Đúng: `ver.php` + `?v=filemtime` — xem `web-ui.md`.
- Thêm file JS/CSS mới → cập nhật list trong `ver.php`.

## 11. Trang web “đứng” / overlay busy kẹt

Nguyên nhân đã gặp:

- Load script bằng `createElement` + `onload` (chain gãy nếu lỗi).
- Busy count / overlay không clear khi API lỗi / timeout.

Hiện tại: `document.write` + busy watchdog ~20s + `markApiError` → `clearBusyHard`.
Nếu vẫn đứng: kiểm tra `start_api.bat` còn chạy; DevTools Network xem `proxy.php` / `ver.php`.

## 12. History API

`GET /api/history` trả `{ lines, rows }`. UI dùng `rows` (đã parse). Limit max 500.

## 13. Quote / positions cho form ra lệnh

- `GET /api/quote` — cần account + MT5 connect; timeout UI ~30s.
- `GET /api/positions` — snapshot lệnh mở để điền modify-all.
- Modify-all **không** validate TP/SL so với giá thị trường (chỉ cặp theo side) — xem `web-ui.md`.

## 14. Copy — đã thử prewarm, đã bỏ

Benchmark BTCUSD: lệch **cùng Exness ~$1**, **Exness↔FTMO ~$25–30** (sàn broker). Prewarm multiprocess chỉ cắt wall ~1s trên khác terminal, **gần như không cải thiện Δfill** — với day trade không đáng phức tạp.

Hiện tại: copy **tuần tự** sau `mt5.shutdown()` rồi connect account tiếp. Không cần `sleep(0.5)` giữa hai lần (đã thử bỏ — reconnect vẫn ổn). Không còn `copy_worker.py` / suite prewarm.
