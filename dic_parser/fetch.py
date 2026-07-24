"""Récupération d'un DIC à partir d'un simple ISIN.

Plusieurs émetteurs/assureurs exposent le DIC via une URL construite à partir
de l'ISIN. On essaie les sources connues dans l'ordre, on garde le premier PDF
valide. C'est le maillon qui règle « je n'ai aucun DIC » : tu donnes des ISIN,
tu récupères les documents automatiquement.

    from dic_parser.fetch import fetch_kid, fetch_and_parse
    path = fetch_kid("FR0007061379")          # -> samples/... .pdf (ou None)
    kid  = fetch_and_parse("FR0007061379")     # télécharge + parse -> KIDData

CLI :
    python -m dic_parser.fetch FR0007061379 LU1681043599 --out samples/ --parse
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from .utils import valid_isin

# Sources connues : (nom, fabrique-URL(s) depuis l'ISIN).
# La fabrique renvoie une URL ou une LISTE d'URL candidates (essayées dans l'ordre).
# Ordre des sources = priorité. Ajouter une source = une ligne.
#   - amundi/vanguard  : émetteurs à URL templatée par ISIN (couvrent leurs propres fonds)
#   - predica/suravenir: portails assureurs (couvrent les fonds de LEUR univers d'UC, multi-maisons)
# Émetteurs SANS URL propre (iShares, Xtrackers, BNPP, Franklin…) : slug requis -> passer par
# leur portail ou fundinfo. À câbler au cas par cas.
SOURCES: list[tuple[str, Callable[[str], object]]] = [
    ("amundi",    lambda i: f"https://www.amundi.fr/fr_instit/dl/doc/kid-priips/{i}/FRA/FRA"),
    ("vanguard",  lambda i: [f"https://fund-docs.vanguard.com/{i.lower()}_priipskid_fr.pdf",
                             f"https://fund-docs.vanguard.com/{i.lower()}_priipskid_en.pdf"]),
    ("predica",   lambda i: f"https://priips.predica.com/credit-agricole/DIS_{i}.pdf"),
    # Cardif (BNP Paribas) : gros hub multi-maisons. Le portail Liferay expose en fait
    # une URL propre via le repository PRIIPs amfinesoft (clé publique du portail Cardif).
    # Si la clé cesse de marcher, la re-scraper sur document-information-cle.cardif.fr
    # (colonne datatable "documentUrl") — voir historique git scripts/probe_cardif.py.
    ("cardif",    lambda i: f"https://epr.amfinesoft.com/api/v1/download/CARDIF/underlying/kid/{i}/lang/fr?key={_CARDIF_KEY}"),
    # --- Autres clients amfinesoft (repository PRIIPs, 50+ assureurs) ---
    # amfinesoft = le fournisseur derrière Cardif. Chaque client = un univers d'UC
    # DISJOINT (0 recouvrement entre eux). Non activés dans le bulk car ils ne
    # couvrent pas les manquants du top-1000 actuel (parts institutionnelles), et
    # les solliciter × chaque miss ralentit le run. À activer si le catalogue change
    # ou pour une couverture plus large :
    # ("sogecap",  lambda i: f"https://epr.amfinesoft.com/api/v1/download/SOGECAP/underlying/kid/{i}/lang/fr?key=7pPlB7HoeaCTjsHOsYGA87RfJcmpSQ"),
    # ("axa-we",   lambda i: f"https://epr.amfinesoft.com/api/v1/download/AXA-WEALTH-EUROPE/underlying/kid/{i}/lang/fr"),
    # ("amfine",   lambda i: f"https://epr.amfinesoft.com/api/v1/download/underlying/kid/{i}/lang/fr"),  # générique, sans clé
    # Suravenir retiré du bulk : lent + renvoie des prospectus (0 DIC valide à l'échelle).
    # ("suravenir", lambda i: f"https://espaceclient.suravenir.fr/o/documents/WsPUS/DocFicheAMF/{i}.pdf"),
]

# Clé publique du portail Cardif (visible dans son datatable). Si elle cesse de
# marcher : la re-scraper via l'API filter de document-information-cle.cardif.fr
# (colonne "documentUrl"). Voir historique git scripts/probe_cardif.py.
_CARDIF_KEY = "QGMGiLdrUa0v5O2FCGkmIF7yhcMOJO"

_UA = "Mozilla/5.0 (compatible; dic-parser/1.0; +regulatory-doc-fetch)"
_MIN_BYTES = 3000        # en-dessous, c'est une page d'erreur, pas un DIC
_MAX_BYTES = 4_000_000   # au-dessus, c'est un prospectus (pas un DIC) : on coupe le téléchargement


def _download(url: str, timeout: int = 25) -> Optional[bytes]:
    try:
        req = Request(url, headers={"User-Agent": _UA})
        with urlopen(req, timeout=timeout) as r:
            # lecture bornée : évite d'aspirer un prospectus de centaines de pages
            data = r.read(_MAX_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        return None
    if len(data) > _MAX_BYTES:
        return None          # trop gros pour être un DIC
    if len(data) >= _MIN_BYTES and data[:5].startswith(b"%PDF"):
        return data
    return None


# Marqueurs réglementaires d'un DIC PRIIPs (FR + EN) et longueur max plausible.
_DIC_MARKERS = ("informations clés", "indicateur de risque",
                "période de détention recommandée", "key information document")
_MAX_DIC_PAGES = 12


def is_dic_pdf(path: Path) -> bool:
    """Écarte les prospectus (centaines de pages) renvoyés par certains portails.

    Contrôle CHEAP par comptage de pages sur les octets bruts (pas de pdfplumber :
    à l'échelle de milliers de DIC, ouvrir pdfplumber ici doublerait le coût CPU).
    La borne de 4 Mo au téléchargement bloque déjà les très gros fichiers ; ce
    garde-fou attrape les prospectus légers mais longs. En cas de doute -> on garde.
    """
    import re as _re
    try:
        data = path.read_bytes()
    except Exception:  # noqa: BLE001
        return True
    # nombre d'objets Page (hors /Pages). Fiable pour la plupart des PDF non compressés en flux d'objets.
    pages = len(_re.findall(rb"/Type\s*/Page[^s]", data))
    if pages == 0:  # xref/objstm compressé : on ne peut pas compter -> ne pas rejeter
        return True
    return pages <= _MAX_DIC_PAGES


def fetch_kid(isin: str, dest_dir: str | Path = "samples",
              sources=SOURCES, verbose: bool = False, use_cache: bool = True,
              network: bool = True, source_filters: Optional[dict] = None) -> Optional[Path]:
    """Télécharge le DIC de l'ISIN via la 1re source qui répond. Renvoie le chemin ou None.

    Cache : si un DIC pour cet ISIN est déjà présent dans dest_dir, on le réutilise
    sans requête réseau (re-runs instantanés, CI incrémentale). use_cache=False force.
    """
    isin = isin.strip().upper()
    if not valid_isin(isin):
        if verbose:
            print(f"  ✗ ISIN invalide : {isin}")
        return None
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    if use_cache:
        cached = sorted(dest_dir.glob(f"*_{isin}.pdf"))
        if cached:
            if verbose:
                print(f"  ⤷ {isin} (cache) {cached[0].name}")
            return cached[0]
    if not network:            # mode cache-seul : pas de requête réseau
        return None
    for name, make_url in sources:
        # pré-filtre : si on connaît l'univers d'une source, ne pas la solliciter
        # pour un ISIN qu'elle ne couvre pas (évite des requêtes inutiles à l'échelle)
        if source_filters and name in source_filters and isin not in source_filters[name]:
            continue
        urls = make_url(isin)
        if isinstance(urls, str):
            urls = [urls]
        for url in urls:
            data = _download(url)
            if data:
                out = dest_dir / f"{name}_{isin}.pdf"
                out.write_bytes(data)
                if not is_dic_pdf(out):          # prospectus / doc non-DIC -> on rejette
                    out.unlink()
                    if verbose:
                        print(f"  · {name} : document renvoyé n'est pas un DIC (rejeté)")
                    continue
                (dest_dir / f"{out.name}.url").write_text(url)   # trace l'URL source officielle
                if verbose:
                    print(f"  ✓ {isin} via {name} ({len(data)//1024} Ko) -> {out}")
                return out
        if verbose:
            print(f"  · {name} : pas de DIC")
    if verbose:
        print(f"  ✗ {isin} : introuvable sur les sources connues")
    return None


def source_url(name: str, isin: str) -> str:
    """URL publique canonique d'un DIC pour (source, ISIN).

    Sert à LIER vers le document d'origine depuis le dashboard, sans le réhéberger
    (évite d'alourdir le dépôt git). Prend la 1re URL candidate de la source.
    """
    for n, make_url in SOURCES:
        if n == name:
            u = make_url(isin)
            return u[0] if isinstance(u, list) else u
    return ""


def fetch_and_parse(isin: str, dest_dir: str | Path = "samples"):
    """Télécharge puis parse. Renvoie KIDData, ou None si non trouvé."""
    from .kid_pdf import parse_kid_pdf
    path = fetch_kid(isin, dest_dir)
    return parse_kid_pdf(path) if path else None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Récupère des DIC par ISIN")
    ap.add_argument("isins", nargs="+", help="un ou plusieurs ISIN")
    ap.add_argument("--out", default="samples", help="dossier de destination")
    ap.add_argument("--parse", action="store_true", help="parse aussi et affiche un résumé")
    args = ap.parse_args(argv)

    ok = 0
    for isin in args.isins:
        path = fetch_kid(isin, args.out, verbose=True)
        if not path:
            continue
        ok += 1
        if args.parse:
            from .kid_pdf import parse_kid_pdf
            k = parse_kid_pdf(path)
            print(f"      SRI={k.sri} RHP={k.rhp_years} frais_gestion={k.costs.ongoing_costs}% "
                  f"transac={k.costs.transaction_costs}% complétude={k.completeness()}%")
    print(f"\n{ok}/{len(args.isins)} DIC récupérés.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
