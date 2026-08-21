# =============================================================================
# Tự cập nhật khi máy 1 chạy start_server.bat (TRADE_SERVER=1)
# =============================================================================
#
# Định kỳ: git fetch → nếu remote có commit mới → git pull --ff-only
# → kiểm tra cú pháp (compileall) → nếu lỗi: Telegram + rollback HEAD cũ, giữ API
# → nếu OK: copy_www.py → os._exit(0) để start_server.bat chạy lại api.py.
#
# Tắt: set TRADE_AUTO_UPDATE=0
# Chu kỳ giây: TRADE_UPDATE_SEC (mặc định 120)
#
# =============================================================================

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_INTERVAL_SEC = 120
FIRST_CHECK_DELAY_SEC = 20
TELEGRAM_DETAIL_MAX = 1500


def _log(message: str) -> None:
    now = time.strftime("%H:%M:%S")
    print(f"[Update {now}] {message}", flush=True)


def _git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _git_head() -> str:
    result = _git(["rev-parse", "HEAD"])
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


def _upstream_behind_count() -> int | None:
    """Số commit remote hơn local. None = chưa set upstream / lỗi git."""
    probe = _git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    if probe.returncode != 0:
        _log("Chua co upstream (git branch -u origin/...). Bo qua auto-update.")
        return None
    _git(["fetch", "--quiet"])
    counted = _git(["rev-list", "--count", "HEAD..@{u}"])
    if counted.returncode != 0:
        _log(f"Khong dem duoc commit moi: {(counted.stderr or counted.stdout).strip()}")
        return None
    try:
        return int((counted.stdout or "0").strip() or "0")
    except ValueError:
        return None


def _working_tree_dirty() -> bool:
    status = _git(["status", "--porcelain"])
    if status.returncode != 0:
        return True
    return bool((status.stdout or "").strip())


def _syntax_check() -> tuple[bool, str]:
    """compileall toàn bộ .py trong project. (ok, chi_tiet_loi)."""
    proc = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", "-f", str(ROOT)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    detail = ((proc.stderr or "") + "\n" + (proc.stdout or "")).strip()
    return proc.returncode == 0, detail


def _notify_syntax_fail(old_head: str, new_head: str, detail: str) -> None:
    try:
        import telegram_notify
    except Exception as exc:
        _log(f"Khong import telegram_notify: {exc}")
        return

    lines = [
        "May 1: git pull ve code loi cu phap — da rollback, API cu van chay.",
        f"HEAD cu: {old_head[:12] or '?'}",
        f"HEAD loi: {new_head[:12] or '?'}",
    ]
    if detail:
        clipped = detail if len(detail) <= TELEGRAM_DETAIL_MAX else detail[:TELEGRAM_DETAIL_MAX] + "\n..."
        lines.append(clipped)
    else:
        lines.append("(compileall that bai, khong co chi tiet stderr)")

    text = telegram_notify.build_message("UPDATE — LỖI CÚ PHÁP", lines)
    ok = telegram_notify.send_alert(text)
    if ok:
        _log("Da gui Telegram canh bao loi cu phap.")
    else:
        err = telegram_notify.last_send_error() or "unknown"
        _log(f"Gui Telegram that bai: {err}")


def _rollback(old_head: str) -> bool:
    if not old_head:
        _log("Khong rollback duoc — thieu old HEAD.")
        return False
    reset = _git(["reset", "--hard", old_head])
    if reset.returncode != 0:
        _log(f"git reset --hard that bai: {(reset.stderr or reset.stdout).strip()}")
        return False
    _log(f"Da rollback ve {old_head[:12]}.")
    return True


def apply_update_if_needed() -> bool:
    """
    Pull + kiểm tra cú pháp + copy_www nếu remote có code mới.
    True = cập nhật OK, caller nên thoát process để bat restart.
    False = không đổi / lỗi cú pháp đã rollback / bỏ qua.
    """
    if not (ROOT / ".git").exists():
        return False

    if _working_tree_dirty():
        _log("Bo qua git pull — working tree co thay doi local (status --porcelain).")
        return False

    behind = _upstream_behind_count()
    if behind is None or behind <= 0:
        return False

    old_head = _git_head()
    _log(f"Phat hien {behind} commit moi tren remote — git pull --ff-only ...")
    pull = _git(["pull", "--ff-only"])
    if pull.returncode != 0:
        _log(f"git pull that bai: {(pull.stderr or pull.stdout).strip()}")
        return False

    new_head = _git_head()
    _log("Kiem tra cu phap (python -m compileall) ...")
    ok, detail = _syntax_check()
    if not ok:
        _log("LOI CU PHAP sau git pull — rollback + Telegram.")
        _notify_syntax_fail(old_head, new_head, detail)
        _rollback(old_head)
        return False

    _log("Cu phap OK. copy_www.py ...")
    copied = subprocess.run(
        [sys.executable, str(ROOT / "copy_www.py")],
        cwd=str(ROOT),
    )
    if copied.returncode != 0:
        _log("copy_www.py that bai (API van restart de nap .py moi).")
    else:
        _log("copy_www xong.")

    _log("Thoat process — start_server.bat se chay lai api.py.")
    return True


def _loop(interval_sec: int) -> None:
    time.sleep(FIRST_CHECK_DELAY_SEC)
    while True:
        try:
            if apply_update_if_needed():
                os._exit(0)
        except Exception as exc:
            _log(f"loi: {type(exc).__name__}: {exc}")
        time.sleep(interval_sec)


def start_auto_update() -> bool:
    """Bật thread daemon. Chỉ gọi khi TRADE_SERVER=1."""
    if os.environ.get("TRADE_AUTO_UPDATE", "1").strip() in ("0", "false", "no", "off"):
        _log("Tat (TRADE_AUTO_UPDATE=0).")
        return False
    try:
        interval = int(os.environ.get("TRADE_UPDATE_SEC", str(DEFAULT_INTERVAL_SEC)))
    except ValueError:
        interval = DEFAULT_INTERVAL_SEC
    interval = max(30, interval)
    thread = threading.Thread(
        target=_loop,
        args=(interval,),
        name="trade-auto-update",
        daemon=True,
    )
    thread.start()
    _log(
        f"Bat auto git pull + compileall + copy_www moi {interval}s "
        f"(sau {FIRST_CHECK_DELAY_SEC}s kiem tra lan dau)."
    )
    return True
