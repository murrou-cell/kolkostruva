"""Reduce a daily kolkostruva.bg open-data ZIP into compact static JSON artifacts."""
import csv, io, json, re, statistics, sys, zipfile
from collections import defaultdict

SIZE = re.compile(r"(?:(\d+)\s*[XХ]\s*)?(\d+(?:[.,]\d+)?)\s*(КГ|KG|ГР|Г|G|МЛ|ML|Л|L)\b", re.I)
UNIT = {"КГ": ("kg", 1), "KG": ("kg", 1), "ГР": ("kg", .001), "Г": ("kg", .001), "G": ("kg", .001),
        "МЛ": ("l", .001), "ML": ("l", .001), "Л": ("l", 1), "L": ("l", 1)}


def chain_name(fn):
    base = fn.rsplit("/", 1)[-1].rsplit("_", 1)[0]
    return base.split(" (")[0].strip()


def parse_size(name):
    m = SIZE.search(name)
    if not m:
        return None
    qty = float(m.group(2).replace(",", "."))
    mult = int(m.group(1)) if m.group(1) else 1
    unit, f = UNIT[m.group(3).upper()]
    return unit, qty * mult * f


def norm_code(c):
    c = c.strip()
    return c[-5:] if len(c) > 5 else c.zfill(5)


def make_row(chain, sku, a):
    med = round(statistics.median(a["p"]), 2)
    row = [chain, sku, a["n"], a["c"], round(min(a["p"]), 2), med, round(max(a["p"]), 2),
           round(min(a["promo"]), 2) if a["promo"] else None, len(a["p"])]
    sz = parse_size(a["n"])
    row.append(round(med / sz[1], 2) if sz and sz[1] > 0 else None)
    row.append(sz[0] if sz else None)
    return row


def reduce(zip_path, date, cities=False):
    prods = {}
    city_rows = defaultdict(dict)
    with zipfile.ZipFile(zip_path) as z:
        for fn in sorted(z.namelist()):
            if not fn.endswith(".csv"):
                continue
            chain = chain_name(fn)
            agg = defaultdict(lambda: {"p": [], "promo": [], "n": "", "c": ""})
            cagg = defaultdict(lambda: {"p": [], "promo": [], "n": "", "c": ""})
            data = z.read(fn)
            try:
                text = data.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = data.decode("cp1251", "replace")
            if True:
                head = text.split("\n", 1)[0]
                rd = csv.reader(io.StringIO(text, newline=""), delimiter=";" if head.count(";") > head.count(",") else ",", skipinitialspace=True)
                next(rd, None)
                for r in rd:
                    if len(r) < 7:
                        continue
                    try:
                        price = float(r[5].replace(",", "."))
                    except ValueError:
                        continue
                    if price <= 0:
                        continue
                    promo = 0
                    if r[6]:
                        try:
                            promo = float(r[6].replace(",", "."))
                        except ValueError:
                            pass
                    for a in ((agg[r[3]], cagg[(norm_code(r[0]), r[3])]) if cities else (agg[r[3]],)):
                        a["n"], a["c"] = r[2], r[4]
                        a["p"].append(price)
                        if promo > 0:
                            a["promo"].append(promo)
            for sku, a in agg.items():
                prods[(chain, sku)] = make_row(chain, sku, a)
            for (city, sku), a in cagg.items():
                city_rows[city][(chain, sku)] = make_row(chain, sku, a)
    cols = ["chain", "sku", "name", "cat", "min", "median", "max", "promo", "stores", "unit_price", "unit"]
    out = {"date": date, "cols": cols, "rows": list(prods.values())}
    if cities:
        out["cities"] = {c: {"date": date, "cols": cols, "rows": list(r.values())} for c, r in city_rows.items()}
    return out


if __name__ == "__main__":
    out = reduce(sys.argv[1], sys.argv[2])
    json.dump(out, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(len(out["rows"]), "products")
