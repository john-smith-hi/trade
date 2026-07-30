# note-ai — ghi chú cho phiên AI tiếp theo

Thư mục này tóm tắt kiến trúc và quy ước đã thống nhất.
Đọc theo thứ tự khi sửa trade / MT5 API / web UI:

1. `architecture.md` — luồng chạy, file quan trọng, endpoint API
2. `web-ui.md` — trang web WAMP, cache `?v=`, performance, UX
3. `accounts-xml.md` — `accounts.xml` + `paths.xml`, API CRUD
4. `auto-reload.md` — .py / .xml tự làm mới khi sửa
5. `xauusd-max-loss.md` — giới hạn lỗ XAUUSD + copy trade
6. `gotchas.md` — lỗi đã gặp, việc không được làm

**Không** ghi mật khẩu / login thật vào đây. `xml/accounts.xml` nằm trong `.gitignore`.

Web UI nằm ngoài repo: `D:\wamp64\www\mt5\` (không git cùng `trade`).
