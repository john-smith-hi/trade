# `xauusd_max_loss` — giới hạn lỗ XAUUSD

## Quy tắc (đã chốt)

| Trường hợp | Hành vi |
|------------|---------|
| Tag trống / không cấu hình | **Không giới hạn** (`None`) — không chặn lệnh |
| Có số trong XML | Dùng đúng số đó |
| Copy + đích trống + gốc có số | `xauusd_max_loss_gốc × multi` của đích |
| Copy + đích có số riêng | Dùng số của đích |
| Copy + gốc và đích đều trống | Không giới hạn |

**Không còn** mặc định cứng `40` (`DEFAULT_XAUUSD_MAX_LOSS` đã bỏ).

## Code liên quan (`mt5.py`)

- `load_accounts()` — parse số hoặc `None`
- `get_xauusd_max_loss(account=None)` — `None` = skip
- `resolve_copy_xauusd_max_loss(copy, primary)` — kế thừa gốc × multi
- `validate_xauusd_max_loss(...)` — chỉ raise nếu có max_loss và ước tính lỗ vượt
- `run_action_on_account` set `_ACTIVE_XAUUSD_MAX_LOSS` từ dict account đang chạy
- Trong `execute_request` (vòng copy): gán `copy_account["xauusd_max_loss"]` = giá trị đã resolve rồi mới chạy

## Validation áp dụng khi

- `open` (có SL)
- `modify-all` (đổi SL) trên symbol XAUUSD / XAUUSDm

Ước tính lỗ dùng `estimate_tp_sl_pnl` + `resolve_contract_size`.
