"""Tests unitaires du parsing — sans dépendre de vrais PDF.

On teste les briques d'extraction (SRI, RHP, coûts, nombres, ISIN) sur du texte
PRIIPs synthétique mais fidèle au libellé réglementaire réel, et le parser EPT
de bout en bout sur un CSV. Lancer :  pytest -q   (ou  python tests/test_extractors.py)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dic_parser.utils import parse_number, parse_pct, valid_isin, find_isin
from dic_parser.kid_pdf import extract_sri, extract_rhp, extract_costs_from_text
from dic_parser.models import CostBreakdown
from dic_parser import providers
from dic_parser.ept import parse_ept


# --- extrait de DIC réaliste (structure/phrasé PRIIPs FR post-2023) ---
DIC_AMUNDI = """
Document d'informations clés
Amundi MSCI World UCITS ETF - EUR (C)
ISIN : LU1681043599   Initiateur : Amundi Asset Management
Ce produit est un fonds indiciel coté (ETF). Devise : EUR.

Quels sont les risques et qu'est-ce que cela pourrait me rapporter ?
Indicateur de risque
Nous avons classé ce produit dans la classe de risque 4 sur 7, qui est une
classe de risque entre basse et moyenne.

Scénarios de performance
Tendu        Ce que vous pourriez obtenir après déduction des coûts   -45,2 %   -8,1 %
Défavorable  Rendement annuel moyen                                   -12,4 %   -1,3 %
Intermédiaire Rendement annuel moyen                                    5,6 %    6,2 %
Favorable    Rendement annuel moyen                                    28,9 %   12,7 %

Que va me coûter cet investissement ?
Coûts au fil du temps
Coûts totaux                         185 €     512 €
Incidence des coûts annuels          1,85 %    0,45 %

Composition des coûts
Coûts d'entrée                       0,00 %
Coûts de sortie                      0,00 %
Coûts récurrents                     0,38 %
Coûts de transaction                 0,05 %
Commissions liées aux résultats      0,00 %

Combien de temps dois-je le conserver ?
Période de détention recommandée : 5 ans
"""


def test_number_parsing():
    assert parse_number("1,85") == 1.85
    assert parse_number("1 234,56") == 1234.56
    assert parse_number("1,234.56") == 1234.56
    assert parse_number("10 000") == 10000
    assert parse_pct("0,38 %") == 0.38
    assert parse_number("n/a") is None


def test_isin_validation():
    assert valid_isin("LU1681043599")
    assert valid_isin("FR0010315770")
    assert not valid_isin("LU1681043598")   # mauvaise clé de contrôle
    assert not valid_isin("HELLO")
    assert find_isin("blah ISIN : LU1681043599 blah") == "LU1681043599"


def test_sri_rhp():
    assert extract_sri(DIC_AMUNDI) == 4
    assert extract_rhp(DIC_AMUNDI) == 5


def test_costs_from_text():
    cb = extract_costs_from_text(DIC_AMUNDI, CostBreakdown())
    assert cb.entry_costs == 0.0
    assert cb.transaction_costs == 0.05
    assert cb.ongoing_costs == 0.38


def test_provider_detection():
    assert providers.detect(DIC_AMUNDI) == "amundi"
    assert providers.manufacturer_name("blackrock") == "BlackRock"
    assert providers.detect("BNP Paribas Asset Management Funds") == "bnpp_am"


def test_ept_csv(tmp_path=None):
    # EPT minimal en CSV (séparateur ';', en-tête anglais standard FinDatEx)
    csv_text = (
        "ISIN;PRIIP name;Manufacturer;Currency;SRI;Recommended holding period (years);"
        "Ongoing costs;Entry cost;Transaction costs;RIY RHP\n"
        "FR0010315770;Carmignac Patrimoine A EUR;Carmignac Gestion;EUR;3;3;1,50;1,00;0,20;2,10\n"
        "LU1681043599;Amundi MSCI World;Amundi;EUR;4;5;0,38;0,00;0,05;0,45\n"
    )
    p = Path(__file__).resolve().parent.parent / "samples" / "_test_ept.csv"
    p.parent.mkdir(exist_ok=True)
    p.write_text(csv_text, encoding="utf-8")

    kids = parse_ept(p)
    assert len(kids) == 2
    by_isin = {k.isin: k for k in kids}
    carm = by_isin["FR0010315770"]
    assert carm.sri == 3
    assert carm.rhp_years == 3
    assert carm.costs.ongoing_costs == 1.50
    assert carm.costs.riy_rhp_pct == 2.10
    assert by_isin["LU1681043599"].costs.transaction_costs == 0.05
    p.unlink()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK  {name}")
    print("\nTous les tests passent.")
