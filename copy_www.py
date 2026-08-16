# =============================================================================
# Copy UI web sang WAMP
# =============================================================================
#
# Không đặt tên file là copy.py — sẽ đè module chuẩn `copy` của Python
# (Flask/Werkzeug cần `from copy import deepcopy` → API không chạy được).
#
# Đường dẫn đích lấy từ xml/www.xml (gitignore). Chưa có thì copy từ
# xml/www.example.xml. Folder đích (mt5/, setup/) được xóa sạch trước khi copy.
#
#   python copy_www.py              # copy cả mt5 và setup
#   python copy_www.py mt5          # chỉ mt5
#   python copy_www.py setup        # chỉ setup
#   python copy_www.py mt5 setup    # cả hai (tường minh)
#   python copy_www.py --dest E:\www   # override xml/www.xml lần chạy này
#
# =============================================================================

from __future__ import annotations

import argparse
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
XML_DIR = ROOT / "xml"
WWW_FILE = XML_DIR / "www.xml"
WWW_EXAMPLE_FILE = XML_DIR / "www.example.xml"
KNOWN_APPS = ("mt5", "setup")
SKIP_DIR_NAMES = {"__pycache__", ".git"}


def load_www_path() -> Path:
    """Đọc path WAMP www từ xml/www.xml. Chưa có thì tạo từ example."""
    XML_DIR.mkdir(parents=True, exist_ok=True)
    if not WWW_FILE.exists():
        if not WWW_EXAMPLE_FILE.exists():
            raise RuntimeError(f"Thieu {WWW_EXAMPLE_FILE}")
        WWW_FILE.write_text(WWW_EXAMPLE_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Da tao {WWW_FILE} tu {WWW_EXAMPLE_FILE.name}")

    try:
        root = ET.parse(WWW_FILE).getroot()
    except ET.ParseError as exc:
        raise RuntimeError(f"File www.xml bi loi dinh dang: {exc}") from exc

    node = root.find("path")
    text = (node.text or "").strip() if node is not None else ""
    if not text:
        raise RuntimeError(f"Thieu <path> trong {WWW_FILE}")
    return Path(text)


def clear_dir(path: Path) -> None:
    """Xóa hết nội dung folder đích rồi tạo lại rỗng."""
    if path.exists():
        shutil.rmtree(path)
        print(f"  da xoa folder cu: {path}")
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
        description="Copy folder mt5/ hoac setup/ vao thu muc WAMP www (xml/www.xml).",
    )
    parser.add_argument(
        "apps",
        nargs="*",
        choices=KNOWN_APPS,
        help="mt5 va/hoac setup. Bo trong = copy ca hai.",
    )
    parser.add_argument(
        "--dest",
        default=None,
        help="Override path trong xml/www.xml cho lan chay nay.",
    )
    args = parser.parse_args()

    apps = list(args.apps) or list(KNOWN_APPS)
    try:
        dest_root = Path(args.dest) if args.dest else load_www_path()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not dest_root.parent.exists() and not dest_root.exists():
        print(f"Khong tim thay thu muc dich: {dest_root}", file=sys.stderr)
        return 1

    dest_root.mkdir(parents=True, exist_ok=True)

    total = 0
    for name in apps:
        src = ROOT / name
        dest = dest_root / name
        if not src.is_dir():
            print(f"Bo qua {name}: khong co folder {src}", file=sys.stderr)
            continue
        print(f"{src}  ->  {dest}")
        clear_dir(dest)
        n = copy_tree(src, dest)
        print(f"  ({n} file)\n")
        total += n

    if total == 0:
        print("Khong copy duoc file nao.", file=sys.stderr)
        return 1

    print(f"Xong. Tong {total} file -> {dest_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
