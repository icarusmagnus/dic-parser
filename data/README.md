# Catalogue & corpus DIC — top 100 fonds du marché

## `top100_funds.csv` — le catalogue (durable)

Les **100 plus gros OPCVM/ETF par encours** distribués sur le marché FR/LUX,
issus du classement par AUM, **plafonné à 5 fonds par maison** pour couvrir les
compagnies les plus connues sans qu'une seule domine.

29 maisons : BlackRock/iShares, JPMorgan, PIMCO, Pictet, Vanguard, Fidelity,
Amundi, DWS/Xtrackers, Schroders, State Street, Natixis, BNP Paribas AM, HSBC,
Franklin Templeton, Invesco, UBS, Morgan Stanley, Goldman Sachs, AllianceBernstein…

Colonnes : `rank, company_group, company_raw, isin, name, type, aum_eur_millions, sfdr, srri`.
ISINs réels. Régénérable via le classement par encours.

## `dic_corpus_results.csv` — l'état de récupération + parsing

Pour chaque fonds du catalogue : quelle source a fourni le DIC, et les champs
parsés (`sri, rhp, ongoing, transaction, completeness, warnings`).

### Couverture réelle (au dernier run)

| | Fonds | DIC récupérés | Complétude moy. |
|---|---|---|---|
| **Récupérables auto.** | Amundi, Vanguard, + univers Crédit Agricole/Predica | **16** | **68 %** |
| Reste du top 100 | iShares, JPMorgan, PIMCO, Pictet, Fidelity, Schroders, DWS, Franklin, State Street, UBS… | 0 | — |

### Pourquoi seulement 16 en auto ?

Le DIC se récupère par ISIN **uniquement** chez les émetteurs à URL templatée
(Amundi, Vanguard) ou via un portail assureur pour les fonds de **son** univers
(Predica a apporté DNCA, Algebris…). Les autres grandes maisons —
qui dominent le top 100 par encours — exposent leurs DIC derrière une URL à
**slug** (pas l'ISIN seul) ou via **fundinfo** (accès contractuel). Il n'existe
pas d'URL publique par ISIN pour iShares, JPMorgan, PIMCO, etc.

⚠️ Piège écarté : le portail Suravenir renvoie le **prospectus complet** (700+
pages) pour les fonds hors de son set curé — le fetcher rejette désormais tout
PDF qui n'est pas un DIC (≤12 pages + marqueurs réglementaires).

### Pour couvrir les 84 restants

1. **Câbler fundinfo** (la plaque centrale, ~98 % de couverture) — accès pro/API.
2. **Résoudre les slugs** émetteur par émetteur (iShares/BlackRock, DWS…).
3. **Récupérer les EPT** auprès des SGP : structuré, propre, et couvre les coûts
   là où le PDF échoue (voir `dic_parser/ept.py`).
