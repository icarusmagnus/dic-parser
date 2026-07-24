# dic-parser — extraction de DIC / KID PRIIPs

Extrait les données réglementaires d'un DIC (Document d'Informations Clés / KID
PRIIPs) vers un schéma unifié : **SRI, période de détention, ventilation des coûts,
scénarios de performance**. Deux entrées, une sortie.

```
EPT (.xlsx/.csv)  ─┐
                   ├─►  parse_document()  ─►  KIDData  ─►  ta table `funds`
DIC (.pdf)        ─┘                          (JSON)
```

## Installation

```bash
pip install -r requirements.txt   # pdfplumber + openpyxl
python3 tests/test_extractors.py  # doit afficher "Tous les tests passent."
```

## Usage

```python
from dic_parser import parse_document, parse_kid_pdf, parse_ept
from dic_parser.fetch import fetch_kid, fetch_and_parse

kid  = parse_kid_pdf("samples/amundi_msci_world.pdf")   # -> KIDData
kids = parse_ept("feeds/generali_ept.xlsx")             # -> list[KIDData]

kid  = fetch_and_parse("FR0007061379")                  # télécharge par ISIN puis parse

print(kid.sri, kid.costs.ongoing_costs, kid.completeness())
```

### Récupérer un DIC à partir d'un ISIN (`fetch.py`)

Plusieurs émetteurs exposent le DIC via une URL construite depuis l'ISIN. Le
fetcher essaie les sources connues et garde le premier PDF valide :

```bash
python3 -m dic_parser.fetch FR0007061379 LU1681043599 --out samples --parse
```

Sources câblées : **Amundi**, **Predica/Crédit Agricole**, **Suravenir**. Pour en
ajouter une, une ligne dans `SOURCES` (`fetch.py`) : `(nom, lambda isin: url)`.

**Calibré sur de vrais DIC** (Amundi, Predica private equity, Suravenir/Keren) —
complétude 87–100 %. Les postes qui s'entrelacent dans le texte deux-colonnes
(entrée/transaction sur produits atypiques) restent le point faible : pour ceux-là,
l'**EPT** donne la valeur propre.

En ligne de commande :

```bash
python3 -m dic_parser.cli "samples/*.pdf" --out kids.json --min-completeness 40
```

## Les deux chemins — et lequel privilégier

| | EPT (`ept.py`) | PDF (`kid_pdf.py`) |
|---|---|---|
| Source | fichier structuré FinDatEx (SGP, fundinfo, agrégateurs) | le DIC PDF lui-même |
| Fiabilité | **élevée** (on lit des colonnes) | moyenne (regex + tableaux) |
| Couverture coûts | complète et normalisée | dépend de la mise en page émetteur |
| Quand l'utiliser | **par défaut, dès que tu peux l'obtenir** | secours, quand seul le PDF existe |

> Règle : **essaie l'EPT d'abord, tombe sur le PDF ensuite.** Le DIC PDF est
> *généré* à partir de l'EPT — parser l'EPT évite toute la fragilité du PDF.
> C'est très probablement ce que fait le `kidParsedAt` « propre » de CHARLIE.

## Ce qui est extrait (`KIDData`)

- **Identité** : isin, product_name, manufacturer, currency
- **Risque** : `sri` (1..7), `rhp_years` (période de détention recommandée)
- **Coûts** (`CostBreakdown`, en %) : entrée, sortie, récurrents, transaction,
  commissions de performance, carried interest + vue « coûts au fil du temps »
  (coût total & incidence annuelle / RIY à 1 an et à la RHP)
- **Scénarios** : Tendu / Défavorable / Intermédiaire / Favorable (rendement 1 an & RHP)
- **Traçabilité** : `source_type`, `provider`, `document_date`, `parse_warnings`,
  et `completeness()` — un taux de remplissage **honnête** (contrairement au
  `dataCompleteness=100` sur lignes vides de CHARLIE).

## Émetteurs gérés (détection + règles)

Amundi/Lyxor · BNP Paribas AM · AXA IM · Natixis (Ostrum/DNCA/Mirova) · BlackRock/iShares ·
DWS/Xtrackers · J.P. Morgan AM · Carmignac · Pictet · Schroders · Fidelity ·
Rothschild & Co / R-co · LFDE · Comgest · M&G · Sycomore.

Le générique couvre le reste. **Ajouter un émetteur** = une entrée dans
`PROVIDERS` (motifs de détection + nom) et, si besoin, un hook dans `POST_HOOKS`
pour ses particularités. C'est le point d'extension prévu.

## Où trouver les documents (le maillon amont)

Le parser suppose que tu as déjà le fichier. Pour l'alimenter, par ISIN :

1. **EPT** : espaces « pro/partenaires » des SGP, ou agrégateurs (fundinfo,
   Fundsquare, Quantalys, OPCVM360). Le circuit prévu — préfère-le.
2. **PDF DIC** : `site:<sgp>.com KID <ISIN>`, plaques fundinfo/Fundsquare
   (URL souvent construite à partir de l'ISIN), pages « documents réglementaires ».

## Limites (assumées)

- Un parser PDF 100 % générique n'existe pas : chaque gabarit émetteur diffère.
  D'où les `parse_warnings` + `completeness()` pour **tracer** ce qui a échoué
  plutôt que de prétendre à une couverture parfaite.
- Respecte les CGU des sources : les DIC sont des documents **publics et
  réglementaires**, mais l'accès aux EPT et aux plaques d'agrégateurs peut être
  contractuel. Voir la note juridique de l'analyse.
```
