/**
 * CSV lịch sử lệnh, hoặc JSON { orders: [...] } từ orders-history.
 *
 * Net = profit + commission + swap.
 * Múi giờ nhóm số liệu là ICT (UTC+7), không theo múi giờ máy.
 * Giờ / thứ / khung trong ngày: lúc MỞ lệnh.
 * Ngày / tuần / tháng: lúc ĐÓNG lệnh.
 * R chỉ tính khi SL còn phía lỗ so với giá vào.
 * SL/TP trong file là mức được ghi (thường là mức lúc đóng, có thể đã dời).
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.HistoryAnalyze = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const ICT_OFFSET_MS = 7 * 60 * 60 * 1000;
  const REQUIRED = [
    "ticket",
    "opening_time_utc",
    "closing_time_utc",
    "type",
    "lots",
    "symbol",
    "opening_price",
    "closing_price",
    "profit",
  ];
  const HOLD_KEYS = ["Dưới 5 phút", "5–30 phút", "30–120 phút", "2–8 giờ", "Trên 8 giờ"];
  const SESSION_KEYS = ["07–15 Sáng", "15–20 Chiều", "20–02 Tối", "02–07 Đêm"];
  const SIDE_KEYS = ["buy", "sell"];
  const WD_KEYS = [1, 2, 3, 4, 5, 6, 0];
  const HOURS = Array.from({ length: 24 }, function (_, i) { return i; });
  const R_KEYS = ["< −1R", "−1R – 0", "0 – 1R", "1R – 2R", "≥ 2R"];
  const REASON_ORDER = ["tp", "sl", "user", "so", "unknown"];
  const MAX_TEXT = 8 * 1024 * 1024;
  const MAX_ROWS = 50000;
  const MAX_TRADES = 20000;
  const MAX_TICKET = 64;
  const MAX_SYMBOL = 64;
  const MAX_REASON = 32;
  const MIN_TIME = Date.UTC(1990, 0, 1);
  const MAX_TIME = Date.UTC(2100, 0, 1);

  function mean(xs) {
    if (!xs.length) return null;
    let s = 0;
    for (let i = 0; i < xs.length; i++) s += xs[i];
    return s / xs.length;
  }

  function median(sorted) {
    const n = sorted.length;
    if (!n) return null;
    const m = Math.floor(n / 2);
    if (n % 2) return sorted[m];
    return (sorted[m - 1] + sorted[m]) / 2;
  }

  function sampleStdev(xs) {
    if (xs.length < 2) return null;
    const m = mean(xs);
    let v = 0;
    for (let i = 0; i < xs.length; i++) {
      const d = xs[i] - m;
      v += d * d;
    }
    return Math.sqrt(v / (xs.length - 1));
  }

  function pad(n) {
    return String(n).padStart(2, "0");
  }

  function ictParts(ms) {
    const d = new Date(ms + ICT_OFFSET_MS);
    return {
      year: d.getUTCFullYear(),
      month: d.getUTCMonth() + 1,
      day: d.getUTCDate(),
      hour: d.getUTCHours(),
      minute: d.getUTCMinutes(),
      second: d.getUTCSeconds(),
      weekday: d.getUTCDay(),
    };
  }

  function dayKey(ms) {
    const p = ictParts(ms);
    return p.year + "-" + pad(p.month) + "-" + pad(p.day);
  }

  function monthKey(ms) {
    const p = ictParts(ms);
    return p.year + "-" + pad(p.month);
  }

  function ictDayStart(key) {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(key || "");
    if (!m) return NaN;
    return Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])) - ICT_OFFSET_MS;
  }

  function isoWeek(ms) {
    const p = ictParts(ms);
    const date = new Date(Date.UTC(p.year, p.month - 1, p.day));
    const dayNum = date.getUTCDay() || 7;
    date.setUTCDate(date.getUTCDate() + 4 - dayNum);
    const isoYear = date.getUTCFullYear();
    const yearStart = new Date(Date.UTC(isoYear, 0, 1));
    const week = Math.ceil((((date - yearStart) / 86400000) + 1) / 7);
    return isoYear + "-W" + pad(week);
  }

  function sessionKey(hour) {
    if (hour >= 7 && hour < 15) return SESSION_KEYS[0];
    if (hour >= 15 && hour < 20) return SESSION_KEYS[1];
    if (hour >= 20 || hour < 2) return SESSION_KEYS[2];
    return SESSION_KEYS[3];
  }

  function holdBucket(ms) {
    const minutes = ms / 60000;
    if (minutes < 5) return HOLD_KEYS[0];
    if (minutes < 30) return HOLD_KEYS[1];
    if (minutes < 120) return HOLD_KEYS[2];
    if (minutes < 480) return HOLD_KEYS[3];
    return HOLD_KEYS[4];
  }

  function rBucket(r) {
    if (r < -1) return R_KEYS[0];
    if (r < 0) return R_KEYS[1];
    if (r < 1) return R_KEYS[2];
    if (r < 2) return R_KEYS[3];
    return R_KEYS[4];
  }

  function lotKey(lots) {
    return (Math.round(lots * 100) / 100).toFixed(2);
  }

  function numOrNull(v) {
    if (v == null) return null;
    const s = String(v).trim();
    if (!s) return null;
    const n = Number(s);
    return Number.isFinite(n) ? n : null;
  }

  function parseTime(v) {
    const raw = String(v || "").trim();
    if (!raw) return null;
    const iso = /Z$|[+-]\d\d:?\d\d$/.test(raw) ? raw : raw + "Z";
    const ms = Date.parse(iso);
    return Number.isFinite(ms) ? ms : null;
  }

  function splitCsv(text) {
    const src = String(text).replace(/^\uFEFF/, "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    const rows = [];
    let row = [];
    let cur = "";
    let quoted = false;
    for (let i = 0; i < src.length; i++) {
      const c = src[i];
      if (quoted) {
        if (c === '"') {
          if (src[i + 1] === '"') {
            cur += '"';
            i++;
          } else {
            quoted = false;
          }
        } else {
          cur += c;
        }
      } else if (c === '"') {
        quoted = true;
      } else if (c === ",") {
        row.push(cur);
        cur = "";
      } else if (c === "\n") {
        row.push(cur);
        rows.push(row);
        row = [];
        cur = "";
      } else {
        cur += c;
      }
    }
    if (cur.length || row.length) {
      row.push(cur);
      rows.push(row);
    }
    return rows.filter(function (r) {
      return r.some(function (cell) { return String(cell).trim() !== ""; });
    });
  }

  function parseCsv(text) {
    if (typeof text !== "string" || !text.trim()) return blankResult("File trống.");
    if (text.indexOf("\0") >= 0) return blankResult("File phải là chữ UTF-8.");
    if (text.length > MAX_TEXT) return blankResult("Nội dung quá lớn (tối đa 8 MB).");
    const rows = splitCsv(text);
    if (!rows.length) return blankResult("File trống.");
    if (rows.length - 1 > MAX_ROWS) return blankResult("Quá nhiều dòng.");
    const idx = new Map();
    rows[0].forEach(function (cell, i) {
      const key = cleanText(cell, 80).toLowerCase();
      if (key && !idx.has(key)) idx.set(key, i);
    });
    const missing = REQUIRED.filter(function (name) { return !idx.has(name); });
    if (missing.length) return blankResult("Thiếu cột: " + missing.join(", "));

    function col(row, name) {
      const i = idx.get(name);
      if (i == null || i >= row.length) return "";
      return String(row[i]).trim();
    }

    const trades = [];
    const skipped = [];
    let skippedTotal = 0;
    for (let i = 1; i < rows.length; i++) {
      const built = buildTrade(rows[i], col);
      if (built.error) {
        skippedTotal++;
        if (skipped.length < 20) skipped.push({ line: i + 1, reason: built.error });
        continue;
      }
      if (trades.length >= MAX_TRADES) return blankResult("Tối đa " + MAX_TRADES + " lệnh mỗi lần nạp.");
      trades.push(built.trade);
    }
    return finish(trades, skipped, skippedTotal);
  }

  function makeTrade(fields) {
    const ticket = asText(fields.ticket, MAX_TICKET);
    const open = asTime(fields.open);
    const close = asTime(fields.close);
    const side = asText(fields.side, 16).toLowerCase();
    const lots = lotsValue(fields.lots);
    const symbol = asText(fields.symbol, MAX_SYMBOL);
    const openPrice = requiredPrice(fields.openPrice);
    const closePrice = requiredPrice(fields.closePrice);
    const profit = requiredProfit(fields.profit);
    if (!ticket) return { error: "thiếu ticket" };
    if (open == null || close == null) return { error: "thời gian không đọc được" };
    if (close < open) return { error: "đóng trước lúc mở" };
    if (side !== "buy" && side !== "sell") return { error: "type không phải buy/sell" };
    if (lots == null) return { error: "lots không hợp lệ" };
    if (!symbol) return { error: "thiếu symbol" };
    if (openPrice == null || closePrice == null) return { error: "giá không đọc được" };
    if (profit == null) return { error: "profit không đọc được" };

    const commission = optionalFee(fields.commission, "commission");
    if (typeof commission === "object") return commission;
    const swap = optionalFee(fields.swap, "swap");
    if (typeof swap === "object") return swap;
    const sl = optionalLevel(fields.sl);
    const tp = optionalLevel(fields.tp);
    const originalLots = lotsValue(fields.originalLots);
    const reasonText = asText(fields.reason, MAX_REASON).toLowerCase();
    const net = profit + commission + swap;
    let r = null;
    let plannedR = null;
    if (sl != null) {
      const risk = side === "buy" ? openPrice - sl : sl - openPrice;
      if (risk > 0) {
        const move = side === "buy" ? closePrice - openPrice : openPrice - closePrice;
        r = move / risk;
        if (tp != null) {
          const target = side === "buy" ? tp - openPrice : openPrice - tp;
          if (target > 0) plannedR = target / risk;
        }
      }
    }
    return {
      trade: {
        ticket: ticket,
        open: open,
        close: close,
        side: side,
        lots: lots,
        originalLots: originalLots,
        symbol: symbol,
        openPrice: openPrice,
        closePrice: closePrice,
        sl: sl,
        tp: tp,
        commission: commission,
        swap: swap,
        profit: profit,
        net: net,
        reason: reasonText || "unknown",
        holdMs: close - open,
        r: r,
        plannedR: plannedR,
        partial: originalLots != null && Math.abs(originalLots - lots) > 1e-8,
      },
    };
  }

  function buildTrade(row, col) {
    return makeTrade({
      ticket: col(row, "ticket"),
      open: col(row, "opening_time_utc"),
      close: col(row, "closing_time_utc"),
      side: col(row, "type"),
      lots: col(row, "lots"),
      symbol: col(row, "symbol"),
      openPrice: col(row, "opening_price"),
      closePrice: col(row, "closing_price"),
      profit: col(row, "profit"),
      sl: col(row, "stop_loss"),
      tp: col(row, "take_profit"),
      commission: col(row, "commission"),
      swap: col(row, "swap"),
      originalLots: col(row, "original_position_size"),
      reason: col(row, "close_reason"),
    });
  }

  function epochMs(v) {
    const n = Number(v);
    if (!Number.isFinite(n) || n <= 0) return null;
    return n >= 1e11 ? n : n * 1000;
  }

  function blankResult(error) {
    return { ok: false, error: error, trades: [], skipped: [], skippedTotal: 0 };
  }

  function cleanText(v, max) {
    return String(v == null ? "" : v).replace(/[\u0000-\u001F\u007F]/g, "").trim().slice(0, max);
  }

  function asText(v, max) {
    if (typeof v === "number" && Number.isFinite(v)) return cleanText(String(v), max);
    if (typeof v !== "string") return "";
    return cleanText(v, max);
  }

  function boundTime(ms) {
    if (ms == null || !Number.isFinite(ms) || ms < MIN_TIME || ms > MAX_TIME) return null;
    return ms;
  }

  function asTime(v) {
    if (typeof v === "number") return boundTime(epochMs(v));
    if (typeof v === "string" && /^\d{1,16}$/.test(v.trim())) return boundTime(epochMs(Number(v.trim())));
    return boundTime(parseTime(v));
  }

  function readNumber(v) {
    if (typeof v === "number") return Number.isFinite(v) ? v : null;
    return numOrNull(v);
  }

  function lotsValue(v) {
    if (v == null || (typeof v !== "number" && String(v).trim() === "")) return null;
    const n = readNumber(v);
    if (n == null || n <= 0 || n > 10000) return null;
    return n;
  }

  function requiredPrice(v) {
    if (v == null || (typeof v !== "number" && String(v).trim() === "")) return null;
    const n = readNumber(v);
    if (n == null || n <= 0 || n > 1e9) return null;
    return n;
  }

  function requiredProfit(v) {
    if (v == null || (typeof v !== "number" && String(v).trim() === "")) return null;
    const n = readNumber(v);
    if (n == null || Math.abs(n) > 1e9) return null;
    return n;
  }

  function optionalLevel(v) {
    if (v == null || (typeof v !== "number" && String(v).trim() === "")) return null;
    const n = readNumber(v);
    if (n == null || n <= 0 || n > 1e9) return null;
    return n;
  }

  function optionalFee(v, label) {
    if (v == null) return 0;
    if (typeof v === "number") {
      if (!Number.isFinite(v) || Math.abs(v) > 1e9) return { error: label + " không hợp lệ" };
      return v;
    }
    const s = String(v).trim();
    if (!s) return 0;
    const n = Number(s);
    if (!Number.isFinite(n) || Math.abs(n) > 1e9) return { error: label + " không hợp lệ" };
    return n;
  }

  function finish(trades, skipped, skippedTotal) {
    if (!trades.length) {
      const why = skipped.length ? skipped[0].reason : "";
      const extra = skippedTotal > 1 ? " (" + skippedTotal + " dòng bỏ qua)" : "";
      return {
        ok: false,
        error: "Không có lệnh hợp lệ" + (why ? ": " + why : "") + extra,
        trades: [],
        skipped: skipped,
        skippedTotal: skippedTotal,
      };
    }
    return { ok: true, error: "", trades: trades, skipped: skipped, skippedTotal: skippedTotal };
  }

  function parseOrders(text) {
    if (typeof text !== "string" || !text.trim()) return blankResult("Nội dung trống.");
    if (text.indexOf("\0") >= 0) return blankResult("File phải là chữ UTF-8.");
    if (text.length > MAX_TEXT) return blankResult("Nội dung quá lớn (tối đa 8 MB).");
    let data;
    try {
      data = JSON.parse(text);
    } catch (e) {
      return blankResult("JSON không hợp lệ.");
    }
    const orders = Array.isArray(data) ? data : (data && Array.isArray(data.orders) ? data.orders : null);
    if (!orders) return blankResult("Không thấy mảng orders.");
    if (orders.length > MAX_ROWS) return blankResult("Quá nhiều dòng.");
    const trades = [];
    const skipped = [];
    let skippedTotal = 0;
    for (let i = 0; i < orders.length; i++) {
      const order = orders[i];
      if (!order || typeof order !== "object" || Array.isArray(order)) {
        skippedTotal++;
        if (skipped.length < 20) skipped.push({ line: i + 1, reason: "dòng không phải lệnh" });
        continue;
      }
      const built = makeTrade({
        ticket: order.position_id != null ? order.position_id : order.deal_id,
        open: order.open_time,
        close: order.close_time,
        side: order.action,
        lots: order.volume_deal,
        symbol: order.symbol,
        openPrice: order.open_price,
        closePrice: order.close_price,
        profit: order.profit,
        sl: order.sl,
        tp: order.tp,
        commission: order.commission,
        swap: order.swap,
        originalLots: order.volume_position,
        reason: order.close_reason,
      });
      if (built.error) {
        skippedTotal++;
        if (skipped.length < 20) skipped.push({ line: i + 1, reason: built.error });
        continue;
      }
      if (trades.length >= MAX_TRADES) return blankResult("Tối đa " + MAX_TRADES + " lệnh mỗi lần nạp.");
      trades.push(built.trade);
    }
    return finish(trades, skipped, skippedTotal);
  }

  function parseInput(text) {
    try {
      if (typeof text !== "string") return blankResult("Nội dung trống.");
      if (text.indexOf("\0") >= 0) return blankResult("File phải là chữ UTF-8.");
      if (text.length > MAX_TEXT) return blankResult("Nội dung quá lớn (tối đa 8 MB).");
      const trimmed = text.replace(/^\uFEFF/, "").trim();
      if (!trimmed) return blankResult("Nội dung trống.");
      if (trimmed.charAt(0) === "{" || trimmed.charAt(0) === "[") return parseOrders(trimmed);
      return parseCsv(trimmed);
    } catch (e) {
      return blankResult("Không đọc được nội dung.");
    }
  }

  function byClose(list) {
    return list.slice().sort(function (a, b) {
      return a.close - b.close || String(a.ticket).localeCompare(String(b.ticket));
    });
  }

  function tally(list) {
    const n = list.length;
    let wins = 0;
    let losses = 0;
    let breakeven = 0;
    let grossProfit = 0;
    let grossLoss = 0;
    let net = 0;
    let totalLots = 0;
    let holdSum = 0;
    let holdWin = 0;
    let holdLoss = 0;
    let commission = 0;
    let swap = 0;
    let partialN = 0;
    let rSum = 0;
    let rCount = 0;
    let largestWin = null;
    let largestLoss = null;
    let best = null;
    let worst = null;
    let longest = null;
    let shortest = null;
    let firstOpen = null;
    let lastClose = null;
    const winNets = [];
    const lossNets = [];
    const nets = [];
    const holds = [];

    for (let i = 0; i < n; i++) {
      const t = list[i];
      net += t.net;
      commission += t.commission;
      swap += t.swap;
      totalLots += t.lots;
      holdSum += t.holdMs;
      holds.push(t.holdMs);
      nets.push(t.net);
      if (t.partial) partialN++;
      if (t.r != null && Number.isFinite(t.r)) {
        rSum += t.r;
        rCount++;
      }
      if (firstOpen == null || t.open < firstOpen) firstOpen = t.open;
      if (lastClose == null || t.close > lastClose) lastClose = t.close;
      if (!longest || t.holdMs > longest.holdMs) longest = t;
      if (!shortest || t.holdMs < shortest.holdMs) shortest = t;
      if (t.net > 0) {
        wins++;
        grossProfit += t.net;
        holdWin += t.holdMs;
        winNets.push(t.net);
        if (largestWin == null || t.net > largestWin) {
          largestWin = t.net;
          best = t;
        }
      } else if (t.net < 0) {
        losses++;
        grossLoss += t.net;
        holdLoss += t.holdMs;
        lossNets.push(t.net);
        if (largestLoss == null || t.net < largestLoss) {
          largestLoss = t.net;
          worst = t;
        }
      } else {
        breakeven++;
      }
    }

    const avgWin = winNets.length ? mean(winNets) : null;
    const avgLoss = lossNets.length ? mean(lossNets) : null;
    const profitFactor = grossLoss < 0
      ? grossProfit / Math.abs(grossLoss)
      : (grossProfit > 0 ? Infinity : null);
    const sortedNets = nets.slice().sort(function (a, b) { return a - b; });
    const sortedHolds = holds.slice().sort(function (a, b) { return a - b; });

    return {
      n: n,
      wins: wins,
      losses: losses,
      breakeven: breakeven,
      winRate: n ? wins / n : null,
      grossProfit: grossProfit,
      grossLoss: grossLoss,
      net: net,
      profitFactor: profitFactor,
      avg: n ? net / n : null,
      avgWin: avgWin,
      avgLoss: avgLoss,
      payoff: avgWin != null && avgLoss != null && avgLoss !== 0 ? avgWin / Math.abs(avgLoss) : null,
      median: median(sortedNets),
      largestWin: largestWin,
      largestLoss: largestLoss,
      best: best,
      worst: worst,
      stdev: sampleStdev(nets),
      totalLots: totalLots,
      avgLots: n ? totalLots / n : null,
      per001: totalLots > 0 ? (net / totalLots) * 0.01 : null,
      avgHold: n ? holdSum / n : null,
      medianHold: median(sortedHolds),
      avgHoldWin: wins ? holdWin / wins : null,
      avgHoldLoss: losses ? holdLoss / losses : null,
      longest: longest,
      shortest: shortest,
      commission: commission,
      swap: swap,
      avgR: rCount ? rSum / rCount : null,
      rCount: rCount,
      partialN: partialN,
      firstOpen: firstOpen,
      lastClose: lastClose,
    };
  }

  function groups(list, keyFn) {
    const map = new Map();
    for (let i = 0; i < list.length; i++) {
      const t = list[i];
      const key = keyFn(t);
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(t);
    }
    const rows = [];
    map.forEach(function (subset, key) {
      rows.push(Object.assign({ key: key }, tally(subset)));
    });
    return rows;
  }

  function ordered(keys, rows) {
    const map = new Map(rows.map(function (row) { return [row.key, row]; }));
    return keys.map(function (key) {
      return map.get(key) || Object.assign({ key: key }, tally([]));
    });
  }

  function groupSorted(list, keyFn) {
    return groups(list, keyFn).sort(function (a, b) {
      return String(a.key).localeCompare(String(b.key));
    });
  }

  function drawdown(sorted) {
    let eq = 0;
    let peak = 0;
    let peakAt = null;
    let maxDd = 0;
    let maxDdPct = null;
    let maxDdPeak = 0;
    let maxStart = null;
    let maxEnd = null;
    let ddStart = null;
    const equity = [];
    for (let i = 0; i < sorted.length; i++) {
      const t = sorted[i];
      eq += t.net;
      if (eq >= peak - 1e-9) {
        peak = eq;
        peakAt = t.close;
        ddStart = null;
      } else {
        if (ddStart == null) ddStart = peakAt;
        const dd = peak - eq;
        if (dd > maxDd + 1e-9) {
          maxDd = dd;
          maxDdPeak = peak;
          maxDdPct = peak > 0 ? dd / peak : null;
          maxStart = ddStart;
          maxEnd = t.close;
        }
      }
      equity.push({
        time: t.close,
        eq: eq,
        peak: peak,
        dd: Math.max(0, peak - eq),
      });
    }
    let recoveredAt = null;
    if (maxEnd != null && maxDd > 0) {
      for (let i = 0; i < equity.length; i++) {
        const p = equity[i];
        if (p.time > maxEnd && p.eq >= maxDdPeak - 1e-6) {
          recoveredAt = p.time;
          break;
        }
      }
    }
    const pcts = [];
    for (let i = 0; i < equity.length; i++) {
      const p = equity[i];
      if (p.peak > 0) pcts.push(((p.peak - p.eq) / p.peak) * 100);
    }
    return {
      maxDrawdown: maxDd,
      maxDrawdownPct: maxDdPct,
      maxDdPeak: maxDdPeak,
      ddStart: maxStart,
      ddEnd: maxEnd,
      ddRecoveredAt: recoveredAt,
      currentDrawdown: peak - eq,
      currentDrawdownPct: peak > 0 ? (peak - eq) / peak : null,
      ulcer: pcts.length ? Math.sqrt(mean(pcts.map(function (x) { return x * x; }))) : null,
      recoveryFactor: maxDd > 0 ? eq / maxDd : null,
    };
  }

  function streaks(sorted) {
    let maxW = 0;
    let maxL = 0;
    let curW = 0;
    let curL = 0;
    for (let i = 0; i < sorted.length; i++) {
      const net = sorted[i].net;
      if (net > 0) {
        curW++;
        curL = 0;
        if (curW > maxW) maxW = curW;
      } else if (net < 0) {
        curL++;
        curW = 0;
        if (curL > maxL) maxL = curL;
      } else {
        curW = 0;
        curL = 0;
      }
    }
    let current = { kind: "flat", n: 0 };
    if (curW > 0) current = { kind: "win", n: curW };
    else if (curL > 0) current = { kind: "loss", n: curL };
    return { maxWinStreak: maxW, maxLossStreak: maxL, currentStreak: current };
  }

  function concurrency(list) {
    const events = [];
    for (let i = 0; i < list.length; i++) {
      events.push([list[i].open, 1]);
      events.push([list[i].close, -1]);
    }
    events.sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
    let cur = 0;
    let max = 0;
    for (let i = 0; i < events.length; i++) {
      cur += events[i][1];
      if (cur > max) max = cur;
    }
    let overlapped = null;
    if (list.length <= 8000) {
      overlapped = 0;
      for (let i = 0; i < list.length; i++) {
        for (let j = 0; j < list.length; j++) {
          if (i === j) continue;
          if (list[i].open < list[j].close && list[j].open < list[i].close) {
            overlapped++;
            break;
          }
        }
      }
    }
    return { maxConcurrent: max, overlapped: overlapped };
  }

  function sharpeSortino(daily) {
    if (!daily.length) return { sharpe: null, sortino: null, calendarDays: 0 };
    const map = new Map(daily.map(function (d) { return [d.key, d.net]; }));
    const start = ictDayStart(daily[0].key);
    const end = ictDayStart(daily[daily.length - 1].key);
    const span = Math.round((end - start) / 86400000) + 1;
    const xs = [];
    if (span > 20000 || span < 1 || !Number.isFinite(span)) {
      for (let i = 0; i < daily.length; i++) xs.push(daily[i].net);
    } else {
      for (let t = start; t <= end; t += 86400000) xs.push(map.get(dayKey(t)) || 0);
    }
    const m = mean(xs);
    const sd = sampleStdev(xs);
    const down = xs.map(function (x) { return Math.min(0, x); });
    const downside = Math.sqrt(mean(down.map(function (x) { return x * x; })));
    return {
      sharpe: sd ? (m / sd) * Math.sqrt(365) : null,
      sortino: downside ? (m / downside) * Math.sqrt(365) : null,
      calendarDays: xs.length,
    };
  }

  function rExtras(list) {
    const rs = [];
    const planned = [];
    let slNotRisk = 0;
    let withSl = 0;
    let withTp = 0;
    for (let i = 0; i < list.length; i++) {
      const t = list[i];
      if (t.sl != null) withSl++;
      if (t.tp != null) withTp++;
      if (t.sl != null && t.r == null) slNotRisk++;
      if (t.r != null && Number.isFinite(t.r)) rs.push(t.r);
      if (t.plannedR != null && Number.isFinite(t.plannedR)) planned.push(t.plannedR);
    }
    rs.sort(function (a, b) { return a - b; });
    return {
      medianR: median(rs),
      plannedCount: planned.length,
      avgPlannedR: planned.length ? mean(planned) : null,
      slNotRisk: slNotRisk,
      missingSl: list.length - withSl,
      missingTp: list.length - withTp,
    };
  }

  function gapStats(list) {
    const sl = [];
    const tp = [];
    for (let i = 0; i < list.length; i++) {
      const t = list[i];
      if (t.reason === "sl" && t.sl != null) sl.push(Math.abs(t.closePrice - t.sl));
      if (t.reason === "tp" && t.tp != null) tp.push(Math.abs(t.closePrice - t.tp));
    }
    return {
      slGapAvg: sl.length ? mean(sl) : null,
      slGapN: sl.length,
      tpGapAvg: tp.length ? mean(tp) : null,
      tpGapN: tp.length,
    };
  }

  function exitFlags(list) {
    let slN = 0;
    let slWinN = 0;
    let slWinNet = 0;
    let soN = 0;
    let soNet = 0;
    for (let i = 0; i < list.length; i++) {
      const t = list[i];
      if (t.reason === "sl") {
        slN++;
        if (t.net > 0) {
          slWinN++;
          slWinNet += t.net;
        }
      } else if (t.reason === "so") {
        soN++;
        soNet += t.net;
      }
    }
    return { slN: slN, slWinN: slWinN, slWinNet: slWinNet, soN: soN, soNet: soNet };
  }

  function overnightStats(list) {
    let overnightN = 0;
    let overnightNet = 0;
    let intradayN = 0;
    let intradayNet = 0;
    for (let i = 0; i < list.length; i++) {
      const t = list[i];
      if (dayKey(t.open) !== dayKey(t.close)) {
        overnightN++;
        overnightNet += t.net;
      } else {
        intradayN++;
        intradayNet += t.net;
      }
    }
    return {
      overnightN: overnightN,
      overnightNet: overnightNet,
      intradayN: intradayN,
      intradayNet: intradayNet,
    };
  }

  function topShare(list, grossProfit) {
    if (!(grossProfit > 0)) return null;
    const wins = [];
    for (let i = 0; i < list.length; i++) {
      if (list[i].net > 0) wins.push(list[i].net);
    }
    wins.sort(function (a, b) { return b - a; });
    let top = 0;
    for (let i = 0; i < wins.length && i < 3; i++) top += wins[i];
    return top / grossProfit;
  }

  function kellyOf(base) {
    const decided = base.wins + base.losses;
    if (!decided || base.payoff == null || !(base.payoff > 0) || !Number.isFinite(base.payoff)) return null;
    const w = base.wins / decided;
    return w - (1 - w) / base.payoff;
  }

  function symbolRows(list) {
    const map = new Map();
    for (let i = 0; i < list.length; i++) {
      const t = list[i];
      if (!map.has(t.symbol)) map.set(t.symbol, []);
      map.get(t.symbol).push(t);
    }
    const rows = [];
    map.forEach(function (subset, symbol) {
      const row = Object.assign({ key: symbol }, tally(subset));
      row.buyN = 0;
      row.buyNet = 0;
      row.sellN = 0;
      row.sellNet = 0;
      for (let i = 0; i < subset.length; i++) {
        const t = subset[i];
        if (t.side === "buy") {
          row.buyN++;
          row.buyNet += t.net;
        } else {
          row.sellN++;
          row.sellNet += t.net;
        }
      }
      rows.push(row);
    });
    rows.sort(function (a, b) { return b.net - a.net || a.key.localeCompare(b.key); });
    return rows;
  }

  function reasonRows(list) {
    const rows = groups(list, function (t) { return t.reason; });
    rows.sort(function (a, b) {
      const ia = REASON_ORDER.indexOf(a.key);
      const ib = REASON_ORDER.indexOf(b.key);
      return (ia < 0 ? 50 : ia) - (ib < 0 ? 50 : ib) || String(a.key).localeCompare(String(b.key));
    });
    return rows;
  }

  function lotRows(list) {
    return groups(list, function (t) { return lotKey(t.lots); }).sort(function (a, b) {
      return Number(a.key) - Number(b.key);
    });
  }

  function analyze(trades) {
    const list = Array.isArray(trades) ? trades : [];
    const base = tally(list);
    const closed = byClose(list);
    const daily = groupSorted(list, function (t) { return dayKey(t.close); });
    const sqn = base.n >= 2 && base.stdev ? (base.avg / base.stdev) * Math.sqrt(base.n) : null;
    return Object.assign(
      {},
      base,
      drawdown(closed),
      streaks(closed),
      concurrency(list),
      sharpeSortino(daily),
      rExtras(list),
      gapStats(list),
      exitFlags(list),
      overnightStats(list),
      {
        top3Share: topShare(list, base.grossProfit),
        kelly: kellyOf(base),
        sqn: sqn,
        daily: daily,
        bySymbol: symbolRows(list),
        bySide: ordered(SIDE_KEYS, groups(list, function (t) { return t.side; })),
        byReason: reasonRows(list),
        byHour: ordered(HOURS, groups(list, function (t) { return ictParts(t.open).hour; })),
        byWeekday: ordered(WD_KEYS, groups(list, function (t) { return ictParts(t.open).weekday; })),
        bySession: ordered(SESSION_KEYS, groups(list, function (t) {
          return sessionKey(ictParts(t.open).hour);
        })),
        byMonth: groupSorted(list, function (t) { return monthKey(t.close); }),
        byWeek: groupSorted(list, function (t) { return isoWeek(t.close); }),
        byHold: ordered(HOLD_KEYS, groups(list, function (t) { return holdBucket(t.holdMs); })),
        byLot: lotRows(list),
        byR: ordered(R_KEYS, groups(list.filter(function (t) { return t.r != null; }), function (t) {
          return rBucket(t.r);
        })),
        winDays: daily.filter(function (d) { return d.net > 0; }).length,
        lossDays: daily.filter(function (d) { return d.net < 0; }).length,
        flatDays: daily.filter(function (d) { return d.net === 0; }).length,
        tradingDays: daily.length,
      }
    );
  }

  return {
    parseCsv: parseCsv,
    parseInput: parseInput,
    analyze: analyze,
    ictParts: ictParts,
    ictDayStart: ictDayStart,
    ICT_OFFSET_MS: ICT_OFFSET_MS,
  };
});
