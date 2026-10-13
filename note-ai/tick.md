# Dữ liệu tick CSV (Exness XAUUSDm)

**Không còn app web `/tick/` hay API `/api/tick/*` trong repo.** Chỉ còn file CSV trên đĩa.

## Vị trí file

| Path | Ghi chú |
|------|---------|
| `data/GOLD/tick/*.csv` | Nguồn chính (đã `.gitignore` qua `data/`) |
| `<www>/tick/*.csv` | Bản copy cũ trên WAMP (nếu còn) — có thể xóa tay |

Tên mẫu: `Exness_XAUUSDm_2026_06.csv` … `_09.csv` (theo tháng).

Quy mô: **~6–8 triệu dòng / file**, **~400–500 MB / file**. **Không** mở/read toàn file trong editor hay `Read` tool của agent.

## Định dạng CSV

Header (dòng 1):

```text
"Exness","Symbol","Timestamp","Bid","Ask"
```

Dòng dữ liệu (UTC, đuôi `Z`, mili giây tùy dòng):

```text
"exness","XAUUSDm","2026-06-01 00:00:00.076Z",4539.717,4539.997
```

- **Timestamp**: UTC (`Z`). Hiển thị giờ Việt Nam = UTC+7, **không DST**.
- **Bid** = giá bán, **Ask** = giá mua.
- File **đã sort** theo thời gian tăng dần (có thể binary-search theo khoảng thời gian).

## Cách đọc an toàn (agent / script)

### Được làm

1. **`path.stat().st_size`** — biết dung lượng không đọc nội dung.
2. **Dòng 1** — header (`readline` hoặc `head -1`).
3. **Vài dòng đầu** sau header — ví dụ `readline` × 5 hoặc `Get-Content -TotalCount 6`.
4. **Cuối file** — `seek(size - 16384)`, đọc chunk, lấy dòng cuối không rỗng (khoảng thời gian kết thúc file).
5. **Khoảng thời gian** — parse UTC từ dòng đầu/cuối → đổi sang VN (+7h).
6. **Tra cứu theo giờ** — mở file **binary**, `seek` + đọc **tuần tự** hoặc **binary search** trên offset (file sort). Chỉ parse dòng trong `[from, to]`.
7. **`grep` / `rg`** với pattern hẹp (ngày cụ thể) nếu cần vài dòng mẫu — **không** grep cả tháng không giới hạn.

### Không làm

- `Read` tool / `read()` / `readlines()` / `pandas.read_csv()` **cả file**.
- Load vào **localStorage**, **IndexedDB**, hoặc **mảng JS** hàng triệu phần tử.
- Commit CSV vào git.

## Parse timestamp UTC (Python gợi ý)

```python
from datetime import datetime, timezone, timedelta

UTC = timezone.utc
VN = timezone(timedelta(hours=7))

def parse_utc_z(s: str) -> datetime:
    s = s.strip().strip('"').rstrip("Zz").replace("T", " ")
    # "2026-06-01 00:00:00.076" -> datetime UTC (cắt micro tùy chuỗi)
    ...
```

Đổi sang VN: `dt.astimezone(VN)`. API cũ dùng `YYYY-MM-DDTHH:MM:SS` **giờ VN** khi filter.

## Tra cứu theo khoảng giờ (ý tưởng thuật toán)

1. Đọc header → vị trí byte `data_pos` sau dòng 1.
2. Đổi `from_vn`, `to_vn` → `start_utc`, `end_utc`.
3. Nếu file sorted: binary search offset đầu tiên có `timestamp >= start_utc`.
4. Từ offset đó đọc từng dòng đến khi `timestamp > end_utc` thì dừng.
5. Bảng/chart: giới hạn số dòng (vd ≤500 bảng, ≤1200 điểm đồ thị — gộp bucket theo thời gian).

## Lệnh nhanh (PowerShell / shell)

```powershell
# Header + 3 dòng
Get-Content "data\GOLD\tick\Exness_XAUUSDm_2026_09.csv" -TotalCount 4

# Dung lượng
(Get-Item "data\GOLD\tick\Exness_XAUUSDm_2026_09.csv").Length
```

```bash
head -n 4 data/GOLD/tick/Exness_XAUUSDm_2026_09.csv
tail -c 2000 data/GOLD/tick/Exness_XAUUSDm_2026_09.csv | tail -n 3
```

## Liên quan repo khác

- `history/` — CSV **lệnh đã đóng**, nhỏ hơn, phân tích trên browser.
- `mt5/history/` — `history_mt5.txt` log gửi lệnh.
- `GET /api/quote` — **tick live** MT5 (bid/ask), không phải file CSV này.

Nếu làm lại UI/tool tick: đọc trực tiếp `data/GOLD/tick/`, query phía server (Python), không đẩy CSV qua trình duyệt.
