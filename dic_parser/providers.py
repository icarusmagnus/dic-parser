"""Règles par émetteur pour les DIC les plus courants (marché FR/LUX).

Le parser générique (kid_pdf.py) couvre ~80 % des cas. Cette couche gère les
particularités connues des gros émetteurs : phrasé différent, tableau de coûts
atypique, nom de produit à un endroit précis, etc.

Ajouter un émetteur = ajouter une entrée dans PROVIDERS. C'est le point
d'extension prévu, comme un module `dataSource` par source chez CHARLIE.
"""
from __future__ import annotations

import re
from typing import Optional, Callable

from .models import KIDData
from .utils import clean_ws, parse_pct


# Chaque émetteur : motifs de détection + libellé propre + hooks optionnels.
PROVIDERS: dict[str, dict] = {
    "amundi": {
        "detect": [r"\bAmundi\b", r"Amundi Asset Management", r"Amundi ETF", r"\bLyxor\b"],
        "name": "Amundi Asset Management",
    },
    "bnpp_am": {
        "detect": [r"BNP\s*Paribas\s*Asset\s*Management", r"BNPP?\s*AM", r"BNP Paribas Funds"],
        "name": "BNP Paribas Asset Management",
    },
    "axa_im": {
        "detect": [r"AXA\s*(Investment Managers|IM)", r"AXA World Funds"],
        "name": "AXA Investment Managers",
    },
    "natixis": {
        "detect": [r"Natixis\s*Investment Managers", r"\bOstrum\b", r"\bDNCA\b",
                   r"\bMirova\b", r"\bThematics\b", r"\bSeeyond\b"],
        "name": "Natixis Investment Managers",
    },
    "blackrock": {
        "detect": [r"\bBlackRock\b", r"\biShares\b", r"BGF ", r"BlackRock Global Funds"],
        "name": "BlackRock",
    },
    "dws": {
        "detect": [r"\bDWS\b", r"\bXtrackers\b", r"DWS Investment"],
        "name": "DWS / Xtrackers",
    },
    "jpmam": {
        "detect": [r"J\.?P\.?\s*Morgan\s*(Asset Management|AM)?", r"JPMorgan Funds", r"JPM "],
        "name": "J.P. Morgan Asset Management",
    },
    "carmignac": {
        "detect": [r"\bCarmignac\b"],
        "name": "Carmignac Gestion",
    },
    "pictet": {
        "detect": [r"\bPictet\b", r"Pictet Asset Management"],
        "name": "Pictet Asset Management",
    },
    "schroders": {
        "detect": [r"\bSchroder", r"Schroder International"],
        "name": "Schroders",
    },
    "fidelity": {
        "detect": [r"\bFidelity\b", r"FIL Investment", r"Fidelity Funds"],
        "name": "Fidelity International",
    },
    "rothschild": {
        "detect": [r"Rothschild\s*&\s*Co", r"\bR-co\b", r"Edmond de Rothschild"],
        "name": "Rothschild & Co Asset Management",
    },
    "lfde": {
        "detect": [r"Financière de l.?Échiquier", r"\bLFDE\b", r"Echiquier"],
        "name": "La Financière de l'Échiquier",
    },
    "comgest": {
        "detect": [r"\bComgest\b"],
        "name": "Comgest",
    },
    "mg": {
        "detect": [r"M&G\s*(Investments|Luxembourg)?", r"M&G \("],
        "name": "M&G Investments",
    },
    "sycomore": {
        "detect": [r"\bSycomore\b"],
        "name": "Sycomore Asset Management",
    },
}


def detect(text: str) -> Optional[str]:
    """Renvoie la clé d'émetteur détectée (ou None)."""
    for key, cfg in PROVIDERS.items():
        if any(re.search(p, text, re.I) for p in cfg["detect"]):
            return key
    return None


def manufacturer_name(provider: Optional[str]) -> Optional[str]:
    return PROVIDERS.get(provider, {}).get("name") if provider else None


def extract_product_name(text: str, provider: Optional[str]) -> Optional[str]:
    """Nom du produit : juste après 'Nom du produit' / 'Dénomination', sinon 1re ligne utile."""
    m = re.search(r"(?:Nom du produit|Dénomination|Produit)\s*:?\s*([^\n]{4,90})", text)
    if m:
        return clean_ws(m.group(1))
    # 1re ligne significative sous le titre "Document d'informations clés"
    m = re.search(r"[Dd]ocument d.?informations? clés?\s*\n+([^\n]{4,90})", text)
    if m:
        return clean_ws(m.group(1))
    return None


# ------------------------------------------------------------ hooks post-traitement
def _amundi(kid: KIDData, text: str, tables) -> None:
    # Amundi/Lyxor ETF : le nom inclut souvent "UCITS ETF"; frais parfois notés "TFE".
    if kid.costs.ongoing_costs is None:
        m = re.search(r"(?:TFE|Total des frais sur encours)\D{0,20}?(\d[.,]\d+)\s*%", text, re.I)
        if m:
            kid.costs.ongoing_costs = parse_pct(m.group(1))


def _blackrock(kid: KIDData, text: str, tables) -> None:
    # iShares : "Ongoing charges / Frais courants" parfois hors tableau de coûts PRIIPs.
    if kid.costs.ongoing_costs is None:
        m = re.search(r"[Ff]rais courants\D{0,20}?(\d[.,]\d+)\s*%", text)
        if m:
            kid.costs.ongoing_costs = parse_pct(m.group(1))


def _bnpp(kid: KIDData, text: str, tables) -> None:
    # BNPP AM : certains DIC listent "Coûts ponctuels" regroupant entrée+sortie.
    if kid.costs.entry_costs is None:
        m = re.search(r"[Cc]oûts?\s+ponctuels?\D{0,30}?(\d[.,]?\d*)\s*%", text)
        if m:
            kid.costs.entry_costs = parse_pct(m.group(1))


POST_HOOKS: dict[str, Callable] = {
    "amundi": _amundi,
    "blackrock": _blackrock,
    "bnpp_am": _bnpp,
}


def post_process(kid: KIDData, text: str, tables) -> None:
    hook = POST_HOOKS.get(kid.provider or "")
    if hook:
        hook(kid, text, tables)
