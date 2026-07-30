# Gotchas / lỗi đã gặp

## 1. `NameError: DEFAULT_XAUUSD_MAX_LOSS is not defined`

Xảy ra khi xóa hằng mặc định nhưng `load_accounts` vẫn còn nhánh cũ.
Hiện tại: trống → `None`. Nếu gặp lại: kiểm tra còn sót tên `DEFAULT_XAUUSD_MAX_LOSS` và restart API.

## 2. Sửa `accounts.xml` mà web vẫn hiện config cũ

- UI cache lúc load trang — cần focus tab / bấm Preview / nút Tải lại danh sách.
- Process API cũ chưa có watch XML — restart `start_api.bat` một lần sau khi pull/sửa `api.py`.

## 3. Không commit secrets

- `xml/accounts.xml` có password thật → gitignore.
- Chỉ commit `xml/accounts.example.xml`.
- Không paste login/password vào note-ai hoặc chat commit message.

## 4. `--no-ask` / `no_ask`

Không có → chỉ xem trước, **không** gửi lệnh thật (kể cả copy).
Web: nút Confirm mới gửi `no_ask: true`.

## 5. Symbol suffix

Exness cần `suffix=m`. FTMO để trống. Sai suffix → không chọn được symbol / giá sai.

## 6. Lock API

Mọi thao tác MT5 đi qua một lock trong `api.py`. Đừng bỏ lock khi thêm endpoint mới.

## 7. Web UI ngoài repo

Sửa `app.js` / `proxy.php` tại `D:\wamp64\www\mt5\` — **không** nằm trong git `trade`. Nhớ đồng bộ tay nếu làm việc máy khác.
