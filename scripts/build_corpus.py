"""Récupère + parse les DIC du catalogue (data/top100_funds.csv) en parallèle.

    ./.venv/bin/python scripts/build_corpus.py

Écrit data/dic_corpus_results.csv (statut de récupération + champs parsés) et
range les PDF dans data/dic_corpus/. Réseau requis (lancer hors sandbox).
"""
import csv
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dic_parser.fetch as F
from dic_parser.fetch import fetch_kid
from dic_parser.kid_pdf import parse_kid_pdf

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "data" / "top100_funds.csv"
CORPUS = ROOT / "data" / "dic_corpus"
OUT = ROOT / "data" / "dic_corpus_results.csv"

# timeout court : la plupart des sources échouent vite, on ne veut pas bloquer
_orig = F._download
F._download = lambda url, timeout=6: _orig(url, timeout)


def work(row):
    isin = row["isin"]
    path = fetch_kid(isin, dest_dir=CORPUS)
    res = dict(row, source="", retrieved=0, sri="", rhp="", ongoing="",
               transaction="", completeness="", warnings="")
    if not path:
        return res
    res["source"] = path.name.split("_")[0]
    res["retrieved"] = 1
    try:
        k = parse_kid_pdf(path)
        res.update(sri=k.sri or "", rhp=k.rhp_years or "",
                   ongoing=k.costs.ongoing_costs if k.costs.ongoing_costs is not None else "",
                   transaction=k.costs.transaction_costs if k.costs.transaction_costs is not None else "",
                   completeness=k.completeness(), warnings="|".join(k.parse_warnings))
    except Exception as e:  # noqa: BLE001
        res["warnings"] = f"PARSE_ERROR:{e}"
    return res


def main():
    rows = list(csv.DictReader(open(CATALOG)))
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=24) as ex:
        results = list(ex.map(work, rows))
    results.sort(key=lambda r: int(r["rank"]))

    cols = ["rank", "company_group", "isin", "name", "type", "source",
            "retrieved", "sri", "rhp", "ongoing", "transaction", "completeness", "warnings"]
    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(results)

    got = [r for r in results if r["retrieved"]]
    from collections import Counter
    print(f"=== {len(got)}/{len(rows)} DIC récupérés en {round(time.time()-t0)}s ===")
    print("par source :", dict(Counter(r["source"] for r in got)))
    print("maisons récupérées :", dict(Counter(r["company_group"] for r in got)))
    print(f"\nDétail -> {OUT}")
    for r in got:
        print(f"  ✓ {r['rank']:>3} {r['isin']} {r['company_group']:16} {r['source']:9} "
              f"compl={r['completeness']}% SRI={r['sri']} frais={r['ongoing']}")


if __name__ == "__main__":
    main()
