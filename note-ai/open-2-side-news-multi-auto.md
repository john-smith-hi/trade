================================================================================
BẢN THIẾT KẾ THUẬT TOÁN HEDGING BOT TỐC ĐỘ CAO (XAUUSD - EXNESS MT5) - PHIÊN BẢN SỬA
================================================================================

QUY TẮC GỐC (cơ sở của toàn bộ thuật toán)
1. Mở BUY và SELL cùng khối lượng V (mỗi phía V lot) nhờ cơ chế bù trừ ký quỹ.
2. Giá chạm SL của một đầu (ví dụ SELL cháy ở 4215): lệnh còn lại (BUY) đang lời
   đúng bằng phần SELL vừa lỗ, nên lúc đó chưa mất gì ngoài spread.
3. Lệnh còn lại được dời SL về (mức SL của đầu đã cháy - BUFFER) - dời trong logic ký quỹ chứ không dời thực tế
   Ví dụ: 4215 - 8 = 4207. Nếu giá quay đầu chạm 4207 thì lệnh còn lại không còn
   đủ lời để gánh phần đã lỗ, và tài khoản mất đúng MAX_RISK.

--------------------------------------------------------------------------------
I. BIẾN ĐẦU VÀO (INPUT PARAMETERS)
1. MAX_RISK       : Số tiền tối đa cho phép mất (USD)              (ví dụ: 375)
2. SL_PIPS        : Khoảng cách Stop Loss ban đầu, tính bằng giá   (ví dụ: 15.0)
3. BUFFER_PIPS    : Khoảng đệm sau khi một đầu cháy SL, tính bằng giá (ví dụ: 8.0)
4. LEVERAGE       : Đòn bẩy tài khoản                              (ví dụ: 200)
5. MAX_EXEC_TIME  : Thời gian bắn lệnh tối đa (ms)                 (ví dụ: 300)

Thông số lấy từ broker (không nhập tay):
- CS (contract size) = 100 (symbol_info().trade_contract_size)
- volume_step, volume_min, volume_max (symbol_info)
- SO = mức Stop Out dạng số thập phân (account_info().margin_so_so / 100;
  0% -> 0, 50% -> 0.5)

--------------------------------------------------------------------------------
II. BỘ CÔNG THỨC TOÁN HỌC

1. Vì sao lot tính theo BUFFER + SPREAD mà KHÔNG phải SL + SPREAD
- Lúc hai đầu cùng chạy: lời/lỗ của BUY và SELL triệt tiêu nhau.
- Khi một đầu cháy SL: khoản lỗ SL_PIPS đó được lệnh còn lại bù lại bằng đúng
  khoản lời đang có. Vì vậy SL_PIPS KHÔNG phải là mức mất cuối cùng.
- Mức mất cuối cùng chỉ gồm: BUFFER_PIPS (phần giá quay đầu sau khi đầu kia cháy)
  cộng Spread. SL_PIPS chỉ quyết định giá nào kích hoạt kịch bản.

Kiểm chứng (P_ref = giá Ask lúc vào = 4200, Spread = 1, SELL vào ở 4199):
- Kịch bản A (giá lên): SELL SL ở 4215, lỗ 16 điểm. BUY dời SL về 4207, lời 7 điểm.
  Mất ròng = 16 - 7 = 9 điểm = BUFFER (8) + Spread (1).
- Kịch bản B (giá xuống): BUY SL ở 4185, lỗ 15 điểm. SELL dời SL về 4185 + 8 = 4193,
  lời 4199 - 4193 = 6 điểm. Mất ròng = 15 - 6 = 9 điểm. Cùng kết quả.

2. Khối lượng mỗi phía (V là lot của BUY, và cũng là lot của SELL)
- Loss_per_lot = CS * (BUFFER_PIPS + Spread)
- V_risk = MAX_RISK / Loss_per_lot
- Kiểm tra Stop Out cho lệnh đứng một mình sau khi một đầu cháy:
  Lúc xấu nhất, equity còn (Equity - V*CS*(BUFFER+Spread)), và margin của lệnh
  đứng một mình là V*CS*Price/LEVERAGE. Yêu cầu: equity đó >= margin * SO, suy ra
  V_so = Equity / [ CS * (Price*SO/LEVERAGE + BUFFER_PIPS + Spread) ]
  (SO = 0 thì V_so = Equity / (CS*(BUFFER+Spread)), trùng V_risk khi Equity = MAX_RISK)
- V = làm tròn xuống theo volume_step của min(V_risk, V_so)
- Nếu V < volume_min thì hủy tiến trình.
- KHÔNG chia đôi V. Mỗi phía đủ V; tổng cộng hai phía là 2V.

3. Số cặp lệnh và cách chia khối lượng (N_pairs)
- T_benchmark: thời gian bắn 1 cặp mẫu (BUY + SELL), đo bằng perf_counter() (ms).
- N_pairs = phần nguyên của [ MAX_EXEC_TIME / T_benchmark ], tối thiểu 1.
- Tính theo đơn vị bước lot: units = V / volume_step. Cặp benchmark chiếm 1 unit và
  được giữ lại, tính vào V (không đóng đi, để khỏi tốn thêm spread).
  units_rest = units - 1
  N_pairs = min(N_pairs, units_rest)
  base = units_rest // N_pairs ; rem = units_rest % N_pairs
  Cặp thứ i (i = 0..N_pairs-1) có khối lượng = (base + 1 nếu i < rem, ngược lại base)
  * volume_step. Tổng các cặp cộng benchmark đúng bằng V, không mất lot do làm tròn.
- Margin Guardrail: chunk lớn nhất phải thỏa
  chunk_max * CS * Price / LEVERAGE <= Free Margin
  (vì giữa lúc BUY khớp và SELL khớp, BUY chưa được bù trừ). Nếu không đạt thì hủy
  hoặc giảm V.

4. Giả định về ký quỹ bù trừ (BẮT BUỘC kiểm tra trước khi chạy thật)
- Thuật toán giả định cặp BUY/SELL cùng khối lượng có margin hedge = 0 (hoặc rất nhỏ).
  Kiểm tra bằng mt5.order_calc_margin và symbol_info().margin_hedged. Nếu broker
  tính margin hedge khác, V_so và Margin Guardrail phải tính lại.
- Sau khi một đầu cháy, lệnh còn lại phải gánh margin đầy đủ (ví dụ 0.41 lot vàng
  ở 4200, đòn bẩy 200 = 861$). Đây là lý do cần kiểm tra Stop Out ở mục 2.

--------------------------------------------------------------------------------
III. QUY TRÌNH THỰC THI (6 BƯỚC)

BƯỚC 1: Lấy giá và kiểm tra an toàn ban đầu
1. mt5.initialize().
2. Lấy tick real-time: Ask, Bid. Spread = Ask - Bid.
3. Lấy Equity, Free Margin. Nếu Equity < MAX_RISK hoặc Free Margin < MAX_RISK thì hủy.
4. Lấy SO, volume_step/min/max, margin hedge. Tính V (mục II.2).

BƯỚC 2: Đo tốc độ (Benchmark Latency) bằng cặp lệnh thật 0.01 lot
1. T_start = perf_counter() -> BUY 0.01 -> SELL 0.01 -> T_end = perf_counter().
2. T_benchmark = (T_end - T_start) * 1000 (ms).
3. Cặp này được giữ lại, là một phần của V. Kiểm tra retcode của cả hai lệnh,
   nếu một lệnh thất bại thì xử lý theo quy tắc ở Bước 4.
4. Gán magic number cho mọi lệnh của bot để nhận diện.

BƯỚC 3: Tính quy mô động
1. Tính N_pairs và danh sách khối lượng từng cặp (mục II.3).
2. Chạy Margin Guardrail cho chunk lớn nhất.

BƯỚC 4: Bắn lệnh XEN KẼ (Interleaved Execution Engine - BẮT BUỘC)
- Quy tắc: không bao giờ gửi toàn bộ BUY rồi mới gửi SELL. Mỗi cặp là 1 BUY rồi
  1 SELL cùng khối lượng, để SELL giải phóng ký quỹ của BUY ngay.
- Thuật toán:
    start_time = now_ms()
    for i in 0..N_pairs-1:
        if now_ms() - start_time > MAX_EXEC_TIME: break   # chỉ kiểm tra ở đầu cặp
        send BUY  (volume = chunk[i], filling = IOC)
        send SELL (volume = chunk[i], filling = IOC)
- Không được dừng giữa BUY và SELL của cùng một cặp.
- Nếu BUY khớp mà SELL thất bại: gửi lại SELL tối đa 2 lần; vẫn thất bại thì đóng
  ngay BUY của cặp đó để không bị hở một chiều.
- Sau vòng lặp, V_actual = tổng khối lượng BUY, phải bằng tổng khối lượng SELL.
  Nếu bị break sớm thì V_actual < V, rủi ro thực tế nhỏ hơn, chấp nhận được.

BƯỚC 5: Gán Stop Loss hàng loạt (sau khi toàn bộ vị thế đã nằm yên trên server)
- Tuyệt đối không gán SL lúc mở lệnh (tránh lỗi trượt giá/giãn spread lúc tin ra).
- Lấy vị thế theo magic, tính:
    P_ref      = giá mở trung bình có trọng số khối lượng của các lệnh BUY
    S_real     = P_ref - giá mở trung bình có trọng số của các lệnh SELL
                 (spread thực tế đã gồm trượt giá)
    Risk_real  = V_actual * CS * (BUFFER_PIPS + S_real)
- Nếu Risk_real > MAX_RISK, giảm BUFFER:
    BUFFER_eff = MAX_RISK / (V_actual * CS) - S_real
  Nếu BUFFER_eff <= 0 thì đóng toàn bộ ngay. Ngược lại BUFFER_eff = BUFFER_PIPS.
- Gán SL đồng nhất cho mọi chunk (một mức chung, không dựa theo giá mở từng lệnh):
    Mọi lệnh BUY : SL = P_ref - SL_PIPS
    Mọi lệnh SELL: SL = P_ref + SL_PIPS
  (BUY_SL và SELL_SL lưu lại để dùng ở Bước 6, kiểm tra stops_level của broker.)

--------------------------------------------------------------------------------
IV. BẢNG MẪU CHẠY THỰC TẾ (DRY RUN DATA)
- Input: MAX_RISK = 375$, SL_PIPS = 15.0, BUFFER_PIPS = 8.0, LEVERAGE = 200,
  MAX_EXEC_TIME = 300ms, SO = 0% (Stop Out 0%).
- Thị trường: Ask = 4200.00, Bid = 4199.00, Spread = 1.0.

1. Bước 1: Loss_per_lot = 100 * (8 + 1) = 900$
   V_risk = 375 / 900 = 0.4167 ; V_so (SO = 0) = 375 / 900 = 0.4167
   V = 0.41 lot cho mỗi phía (0.41 BUY + 0.41 SELL). Mất tối đa = 0.41 * 900 = 369$.
   (Nếu quên spread, 375/800 = 0.46 lot sẽ mất 0.46 * 900 = 414$, vượt MAX_RISK.)
2. Bước 2: T_benchmark = 45 ms. Cặp mẫu 0.01 lot được giữ lại.
3. Bước 3: N_pairs = floor(300 / 45) = 6.
   units = 41, units_rest = 40, base = 6, rem = 4.
   Các cặp: 0.07, 0.07, 0.07, 0.07, 0.06, 0.06 (tổng 0.40) cộng benchmark 0.01 = 0.41.
   Margin Guardrail: 0.07 * 100 * 4200 / 200 = 147$ <= Free Margin 375$ (đạt).
4. Bước 4: Bắn xen kẽ: BUY(0.07) -> SELL(0.07) -> ... -> BUY(0.06) -> SELL(0.06).
5. Bước 5: P_ref = 4200.00, S_real = 1.0 (giả sử không trượt giá).
   BUY SL = 4185.00 ; SELL SL = 4215.00.
6. Bước 6:
   - Nếu SELL chạm 4215: SELL lỗ 16 * 41 = 656$, BUY lời tạm thời lớn. Nếu giá về 4207: BUY lời 7 * 41 = 287$.
     Mất ròng = 656 - 287 = 369$.
   - Nếu BUY chạm 4185: BUY lỗ 15 * 41 = 615$. Nếu giá về 4193: SELL lời (4199 - 4193) * 41 = 246$.
     Mất ròng = 615 - 246 = 369$.
================================================================================