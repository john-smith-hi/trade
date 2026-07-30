# note-ai — ghi chú cho phiên AI tiếp theo

Thư mục này tóm tắt kiến trúc và quy ước đã thống nhất trong các phiên làm việc gần đây.
Đọc theo thứ tự khi sửa trade/MT5 API:

1. `architecture.md` — luồng chạy, file quan trọng, web UI
2. `accounts-xml.md` — cấu hình `xml/accounts.xml`
3. `auto-reload.md` — .py / .xml tự làm mới khi sửa
4. `xauusd-max-loss.md` — logic giới hạn lỗ XAUUSD + copy trade
5. `gotchas.md` — lỗi đã gặp, việc không được làm

**Không** ghi mật khẩu / login thật vào đây. `xml/accounts.xml` nằm trong `.gitignore`.
