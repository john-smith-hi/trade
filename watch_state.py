# =============================================================================
# Trạng thái watcher MT5 — khử trùng Telegram (xml/mt5_watch.xml)
# =============================================================================

from pathlib import Path
import threading
import xml.etree.ElementTree as ET

XML_DIR = Path(__file__).with_name("xml")
WATCH_FILE = XML_DIR / "mt5_watch.xml"

_lock = threading.Lock()
_MAX_IDS = 400


def _parse_id_list(text):
    out = []
    seen = set()
    for part in (text or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            num = int(part)
        except ValueError:
            continue
        if num in seen:
            continue
        seen.add(num)
        out.append(num)
    return out


def _join_ids(values):
    items = []
    seen = set()
    for value in values or []:
        try:
            num = int(value)
        except (TypeError, ValueError):
            continue
        if num in seen:
            continue
        seen.add(num)
        items.append(num)
    if len(items) > _MAX_IDS:
        items = items[-_MAX_IDS:]
    return ",".join(str(i) for i in items)


def _empty_state():
    return {
        "notified_deals": [],
        "skip_open_orders": [],
        "accounts": {},
    }


def _empty_account():
    return {
        "seeded": False,
        "pending": [],
        "positions": [],
    }


def load_state():
    XML_DIR.mkdir(parents=True, exist_ok=True)
    if not WATCH_FILE.exists():
        return _empty_state()
    try:
        root = ET.parse(WATCH_FILE).getroot()
    except ET.ParseError:
        return _empty_state()

    state = _empty_state()
    state["notified_deals"] = _parse_id_list(root.findtext("notified_deals"))
    state["skip_open_orders"] = _parse_id_list(root.findtext("skip_open_orders"))
    for node in root.findall("accounts/account"):
        name = (node.get("name") or "").strip()
        if not name:
            continue
        seeded = (node.get("seeded") or "").strip().lower() in ("1", "true", "yes")
        state["accounts"][name] = {
            "seeded": seeded,
            "pending": _parse_id_list(node.findtext("pending")),
            "positions": _parse_id_list(node.findtext("positions")),
        }
    return state


def save_state(state):
    XML_DIR.mkdir(parents=True, exist_ok=True)
    data = state or _empty_state()
    root = ET.Element("mt5_watch")
    ET.SubElement(root, "notified_deals").text = _join_ids(data.get("notified_deals"))
    ET.SubElement(root, "skip_open_orders").text = _join_ids(data.get("skip_open_orders"))
    accounts_node = ET.SubElement(root, "accounts")
    for name, acc in (data.get("accounts") or {}).items():
        node = ET.SubElement(accounts_node, "account", {
            "name": str(name),
            "seeded": "true" if acc.get("seeded") else "false",
        })
        ET.SubElement(node, "pending").text = _join_ids(acc.get("pending"))
        ET.SubElement(node, "positions").text = _join_ids(acc.get("positions"))
    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")
    tree.write(WATCH_FILE, encoding="UTF-8", xml_declaration=True)


def _append_id(items, ticket):
    try:
        num = int(ticket)
    except (TypeError, ValueError):
        return items
    items = list(items or [])
    if num not in items:
        items.append(num)
    if len(items) > _MAX_IDS:
        items = items[-_MAX_IDS:]
    return items


def remember_deal(ticket):
    if ticket in (None, ""):
        return
    with _lock:
        state = load_state()
        state["notified_deals"] = _append_id(state.get("notified_deals"), ticket)
        save_state(state)


def remember_skip_open_order(order_ticket):
    if order_ticket in (None, ""):
        return
    with _lock:
        state = load_state()
        state["skip_open_orders"] = _append_id(state.get("skip_open_orders"), order_ticket)
        save_state(state)


def add_pending_ticket(account_name, order_ticket):
    name = str(account_name or "").strip()
    if not name or order_ticket in (None, ""):
        return
    with _lock:
        state = load_state()
        acc = state["accounts"].setdefault(name, _empty_account())
        acc["pending"] = _append_id(acc.get("pending"), order_ticket)
        save_state(state)


def is_deal_notified(state, ticket):
    try:
        num = int(ticket)
    except (TypeError, ValueError):
        return False
    return num in set(state.get("notified_deals") or [])


def is_skip_open_order(state, order_ticket):
    try:
        num = int(order_ticket)
    except (TypeError, ValueError):
        return False
    return num in set(state.get("skip_open_orders") or [])


def account_state(state, account_name):
    name = str(account_name or "").strip()
    acc = (state.get("accounts") or {}).get(name)
    if acc is None:
        acc = _empty_account()
        state.setdefault("accounts", {})[name] = acc
    return acc


def mark_deal(state, ticket):
    state["notified_deals"] = _append_id(state.get("notified_deals"), ticket)


state_lock = _lock
append_id = _append_id
