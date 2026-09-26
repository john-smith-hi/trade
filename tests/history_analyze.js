"use strict";

const fs = require("fs");
const path = require("path");
const H = require("../history/analyze.js");

let failed = 0;

function check(name, fn) {
  try {
    fn();
    console.log("ok  " + name);
  } catch (err) {
    failed++;
    console.error("FAIL " + name);
    console.error("  " + (err && err.stack ? err.stack : err));
  }
}

function eq(actual, expected, label) {
  if (actual !== expected) {
    throw new Error((label || "expected") + " " + JSON.stringify(expected) + " but got " + JSON.stringify(actual));
  }
}

const HEADER = "ticket,opening_time_utc,closing_time_utc,type,lots,original_position_size,symbol,opening_price,closing_price,stop_loss,take_profit,commission,swap,profit,equity,margin_level,close_reason";

function line(fields) {
  const row = Object.assign({
    ticket: "1",
    open: "2026-01-02T00:00:00Z",
    close: "2026-01-02T01:00:00Z",
    type: "buy",
    lots: "0.10",
    original: "0.10",
    symbol: "XAUUSDm",
    openPx: "100",
    closePx: "110",
    sl: "90",
    tp: "120",
    commission: "-1",
    swap: "-0.5",
    profit: "10",
    reason: "tp",
  }, fields);
  return [
    row.ticket, row.open, row.close, row.type, row.lots, row.original, row.symbol,
    row.openPx, row.closePx, row.sl, row.tp, row.commission, row.swap, row.profit, "", "", row.reason,
  ].join(",");
}

function csv(rows) {
  return [HEADER].concat(rows).join("\n");
}

function order(fields) {
  return Object.assign({
    position_id: 42,
    action: "sell",
    symbol: "XAUUSDm",
    open_time: 1760000000000,
    close_time: 1760003600000,
    volume_deal: "0.02",
    volume_position: "0.04",
    open_price: 200,
    close_price: 190,
    sl: 210,
    tp: 180,
    commission: -0.2,
    swap: 0,
    profit: 5,
    close_reason: "TP",
  }, fields);
}

check("sample csv golden stats", function () {
  const text = fs.readFileSync(path.join(__dirname, "../csv/01_01_2007-26_09_2026.csv"), "utf8");
  const parsed = H.parseCsv(text);
  eq(parsed.ok, true);
  eq(parsed.trades.length, 135);
  eq(parsed.skippedTotal, 0);
  const report = H.analyze(parsed.trades);
  eq(Number(report.net.toFixed(2)), 180.23);
  eq(report.wins, 59);
  eq(report.losses, 76);
  eq(report.breakeven, 0);
  if (Math.abs(report.profitFactor - 1.128447624613367) > 1e-9) throw new Error("pf " + report.profitFactor);
});

check("empty and header-only csv", function () {
  eq(H.parseCsv("").error, "File trống.");
  eq(H.parseCsv("   \n").error, "File trống.");
  eq(H.parseInput("").error, "Nội dung trống.");
  eq(H.parseInput(" \n ").error, "Nội dung trống.");
  const onlyHeader = H.parseCsv(HEADER + "\n");
  eq(onlyHeader.ok, false);
  eq(onlyHeader.error, "Không có lệnh hợp lệ");
});

check("missing columns and null byte", function () {
  const missing = H.parseCsv("ticket,symbol\n1,XAU\n");
  eq(missing.ok, false);
  if (missing.error.indexOf("Thiếu cột:") !== 0) throw new Error(missing.error);
  eq(H.parseInput("a,b\0c").error, "File phải là chữ UTF-8.");
});

check("bad rows are skipped and a good row is kept", function () {
  const parsed = H.parseCsv(csv([
    line({ ticket: "1" }),
    line({ ticket: "2", type: "balance" }),
    line({ ticket: "3", lots: "0" }),
    line({ ticket: "4", lots: "-1" }),
    line({ ticket: "5", openPx: "0" }),
    line({ ticket: "6", close: "2026-01-01T00:00:00Z" }),
    line({ ticket: "7", profit: "nope" }),
    line({ ticket: "8", commission: "1e309" }),
    line({ ticket: "", symbol: "XAUUSDm" }),
  ]));
  eq(parsed.ok, true);
  eq(parsed.trades.length, 1);
  eq(parsed.skippedTotal, 8);
  eq(parsed.skipped.length, 8);
  eq(parsed.trades[0].ticket, "1");
  eq(parsed.trades[0].net, 8.5);
  eq(Number(parsed.trades[0].r.toFixed(2)), 1);
});

check("all invalid rows do not import", function () {
  const parsed = H.parseCsv(csv([
    line({ type: "limit" }),
    line({ lots: "-2" }),
  ]));
  eq(parsed.ok, false);
  if (parsed.error.indexOf("Không có lệnh hợp lệ") !== 0) throw new Error(parsed.error);
  eq(parsed.skippedTotal, 2);
});

check("quoted comma, escaped quote, crlf, bom, case", function () {
  const text = "\uFEFF" + HEADER + "\r\n" +
    '"9","2026-03-01T00:00:00Z","2026-03-01T02:00:00Z","BUY","0.2","0.5","XA""U,USD","100","101","99","110","0","0","1","","","User"\r\n';
  const parsed = H.parseCsv(text);
  eq(parsed.ok, true);
  eq(parsed.trades.length, 1);
  const trade = parsed.trades[0];
  eq(trade.symbol, 'XA"U,USD');
  eq(trade.side, "buy");
  eq(trade.reason, "user");
  eq(trade.partial, true);
  eq(trade.holdMs, 2 * 60 * 60 * 1000);
});

check("control chars stripped and sl 0 is ignored", function () {
  const parsed = H.parseCsv(csv([
    line({ symbol: "XAU\u0007USDm", sl: "0", tp: "" }),
  ]));
  eq(parsed.ok, true, parsed.error);
  eq(parsed.trades[0].symbol, "XAUUSDm");
  eq(parsed.trades[0].sl, null);
  eq(parsed.trades[0].tp, null);
  eq(parsed.trades[0].r, null);
  eq(H.parseCsv("ticket\0,symbol\n").error, "File phải là chữ UTF-8.");
});

check("wrong-side sl has no R and equal open/close is allowed", function () {
  const wrong = H.parseCsv(csv([line({ sl: "130", closePx: "110" })]));
  eq(wrong.trades[0].r, null);
  const flat = H.parseCsv(csv([line({ close: "2026-01-02T00:00:00Z", closePx: "100", profit: "0", commission: "0", swap: "0", sl: "" })]));
  eq(flat.ok, true);
  eq(flat.trades[0].holdMs, 0);
  eq(flat.trades[0].net, 0);
});

check("unclosed quote does not throw", function () {
  const parsed = H.parseCsv(HEADER + '\n"1,2026-01-02T00:00:00Z,2026-01-02T01:00:00Z,buy,0.1,0.1,XAU,100,110,90,120,0,0,1,,,tp');
  eq(parsed.ok, false);
});

check("json orders, seconds, array, and partial", function () {
  const wrapped = H.parseInput(JSON.stringify({ count: 1, orders: [order({})] }));
  eq(wrapped.ok, true);
  eq(wrapped.trades[0].ticket, "42");
  eq(wrapped.trades[0].side, "sell");
  eq(wrapped.trades[0].reason, "tp");
  eq(wrapped.trades[0].partial, true);
  eq(Number(wrapped.trades[0].r.toFixed(2)), 1);
  eq(wrapped.trades[0].net, 4.8);

  const seconds = H.parseInput(JSON.stringify([order({
    position_id: "7",
    open_time: 1600000000,
    close_time: 1600003600,
    action: "buy",
    sl: 190,
    tp: 220,
    open_price: 200,
    close_price: 210,
  })]));
  eq(seconds.ok, true);
  eq(seconds.trades[0].open, 1600000000 * 1000);

  const millis = H.parseInput(JSON.stringify([order({ open_time: 946684800000, close_time: 946688400000 })]));
  eq(millis.trades[0].open, 946684800000);
});

check("json errors", function () {
  eq(H.parseInput("{").error, "JSON không hợp lệ.");
  eq(H.parseInput("{}").error, "Không thấy mảng orders.");
  eq(H.parseInput("[]").error, "Không có lệnh hợp lệ");
  eq(H.parseInput('{"orders":null}').error, "Không thấy mảng orders.");
  const bad = H.parseInput('{"orders":[null, 1, []]}');
  eq(bad.ok, false);
  eq(bad.skippedTotal, 3);
  const proto = Object.prototype.polluted;
  H.parseInput('{"__proto__":{"polluted":true},"orders":[]}');
  eq(Object.prototype.polluted, proto);
});

check("xss payload stays text", function () {
  const symbol = "<svg/onload=alert(1)>";
  const parsed = H.parseInput(JSON.stringify({ orders: [order({ symbol: symbol, position_id: "x<script>" })] }));
  eq(parsed.trades[0].symbol, symbol);
  eq(parsed.trades[0].ticket, "x<script>");
});

check("time bounds and ict parts", function () {
  const old = H.parseCsv(csv([line({ open: "1980-01-01T00:00:00Z", close: "1980-01-01T01:00:00Z" })]));
  eq(old.ok, false);
  const parts = H.ictParts(Date.parse("2026-09-24T17:00:00Z"));
  eq(parts.year, 2026);
  eq(parts.month, 9);
  eq(parts.day, 25);
  eq(parts.hour, 0);
  eq(parts.second, 0);
  const start = H.ictDayStart("2026-09-14");
  eq(start, Date.parse("2026-09-13T17:00:00Z"));
});

check("analyze edge reports", function () {
  const empty = H.analyze([]);
  eq(empty.n, 0);
  eq(empty.profitFactor, null);
  eq(empty.maxDrawdown, 0);
  const wins = H.parseCsv(csv([
    line({ ticket: "1", profit: "10", commission: "0", swap: "0" }),
    line({ ticket: "2", profit: "5", commission: "0", swap: "0", close: "2026-01-02T02:00:00Z" }),
  ]));
  eq(H.analyze(wins.trades).profitFactor, Infinity);
  const losses = H.parseCsv(csv([
    line({ ticket: "1", closePx: "90", profit: "-4", commission: "0", swap: "0", sl: "90", tp: "" }),
  ]));
  eq(H.analyze(losses.trades).profitFactor, 0);
  const dd = H.parseCsv(csv([
    line({ ticket: "1", profit: "10", commission: "0", swap: "0", close: "2026-01-02T01:00:00Z" }),
    line({ ticket: "2", profit: "-30", commission: "0", swap: "0", close: "2026-01-02T02:00:00Z" }),
    line({ ticket: "3", profit: "5", commission: "0", swap: "0", close: "2026-01-02T03:00:00Z" }),
  ]));
  eq(H.analyze(dd.trades).maxDrawdown, 30);
  eq(H.analyze(dd.trades).maxLossStreak, 1);
  eq(H.analyze(null).n, 0);
});

check("too many trades and too large text", function () {
  const rows = [];
  for (let i = 0; i < 20001; i++) rows.push(line({ ticket: String(i + 1) }));
  eq(H.parseCsv(csv(rows)).error, "Tối đa 20000 lệnh mỗi lần nạp.");
  eq(H.parseInput("{" + "a".repeat(8 * 1024 * 1024)).error, "Nội dung quá lớn (tối đa 8 MB).");
});

if (failed) {
  console.error(failed + " failed");
  process.exit(1);
}
console.log("all passed");
