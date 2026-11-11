"""Fetch new daily kolkostruva.bg ZIPs, reduce them and publish JSON under DATA_DIR."""
import json, os, sys, time, urllib.request, urllib.error, tempfile, datetime
from collections import Counter
from reduce import reduce

BASE = os.environ.get("SOURCE_BASE", "https://kolkostruva.bg/opendata_files")
DATA = os.environ.get("DATA_DIR", "/data")
KEEP_DAYS = int(os.environ.get("KEEP_DAYS", "90"))
BACKFILL = int(os.environ.get("BACKFILL_DAYS", "14"))
INTERVAL = int(os.environ.get("INTERVAL_SECONDS", "3600"))


def fetch(date, dest):
    req = urllib.request.Request(f"{BASE}/{date}.zip", headers={"User-Agent": "kolkostruva-mirror"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise


def write_atomic(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def write_cities(out, date):
    names = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ekatte.json"), encoding="utf-8"))
    cdir = os.path.join(DATA, "cities")
    os.makedirs(cdir, exist_ok=True)
    index = []
    for code, d in out["cities"].items():
        write_atomic(os.path.join(cdir, f"{code}.json"), d)
        name, area = names.get(code, [code, ""])
        index.append({"code": code, "name": name, "area": area, "products": len(d["rows"]), "chains": len({r[0] for r in d["rows"]})})
    for f in os.listdir(cdir):
        if f.endswith(".json") and f[:-5] not in out["cities"] and f != "index.json":
            os.remove(os.path.join(cdir, f))
    index.sort(key=lambda c: -c["products"])
    write_atomic(os.path.join(cdir, "index.json"), {"date": date, "cities": index})


def cities_current(date):
    try:
        return json.load(open(os.path.join(DATA, "cities", "index.json"), encoding="utf-8"))["date"] == date
    except (OSError, ValueError, KeyError):
        return False


def run_once():
    hist = os.path.join(DATA, "history")
    os.makedirs(hist, exist_ok=True)
    today = datetime.date.today()
    dates = [(today - datetime.timedelta(days=i)).isoformat() for i in range(BACKFILL)]
    for d in reversed(dates):
        out = os.path.join(hist, f"{d}.json")
        if os.path.exists(out):
            continue
        with tempfile.NamedTemporaryFile(suffix=".zip") as tmp:
            if not fetch(d, tmp.name):
                continue
            res = reduce(tmp.name, d, cities=True)
            cit = res.pop("cities")
            write_atomic(out, res)
            write_cities({"cities": cit}, d)
            print("ingested", d, flush=True)
    days = sorted(f[:-5] for f in os.listdir(hist) if f.endswith(".json"))
    for old in days[:-KEEP_DAYS]:
        os.remove(os.path.join(hist, f"{old}.json"))
    days = days[-KEEP_DAYS:]
    if days and not cities_current(days[-1]):
        with tempfile.NamedTemporaryFile(suffix=".zip") as tmp:
            if fetch(days[-1], tmp.name):
                write_cities(reduce(tmp.name, days[-1], cities=True), days[-1])
                print("cities rebuilt", days[-1], flush=True)
    if days:
        latest = json.load(open(os.path.join(hist, f"{days[-1]}.json"), encoding="utf-8"))
        write_atomic(os.path.join(DATA, "latest.json"), latest)
        write_atomic(os.path.join(DATA, "meta.json"), {"latest": days[-1], "days": days, "source": "КЗП, kolkostruva.bg/opendata"})
    return days[-1] if days else None


if __name__ == "__main__":
    while True:
        failed = False
        try:
            print("check ok, latest day:", run_once(), flush=True)
        except Exception as e:
            failed = True
            print("update failed, retry in 60s:", e, file=sys.stderr, flush=True)
        if "--once" in sys.argv:
            break
        time.sleep(min(INTERVAL, 60) if failed else INTERVAL)
