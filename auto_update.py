# =============================================================================
# Tự cập nhật khi máy 1 chạy start_server.bat (TRADE_SERVER=1)
# =============================================================================
#
# Định kỳ: git fetch → nếu remote có commit mới → git pull --ff-only
# → copy_www.py → os._exit(0) để start_server.bat vòng loop chạy lại api.py.
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


def apply_update_if_needed() -> bool:
    """
    Pull + copy_www nếu remote có code mới.
    True = đã cập nhật, caller nên thoát process để bat restart.
    """
    if not (ROOT / ".git").exists():
        return False

    behind = _upstream_behind_count()
    if behind is None or behind <= 0:
        return False

    # Bỏ sửa local trên file tracked để pull luôn được (máy 1 = bản deploy).
    _git(["reset", "--hard", "HEAD"])
    _git(["clean", "-fd", "--", "*.pyc"])

    _log(f"Phat hien {behind} commit moi tren remote — git pull --ff-only ...")
    pull = _git(["pull", "--ff-only"])
    if pull.returncode != 0:
        _log(f"git pull that bai: {(pull.stderr or pull.stdout).strip()}")
        return False

    _log("copy_www.py ...")
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
        f"Bat auto git pull + copy_www moi {interval}s "
        f"(sau {FIRST_CHECK_DELAY_SEC}s kiem tra lan dau)."
    )
    return True
