"""Keep per-product price-change events and derive the price-changes list."""
import json, os, datetime

WINDOW = int(os.environ.get("TREND_DAYS", "14"))
MIN_PCT = float(os.environ.get("TREND_MIN_PCT", "0.02"))
MAX_PCT = 1.0
KEEP = 60


def _write(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def update(data_dir):
    hist_dir = os.path.join(data_dir, "history")
    path = os.path.join(data_dir, "hist.json")
    try:
        h = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        h = {"days": [], "ev": {}}
    days = sorted(f[:-5] for f in os.listdir(hist_dir) if f.endswith(".json"))
    for d in days:
        if h["days"] and d <= h["days"][-1]:
            continue
        for r in json.load(open(os.path.join(hist_dir, d + ".json"), encoding="utf-8"))["rows"]:
            ev = h["ev"].setdefault(f"{r[0]}|{r[1]}", [])
            if not ev or ev[-1][1] != r[5]:
                ev.append([d, r[5]])
        h["days"].append(d)
    if not h["days"]:
        return
    latest = h["days"][-1]
    cutoff = (datetime.date.fromisoformat(latest) - datetime.timedelta(days=KEEP)).isoformat()
    for ev in h["ev"].values():
        while len(ev) >= 2 and ev[1][0] <= cutoff:
            ev.pop(0)
    h["days"] = h["days"][-KEEP:]
    _write(path, h)
    start = (datetime.date.fromisoformat(latest) - datetime.timedelta(days=WINDOW)).isoformat()
    out = []
    for r in json.load(open(os.path.join(hist_dir, latest + ".json"), encoding="utf-8"))["rows"]:
        ev = h["ev"].get(f"{r[0]}|{r[1]}")
        if not ev or len(ev) < 2:
            continue
        ref = next((e for e in reversed(ev) if e[0] <= start), ev[0])
        if ref[1] <= 0 or ref[0] == ev[-1][0]:
            continue
        pct = (ev[-1][1] - ref[1]) / ref[1]
        if MIN_PCT <= abs(pct) <= MAX_PCT:
            out.append([r[0], r[1], r[2], r[3], ref[1], ev[-1][1], round(pct, 3), ev[-1][0]])
    out.sort(key=lambda x: -abs(x[6]))
    _write(os.path.join(data_dir, "changes.json"), {
        "date": latest, "window": WINDOW, "from": h["days"][max(0, len(h["days"]) - WINDOW - 1)],
        "cols": ["chain", "sku", "name", "cat", "old", "new", "pct", "changed"], "rows": out})
