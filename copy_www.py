# =============================================================================
# Copy UI web sang WAMP
# =============================================================================
#
# Không đặt tên file là copy.py — sẽ đè module chuẩn `copy` của Python
# (Flask/Werkzeug cần `from copy import deepcopy` → API không chạy được).
#
# Chuyển nội dung folder mt5/ và/hoặc setup/ vào D:\wamp64\www
# (giữ nguyên tên thư mục: ...\www\mt5, ...\www\setup).
# Folder đích được xóa sạch trước khi copy, không để lại file cũ.
#
#   python copy_www.py              # copy cả mt5 và setup
#   python copy_www.py mt5          # chỉ mt5
#   python copy_www.py setup        # chỉ setup
#   python copy_www.py mt5 setup    # cả hai (tường minh)
#   python copy_www.py --dest E:\www
#
# =============================================================================

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
DEFAULT_DEST = Path(r"D:\wamp64\www")
KNOWN_APPS = ("mt5", "setup")
SKIP_DIR_NAMES = {"__pycache__", ".git"}


def clear_dir(path: Path) -> None:
    """Xóa hết nội dung folder đích rồi tạo lại rỗng."""
    if path.exists():
        shutil.rmtree(path)
        print(f"  đã xóa folder cũ: {path}")
    path.mkdir(parents=True, exist_ok=True)


def copy_tree(src: Path, dest: Path) -> int:
    """Copy đè file; trả về số file đã copy."""
    count = 0
    dest.mkdir(parents=True, exist_ok=True)
    for path in src.rglob("*"):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        rel = path.relative_to(src)
        target = dest / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        count += 1
        print(f"  {rel.as_posix()}")
    return count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy folder mt5/ hoặc setup/ vào thư mục WAMP www.",
    )
    parser.add_argument(
        "apps",
        nargs="*",
        choices=KNOWN_APPS,
        help="mt5 và/hoặc setup. Bỏ trống = copy cả hai.",
    )
    parser.add_argument(
        "--dest",
        default=str(DEFAULT_DEST),
        help=rf"Thư mục đích (mặc định: {DEFAULT_DEST})",
    )
    args = parser.parse_args()

    apps = list(args.apps) or list(KNOWN_APPS)
    dest_root = Path(args.dest)

    if not dest_root.parent.exists() and not dest_root.exists():
        print(f"Không tìm thấy thư mục đích: {dest_root}", file=sys.stderr)
        return 1

    dest_root.mkdir(parents=True, exist_ok=True)

    total = 0
    for name in apps:
        src = ROOT / name
        dest = dest_root / name
        if not src.is_dir():
            print(f"Bỏ qua {name}: không có folder {src}", file=sys.stderr)
            continue
        print(f"{src}  ->  {dest}")
        clear_dir(dest)
        n = copy_tree(src, dest)
        print(f"  ({n} file)\n")
        total += n

    if total == 0:
        print("Không copy được file nào.", file=sys.stderr)
        return 1

    print(f"Xong. Tong {total} file -> {dest_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
