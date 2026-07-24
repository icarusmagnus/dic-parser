"""Pipeline unifié : catalogue -> récupération DIC + ingestion EPT -> dataset JSON.

Produit `data/dic_data.json` (la donnée accessible, consommée par le dashboard).
Deux entrées :
  1. les DIC PDF récupérables par ISIN (Amundi, Vanguard, portails assureurs) ;
  2. tout fichier EPT déposé dans `data/ept_inbox/` (chemin propre pour les
     grandes maisons sans URL publique : iShares, JPMorgan, PIMCO…).

Lancer :  ./.venv/bin/python scripts/pipeline.py   (réseau requis pour la partie DIC)
Conçu pour tourner aussi en CI (GitHub Actions) sans intervention.
"""
import csv
import glob
import hashlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

# DIC_NETWORK=0 -> mode cache seul (génération locale instantanée depuis data/dic_corpus)
NETWORK = os.environ.get("DIC_NETWORK", "1") != "0"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dic_parser.fetch as F
from dic_parser.fetch import fetch_kid, source_url
from dic_parser.kid_pdf import parse_kid_pdf
from dic_parser.ept import parse_ept

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "data" / "top_funds.csv"
CORPUS = ROOT / "data" / "dic_corpus"
CARDIF_ISINS = ROOT / "data" / "cardif_isins.txt"
EPT_INBOX = ROOT / "data" / "ept_inbox"
OUT_JSON = ROOT / "data" / "dic_data.json"

# timeout court en CI pour ne pas bloquer sur les sources lentes
_orig = F._download
F._download = lambda url, timeout=8: _orig(url, timeout)


def _kid_fields(k):
    c = k.costs
    return dict(sri=k.sri, rhp_years=k.rhp_years, currency=k.currency,
                ongoing_costs=c.ongoing_costs, entry_costs=c.entry_costs,
                transaction_costs=c.transaction_costs, riy_rhp_pct=c.riy_rhp_pct,
                total_cost_rhp_eur=c.total_cost_rhp_eur,
                scenarios=len(k.scenarios), completeness=k.completeness(),
                warnings=k.parse_warnings, doc_date=k.document_date)


_SOURCE_FILTERS = {}
if CARDIF_ISINS.exists():
    _SOURCE_FILTERS["cardif"] = set(CARDIF_ISINS.read_text().split())

# Résultats du run précédent : permet de NE re-parser que les DIC nouveaux ou modifiés
# (le parsing pdfplumber est le coût dominant ; on le saute si le PDF est identique).
_PREV = {}
if OUT_JSON.exists():
    try:
        _PREV = {f["isin"]: f for f in json.loads(OUT_JSON.read_text()).get("funds", [])}
    except Exception:  # noqa: BLE001
        _PREV = {}

_REUSE_FIELDS = ("sri", "rhp_years", "currency", "ongoing_costs", "entry_costs",
                 "transaction_costs", "riy_rhp_pct", "total_cost_rhp_eur",
                 "scenarios", "completeness", "warnings", "doc_date")


def _from_dic(row):
    isin = row["isin"]
    path = fetch_kid(isin, dest_dir=CORPUS, network=NETWORK, source_filters=_SOURCE_FILTERS)
    rec = dict(row, source="", origin="", retrieved=False, dic_url="", pdf_sig="")
    if not path:
        return rec
    rec["source"] = path.name.split("_")[0]
    rec["retrieved"] = True
    # On ne réhéberge PAS le PDF : on lie vers l'URL source (dépôt léger).
    rec["dic_url"] = source_url(rec["source"], isin)
    try:
        rec["pdf_sig"] = hashlib.md5(path.read_bytes()).hexdigest()[:16]
    except Exception:  # noqa: BLE001
        rec["pdf_sig"] = ""

    prev = _PREV.get(isin)
    # PDF inchangé depuis le dernier run -> on réutilise le parsing (pas de pdfplumber)
    if (prev and rec["pdf_sig"] and prev.get("pdf_sig") == rec["pdf_sig"]
            and prev.get("completeness") is not None):
        for k in _REUSE_FIELDS:
            if k in prev:
                rec[k] = prev[k]
        rec["origin"] = "dic_pdf_cache"
        return rec

    rec["origin"] = "dic_pdf"
    try:
        rec.update(_kid_fields(parse_kid_pdf(path)))
    except Exception as e:  # noqa: BLE001
        rec["warnings"] = [f"PARSE_ERROR:{e}"]
    return rec


def _ept_index():
    """ISIN -> KIDData issu des EPT déposés dans data/ept_inbox/."""
    idx = {}
    for f in glob.glob(str(EPT_INBOX / "*")):
        if Path(f).suffix.lower() not in (".csv", ".xlsx", ".xlsm"):
            continue
        try:
            for k in parse_ept(f):
                if k.isin:
                    idx[k.isin] = k
        except Exception as e:  # noqa: BLE001
            print(f"[EPT] {Path(f).name}: {e}")
    return idx


def main():
    rows = list(csv.DictReader(open(CATALOG)))
    ept = _ept_index()

    # 1) DIC PDF (parallèle)
    with ThreadPoolExecutor(max_workers=24) as ex:
        recs = list(ex.map(_from_dic, rows))

    # 2) EPT en priorité/complément (données propres, notamment les coûts)
    for rec in recs:
        k = ept.get(rec["isin"])
        if k and (not rec["retrieved"] or (rec.get("completeness") or 0) < k.completeness()):
            rec.update(_kid_fields(k))
            rec["source"] = "ept-inbox"
            rec["origin"] = "ept"
            rec["retrieved"] = True

    retrieved = [r for r in recs if r["retrieved"]]
    comps = [r["completeness"] for r in retrieved if r.get("completeness") is not None]
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "catalog_size": len(rows),
        "retrieved": len(retrieved),
        "avg_completeness": round(sum(comps) / len(comps), 1) if comps else None,
        "sources": _count(retrieved, "source"),
        "companies_covered": len({r["company_group"] for r in retrieved}),
        "funds": recs,
    }
    # N'écrit que si le contenu a changé (hors horodatage) -> pas de commit inutile
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    prev = {}
    if OUT_JSON.exists():
        try:
            prev = json.loads(OUT_JSON.read_text())
        except Exception:  # noqa: BLE001
            prev = {}
    if {k: v for k, v in prev.items() if k != "generated_at"} != \
       {k: v for k, v in payload.items() if k != "generated_at"}:
        OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        print(f"[maj] {len(retrieved)}/{len(rows)} DIC | complétude {payload['avg_completeness']}% "
              f"| sources {payload['sources']}")
    else:
        print(f"[inchangé] {len(retrieved)}/{len(rows)} DIC — pas de réécriture")


def _count(items, key):
    out = {}
    for it in items:
        out[it[key]] = out.get(it[key], 0) + 1
    return out


if __name__ == "__main__":
    main()
