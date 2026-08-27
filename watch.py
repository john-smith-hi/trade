# =============================================================================
# Watcher 24/7: Timer vùng giá + lệnh khớp/đóng TP-SL (cảnh báo Telegram)
# =============================================================================
#
# Chạy trong cùng process với api.py (chung lock MT5).
# Lần đầu mỗi account chỉ seed — không spam lịch sử cũ.
#
# =============================================================================

from collections import defaultdict
from datetime import datetime, timedelta
import threading
import time
import traceback

import MetaTrader5 as mt5

import mt5 as mt5app
import telegram_notify
import timer_alerts
import modify_if
import watch_state

WATCH_INTERVAL_SEC = 30
DEAL_LOOKBACK_HOURS = 6

DEAL_ENTRY_IN = getattr(mt5, "DEAL_ENTRY_IN", 0)
DEAL_ENTRY_OUT = getattr(mt5, "DEAL_ENTRY_OUT", 1)
DEAL_REASON_SL = getattr(mt5, "DEAL_REASON_SL", 3)
DEAL_REASON_TP = getattr(mt5, "DEAL_REASON_TP", 4)
DEAL_REASON_SO = getattr(mt5, "DEAL_REASON_SO", 5)

_started = False
_thread = None


def _log(message):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[Watch {now}] {message}", flush=True)


def _deal_side(deal):
    deal_type = int(getattr(deal, "type", -1))
    if deal_type == mt5.DEAL_TYPE_BUY:
        return "BUY"
    if deal_type == mt5.DEAL_TYPE_SELL:
        return "SELL"
    return ""


def _close_title(reason):
    reason = int(reason)
    if reason == DEAL_REASON_TP:
        return "ĐÓNG TP"
    if reason == DEAL_REASON_SL:
        return "ĐÓNG SL"
    if reason == DEAL_REASON_SO:
        return "STOP OUT"
    return "ĐÓNG LỆNH"


def poll_timer_alerts(lock):
    """Poll nến M1 đã đóng, cập nhật xml/timer.xml, Telegram khi đi vào vùng."""
    try:
        alerts = timer_alerts.load_alerts()
    except Exception as exc:
        _log(f"khong doc timer.xml: {exc}")
        return

    enabled = [a for a in alerts if a.get("enabled")]
    if not enabled:
        return

    groups = defaultdict(list)
    for alert in enabled:
        groups[alert["account"]].append(alert)

    now_ms = int(time.time() * 1000)
    quotes = {}
    for account_name, group in groups.items():
        try:
            account = mt5app.get_account(account_name)
            with lock:
                mt5app.connect_mt5(account, quiet=True)
                seen_symbols = {}
                try:
                    for alert in group:
                        symbol = alert["symbol"]
                        if symbol not in seen_symbols:
                            try:
                                seen_symbols[symbol] = mt5app.fetch_last_m1_candle(
                                    account, symbol, closed=True
                                )
                            except Exception as exc:
                                seen_symbols[symbol] = {"error": str(exc)}
                finally:
                    try:
                        mt5.shutdown()
                    except Exception:
                        pass
            quotes[account_name] = seen_symbols
        except Exception as exc:
            quotes[account_name] = {alert["symbol"]: {"error": str(exc)} for alert in group}
            _log(f"timer account {account_name}: {exc}")

    changed = False
    next_alerts = []
    for alert in alerts:
        if not alert.get("enabled"):
            next_alerts.append(alert)
            continue
        quote = (quotes.get(alert["account"]) or {}).get(alert["symbol"]) or {"error": "no quote"}
        if quote.get("error"):
            updated = dict(alert)
            updated["lastError"] = quote.get("error") or "no quote"
            updated["lastAt"] = now_ms
            next_alerts.append(updated)
            changed = True
            continue

        inside = timer_alerts.candle_hits_zone(quote, alert)
        updated = dict(alert)
        updated["lastBid"] = quote.get("close", quote.get("bid"))
        updated["lastAsk"] = quote.get("close", quote.get("ask"))
        updated["lastOpen"] = quote.get("open")
        updated["lastHigh"] = quote.get("high")
        updated["lastLow"] = quote.get("low")
        updated["lastClose"] = quote.get("close")
        updated["lastCandleTime"] = quote.get("time_str") or ""
        updated["lastSymbol"] = quote.get("symbol") or alert["symbol"]
        updated["lastAt"] = now_ms
        updated["lastError"] = ""
        updated["inside"] = inside

        if not alert.get("fired"):
            if not alert.get("primed"):
                updated["primed"] = True
            elif inside and not alert.get("inside"):
                updated["fired"] = True
                updated["firedAt"] = now_ms
                _log(
                    f"CHAM VUNG {alert['account']} {alert['symbol']} "
                    f"{alert['zoneLow']}-{alert['zoneHigh']} M1 {quote.get('time_str')}"
                )
                telegram_notify.send_alert(telegram_notify.build_message(
                    "TIMER — CHẠM VÙNG",
                    [
                        f"account: {alert['account']}",
                        f"{alert['symbol']} vùng {alert['zoneLow']} – {alert['zoneHigh']}",
                        f"M1 {quote.get('time_str') or ''} "
                        f"H={quote.get('high')} L={quote.get('low')} C={quote.get('close')}",
                        alert.get("note") or "",
                    ],
                ))
        next_alerts.append(updated)
        changed = True

    if changed:
        try:
            timer_alerts.save_alerts(next_alerts)
        except Exception as exc:
            _log(f"khong ghi timer.xml: {exc}")


def poll_modify_if(lock):
    """Poll tick; khi giá chạm vùng thì sửa SL/TP các lệnh mở cùng symbol."""
    try:
        jobs = modify_if.load_jobs()
    except Exception as exc:
        _log(f"khong doc modify_if.xml: {exc}")
        return

    waiting = [j for j in jobs if j.get("enabled") and not j.get("fired")]
    if not waiting:
        return

    groups = defaultdict(list)
    for job in waiting:
        groups[job["account"]].append(job)

    now_ms = int(time.time() * 1000)
    quotes = {}
    fired_results = {}
    for account_name, group in groups.items():
        try:
            account = mt5app.get_account(account_name)
            with lock:
                mt5app.connect_mt5(account, quiet=True)
                seen = {}
                try:
                    for job in group:
                        symbol = job["symbol"]
                        if symbol not in seen:
                            try:
                                seen[symbol] = mt5app.fetch_quote(account, symbol, "buy")
                            except Exception as exc:
                                seen[symbol] = {"error": str(exc)}
                    quotes[account_name] = seen
                    for job in group:
                        quote = seen.get(job["symbol"]) or {"error": "no quote"}
                        if quote.get("error"):
                            continue
                        if not job.get("primed"):
                            continue
                        hit = modify_if.tick_hits_zone(
                            job, quote["bid"], quote["ask"],
                            job.get("lastBid"), job.get("lastAsk"),
                        )
                        if hit:
                            try:
                                mt5app.apply_modify_if_job(account, {**job, "lastSymbol": quote.get("symbol")})
                                fired_results[job["id"]] = {"ok": True, "quote": quote}
                            except Exception as exc:
                                fired_results[job["id"]] = {"ok": False, "error": str(exc), "quote": quote}
                                _log(f"modify-if {account_name} {job['symbol']}: {exc}")
                finally:
                    try:
                        mt5.shutdown()
                    except Exception:
                        pass
        except Exception as exc:
            quotes[account_name] = {job["symbol"]: {"error": str(exc)} for job in group}
            _log(f"modify-if account {account_name}: {exc}")

    changed = False
    next_jobs = []
    for job in jobs:
        if not job.get("enabled") or job.get("fired"):
            next_jobs.append(job)
            continue
        quote = (quotes.get(job["account"]) or {}).get(job["symbol"]) or {"error": "no quote"}
        updated = dict(job)
        updated["lastAt"] = now_ms
        if quote.get("error"):
            updated["lastError"] = quote.get("error") or "no quote"
            next_jobs.append(updated)
            changed = True
            continue

        updated["lastBid"] = quote.get("bid")
        updated["lastAsk"] = quote.get("ask")
        updated["lastSymbol"] = quote.get("symbol") or job["symbol"]
        updated["lastError"] = ""

        fire = fired_results.get(job["id"])
        if not job.get("primed"):
            updated["primed"] = True
        elif fire is not None:
            updated["fired"] = True
            updated["enabled"] = False
            updated["firedAt"] = now_ms
            quote_f = fire.get("quote") or quote
            _log(
                f"MODIFY-IF {job['account']} {updated['lastSymbol']} "
                f"{job['zoneLow']}-{job['zoneHigh']} bid={quote_f.get('bid')} ask={quote_f.get('ask')}"
            )
            tp = job["tpPrice"] if job.get("tpPrice") is not None else "không đặt"
            telegram_notify.send_alert(telegram_notify.build_message(
                "KÍCH HOẠT MODIFY-ALL-IF" if fire.get("ok") else "LỖI MODIFY-ALL-IF",
                [
                    f"account: {job['account']}",
                    f"{updated['lastSymbol']} vùng {job['zoneLow']} – {job['zoneHigh']}",
                    f"bid={quote_f.get('bid')} ask={quote_f.get('ask')}",
                    f"SL mới: {job['slPrice']} | TP mới: {tp}",
                    "" if fire.get("ok") else (fire.get("error") or ""),
                ],
            ))
        next_jobs.append(updated)
        changed = True

    if changed:
        try:
            modify_if.save_jobs_locked(next_jobs)
        except Exception as exc:
            _log(f"khong ghi modify_if.xml: {exc}")


def _process_account_deals(account, state):
    name = account.get("name") or ""
    acc = watch_state.account_state(state, name)
    positions = mt5.positions_get() or []
    orders = mt5.orders_get() or []
    pos_tickets = [int(p.ticket) for p in positions]
    pending_tickets = [int(o.ticket) for o in orders]
    pending_set = set(acc.get("pending") or [])

    since = datetime.now() - timedelta(hours=DEAL_LOOKBACK_HOURS)
    deals = mt5.history_deals_get(since, datetime.now()) or []

    if not acc.get("seeded"):
        for deal in deals:
            watch_state.mark_deal(state, getattr(deal, "ticket", None))
        acc["seeded"] = True
        acc["pending"] = pending_tickets
        acc["positions"] = pos_tickets
        _log(f"seed {name}: {len(deals)} deals, {len(pos_tickets)} pos, {len(pending_tickets)} pending")
        return

    for deal in sorted(deals, key=lambda d: (int(getattr(d, "time", 0) or 0), int(getattr(d, "ticket", 0) or 0))):
        ticket = getattr(deal, "ticket", None)
        if watch_state.is_deal_notified(state, ticket):
            continue
        entry = int(getattr(deal, "entry", -1))
        reason = int(getattr(deal, "reason", -1))
        order_id = int(getattr(deal, "order", 0) or 0)
        symbol = getattr(deal, "symbol", "") or ""
        volume = getattr(deal, "volume", "")
        price = getattr(deal, "price", "")
        side = _deal_side(deal)
        lines = [
            f"account: {name}",
            f"{symbol} {side} {volume}".strip(),
            f"giá: {price}" if price not in (None, "") else "",
            f"ticket: {ticket}",
        ]

        if entry == DEAL_ENTRY_IN:
            watch_state.mark_deal(state, ticket)
            if watch_state.is_skip_open_order(state, order_id):
                continue
            if order_id in pending_set:
                title = "PENDING KHỚP"
            else:
                title = "MỞ LỆNH"
            telegram_notify.send_alert(telegram_notify.build_message(title, lines))
        elif entry == DEAL_ENTRY_OUT:
            watch_state.mark_deal(state, ticket)
            title = _close_title(reason)
            pnl_text = telegram_notify.format_pnl(getattr(deal, "profit", None))
            if pnl_text:
                lines.append(f"P/L: {pnl_text}")
            telegram_notify.send_alert(telegram_notify.build_message(title, lines))
        else:
            watch_state.mark_deal(state, ticket)

    acc["pending"] = pending_tickets
    acc["positions"] = pos_tickets


def poll_deals(lock):
    try:
        mt5app.ensure_accounts_fresh()
        accounts = list(mt5app.ACCOUNTS or [])
    except Exception as exc:
        _log(f"khong nap accounts: {exc}")
        return

    with watch_state.state_lock:
        state = watch_state.load_state()
        for account in accounts:
            name = account.get("name") or "?"
            try:
                with lock:
                    mt5app.connect_mt5(account, quiet=True)
                    try:
                        _process_account_deals(account, state)
                    finally:
                        try:
                            mt5.shutdown()
                        except Exception:
                            pass
            except Exception as exc:
                _log(f"deals {name}: {exc}")
        watch_state.save_state(state)


def run_once(lock):
    poll_timer_alerts(lock)
    poll_modify_if(lock)
    poll_deals(lock)


def _loop(lock):
    _log(f"bat dau watcher (moi {WATCH_INTERVAL_SEC}s) — Timer + modify-if + TP/SL/pending")
    while True:
        try:
            # Lock chỉ quanh từng lần connect MT5 — không khóa cả chu kỳ.
            run_once(lock)
        except Exception:
            _log("loi watcher:\n" + traceback.format_exc())
        time.sleep(WATCH_INTERVAL_SEC)


def start_watcher(lock):
    """Start thread daemon một lần. lock = threading.Lock dùng chung với API."""
    global _started, _thread
    if _started:
        return False
    _started = True
    _thread = threading.Thread(target=_loop, args=(lock,), name="mt5-watch", daemon=True)
    _thread.start()
    return True
