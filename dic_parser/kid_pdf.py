"""Parser PDF du DIC PRIIPs (français) — chemin de secours quand pas d'EPT.

Le DIC a une structure RÉGLEMENTAIRE normalisée (rubriques imposées), ce qui
donne des ancres textuelles stables :

  - "Quels sont les risques..."  -> indicateur SRI 1..7
  - "Scénarios de performance"    -> Tendu / Défavorable / Intermédiaire / Favorable
  - "Coûts au fil du temps"       -> Coûts totaux + Incidence des coûts annuels (1 an / RHP)
  - "Composition des coûts"       -> entrée / sortie / récurrents / transaction / résultats
  - "Période de détention recommandée" -> RHP

La MISE EN PAGE, elle, varie par émetteur -> on combine :
  1) extraction de tableaux (pdfplumber) pour les grilles de coûts/scénarios ;
  2) regex sur le texte pour SRI, RHP, et fallback quand le tableau est illisible ;
  3) surcouche par émetteur (providers.py) pour les cas particuliers.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .models import KIDData, CostBreakdown, PerformanceScenario
from .utils import find_isin, parse_number, parse_pct, clean_ws
from . import providers

try:
    import pdfplumber
    _HAS_PDF = True
except ImportError:
    _HAS_PDF = False


SCENARIO_LABELS = {
    "tendu": "Tendu", "stress": "Tendu",
    "defavorable": "Défavorable", "défavorable": "Défavorable",
    "intermediaire": "Intermédiaire", "intermédiaire": "Intermédiaire",
    "favorable": "Favorable",
}


# ---------------------------------------------------------------- extraction brute
# Un DIC PRIIPs fait 2-3 pages. On plafonne : au-delà c'est un prospectus/brochure
# (parfois renvoyé par un portail), lent et inutile à parser en entier.
MAX_PAGES = 6


def _extract(path: Path) -> tuple[str, list[list[list]]]:
    """Retourne (texte, tableaux) des premières pages du PDF (cap MAX_PAGES)."""
    if not _HAS_PDF:
        raise RuntimeError("pdfplumber requis (pip install pdfplumber)")
    texts, tables = [], []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[:MAX_PAGES]:
            texts.append(page.extract_text() or "")
            for t in page.extract_tables():
                if t:
                    tables.append(t)
    return "\n".join(texts), tables


# ---------------------------------------------------------------- SRI
def extract_sri(text: str) -> Optional[int]:
    patterns = [
        r"classe de risque\s+(\d)\s+sur\s+7",
        r"classé[^.]{0,40}?(\d)\s+sur\s+7",
        r"indicateur[^.]{0,60}?niveau\s+(\d)",
        r"\b([1-7])\s*/\s*7\b",
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            v = int(m.group(1))
            if 1 <= v <= 7:
                return v
    return None


# ---------------------------------------------------------------- RHP
def extract_rhp(text: str) -> Optional[float]:
    patterns = [
        r"[Pp]ériode de détention recommandée\s*:?\s*(\d+[.,]?\d*)\s*an",
        r"détention recommandée[^.]{0,40}?(\d+[.,]?\d*)\s*an",
        r"recommandée\D{0,20}?(\d+)\s*an",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return parse_number(m.group(1))
    # Fallback : l'horizon des scénarios/coûts ("Si vous sortez après N ans")
    hits = [int(x) for x in re.findall(r"[Ss]i vous sortez\s+après\s+(\d+)\s*ans?", text)]
    if hits:
        return float(max(hits))
    return None


def extract_currency(text: str) -> Optional[str]:
    if re.search(r"\bEUR\b|euro", text, re.I):
        return "EUR"
    for cur in ("USD", "GBP", "CHF", "JPY"):
        if re.search(rf"\b{cur}\b", text):
            return cur
    return None


# ---------------------------------------------------------------- coûts (tableaux)
def _cell_pcts(cell) -> list[float]:
    if cell is None:
        return []
    out = []
    for m in re.finditer(r"-?\d[\d\s  .,]*\s*%", str(cell)):
        v = parse_pct(m.group(0))
        if v is not None:
            out.append(v)
    return out


def fill_costs_from_tables(cb: CostBreakdown, tables: list[list[list]]) -> CostBreakdown:
    """Bouche-trou : ne remplit QUE les champs encore vides après le texte.

    Le texte est prioritaire car, sur les DIC français, pdfplumber fabrique
    souvent de faux tableaux qui mélangent les lignes (source de valeurs erronées).
    """
    for table in tables:
        for row in table:
            joined = clean_ws(" ".join(str(c or "") for c in row)).lower()
            pcts = [v for c in row for v in _cell_pcts(c)]
            if not pcts:
                continue
            if ("incidence des coûts annuels" in joined) and cb.riy_rhp_pct is None:
                cb.riy_1y_pct, cb.riy_rhp_pct = pcts[0], pcts[-1]
    return cb


# --- outils d'extraction texte, calés sur le phrasé réglementaire réel ---
def _euros_after(text: str, label: str, n: int = 2) -> list[float]:
    """Montants en € qui suivent un libellé (ex. 'Coûts totaux 194€ 1 114€')."""
    m = re.search(label, text, re.I)
    if not m:
        return []
    window = text[m.end():m.end() + 60]
    vals = [parse_number(x) for x in re.findall(r"(\d[\d\s ]*)\s*(?:€|EUR)", window)]
    return [v for v in vals if v is not None][:n]


def _pct_window(text: str, anchor: str, before: int = 90, after: int = 40) -> Optional[float]:
    """% le plus proche d'une amorce (le % peut précéder OU suivre le libellé)."""
    m = re.search(anchor, text, re.I)
    if not m:
        return None
    lo = max(0, m.start() - before)
    seg = text[lo:m.end() + after]
    apos = m.start() - lo
    best, best_d = None, 1e9
    for mm in re.finditer(r"(-?\d[.,]?\d*)\s*%", seg):
        d = min(abs(mm.start() - apos), abs(mm.end() - apos))
        if d < best_d:
            best, best_d = mm.group(1), d
    return parse_number(best) if best else None


def extract_costs_from_text(text: str, cb: CostBreakdown) -> CostBreakdown:
    """Extraction principale — ancrée sur le libellé PRIIPs français réel."""
    text = re.sub(r"\s+", " ", text)   # aplatir : les phrases-ancres traversent les sauts de ligne

    def keep(cur, val):
        return cur if cur is not None else val

    # Frais de gestion / coûts récurrents : "Frais de gestion ... et autres coûts0,27%"
    if cb.ongoing_costs is None:
        m = re.search(r"[Ff]rais de gestion[^%\d]{0,40}?(\d[.,]?\d*)\s*%", text)
        cb.ongoing_costs = parse_number(m.group(1)) if m else None
    if cb.ongoing_costs is None:                              # libellé alternatif (valeur après)
        cb.ongoing_costs = _pct_window(text, r"[Cc]oûts? récurrents", before=0, after=60)

    # Coûts de transaction : ancre sur "coûts encourus" (couvre "lors de l'achat"
    # ET "lorsque nous achetons") ; le % précède le libellé -> fenêtre large à gauche.
    cb.transaction_costs = keep(cb.transaction_costs,
        _pct_window(text, r"co[uû]ts encourus", before=135, after=30))
    if cb.transaction_costs is None:                         # libellé en clair (valeur après)
        cb.transaction_costs = _pct_window(text, r"[Cc]oûts? de transaction", before=0, after=80)
    if cb.transaction_costs is None:                         # "ne facturons pas" => 0 %
        m = re.search(r"[Cc]oûts? de transaction[^%]{0,60}?(ne facturons pas|aucun co[uû]t)", text, re.I)
        if m:
            cb.transaction_costs = 0.0

    # Coûts d'entrée / sortie : le % prime ; sinon "ne facturons pas" => 0
    for attr, label, stop in (
        ("entry_costs", r"[Cc]oûts? d.?entrée", r"[Cc]oûts? de sortie|[Cc]oûts? récurrents|[Ff]rais de gestion"),
        ("exit_costs", r"[Cc]oûts? de sortie", r"[Cc]oûts? récurrents|[Ff]rais de gestion|[Cc]oûts? de transaction"),
    ):
        if getattr(cb, attr) is not None:
            continue
        m = re.search(label, text, re.I)
        if not m:
            continue
        win = text[m.end():m.end() + 320]
        win = re.split(stop, win)[0]            # ne pas déborder sur le poste suivant
        mm = re.search(r"(\d[.,]?\d*)\s*%", win)
        if mm:
            setattr(cb, attr, parse_number(mm.group(1)))
        elif re.search(r"ne facturons pas|aucun co[uû]t|\b0(?:[.,]0+)?\s*(?:€|EUR)\b", win, re.I):
            setattr(cb, attr, 0.0)

    # Commissions de performance / intéressement
    cb.performance_fees = keep(cb.performance_fees,
        _pct_window(text, r"[Cc]ommissions? (?:liées? aux résultats|de performance)"))
    cb.carried_interest = keep(cb.carried_interest,
        _pct_window(text, r"[Ii]ntéressement|carried interest"))

    # Vue "coûts au fil du temps" : Coûts totaux (€) + Incidence annuelle (%)
    euros = _euros_after(text, r"[Cc]oûts? totaux")
    if euros:
        cb.total_cost_1y_eur = euros[0]
        cb.total_cost_rhp_eur = euros[-1]
    m = re.search(r"[Ii]ncidence des co[uû]ts annuels[^\n]{0,50}", text)
    if m:
        pcts = [parse_number(x) for x in re.findall(r"(-?\d[.,]?\d*)\s*%", m.group(0))]
        pcts = [p for p in pcts if p is not None]
        if pcts:
            cb.riy_1y_pct = pcts[0]
            cb.riy_rhp_pct = pcts[-1]
    return cb


# ---------------------------------------------------------------- scénarios
def extract_scenarios(tables: list[list[list]], text: str) -> list[PerformanceScenario]:
    found: dict[str, PerformanceScenario] = {}
    for table in tables:
        for row in table:
            joined = clean_ws(" ".join(str(c or "") for c in row)).lower()
            for key, label in SCENARIO_LABELS.items():
                if key in joined:
                    pcts = [v for c in row for v in _cell_pcts(c)]
                    sc = found.get(label, PerformanceScenario(name=label))
                    if pcts:
                        sc.return_1y_pct = pcts[0]
                        sc.return_rhp_pct = pcts[-1]
                    found.setdefault(label, sc)
                    found[label] = sc
    return list(found.values())


# ---------------------------------------------------------------- orchestration
def parse_kid_pdf(path: str | Path) -> KIDData:
    path = Path(path)
    text, tables = _extract(path)

    provider = providers.detect(text)
    kid = KIDData(
        isin=find_isin(text),
        product_name=providers.extract_product_name(text, provider),
        manufacturer=providers.manufacturer_name(provider) or _guess_manufacturer(text),
        currency=extract_currency(text),
        sri=extract_sri(text),
        rhp_years=extract_rhp(text),
        recommended_investment=_extract_reco_amount(text),
        source_type="kid_pdf",
        source_ref=str(path),
        provider=provider,
        document_date=_extract_doc_date(text),
    )

    cb = extract_costs_from_text(text, CostBreakdown())   # texte = source primaire
    cb = fill_costs_from_tables(cb, tables)                # tableau = bouche-trou
    kid.costs = cb
    kid.scenarios = extract_scenarios(tables, text)

    # surcouche émetteur : corrige les cas particuliers connus
    providers.post_process(kid, text, tables)

    # journal de qualité (comme kidParsedAt : on trace ce qui a échoué)
    if kid.sri is None:
        kid.parse_warnings.append("SRI non détecté")
    if kid.costs.ongoing_costs is None and kid.costs.riy_rhp_pct is None:
        kid.parse_warnings.append("Coûts non détectés")
    if not kid.scenarios:
        kid.parse_warnings.append("Scénarios non détectés")
    return kid


def _extract_reco_amount(text: str) -> Optional[float]:
    m = re.search(r"investi[st]{1,2}ement\D{0,30}?(\d[\d\s]{3,})\s*(?:€|EUR)", text, re.I)
    if m:
        return parse_number(m.group(1))
    m = re.search(r"(10[\s ]?000)\s*(?:€|EUR)", text)
    return parse_number(m.group(1)) if m else None


def _extract_doc_date(text: str) -> Optional[str]:
    m = re.search(r"(\d{1,2})[/\s.-](\d{1,2})[/\s.-](20\d{2})", text)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    return None


def _guess_manufacturer(text: str) -> Optional[str]:
    # "Initiateur : X" ou "Initiateur du PRIIPS : …….KEREN FINANCE, agréé…"
    m = re.search(r"[Ii]nitiateur(?:\s+du\s+PRIIPS)?\s*:?[\s.…]*([A-ZÉÀ][\w &.\-']{3,60})", text)
    if not m:
        return None
    name = clean_ws(m.group(1))
    return re.split(r",|\(| agréé| est agréé", name)[0].strip() or None
