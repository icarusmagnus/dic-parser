"""CLI : parse un ou plusieurs DIC/EPT et sort du JSON.

    python -m dic_parser.cli samples/*.pdf
    python -m dic_parser.cli feed.xlsx --out resultats.json
"""
from __future__ import annotations

import argparse
import glob
import json
import sys

from . import parse_document
from .models import KIDData


def main(argv=None):
    ap = argparse.ArgumentParser(description="Parser DIC/KID PRIIPs (EPT + PDF)")
    ap.add_argument("paths", nargs="+", help="fichiers .pdf / .xlsx / .csv (globs OK)")
    ap.add_argument("--out", help="fichier JSON de sortie (défaut: stdout)")
    ap.add_argument("--min-completeness", type=float, default=0.0,
                    help="ignore les résultats sous ce taux de remplissage")
    args = ap.parse_args(argv)

    files = []
    for p in args.paths:
        files.extend(glob.glob(p))
    if not files:
        print("Aucun fichier.", file=sys.stderr)
        return 1

    results: list[dict] = []
    for f in files:
        try:
            res = parse_document(f)
            kids = res if isinstance(res, list) else [res]
            for k in kids:
                if k.completeness() >= args.min_completeness:
                    d = k.to_dict()
                    d["_completeness"] = k.completeness()
                    results.append(d)
        except Exception as e:  # noqa: BLE001 — on log et on continue le batch
            print(f"[ERREUR] {f}: {e}", file=sys.stderr)

    payload = json.dumps(results, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(payload)
        print(f"{len(results)} DIC -> {args.out}", file=sys.stderr)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
