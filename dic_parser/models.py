"""Modèle de données unifié pour un DIC / KID PRIIPs.

Que la donnée vienne d'un EPT (structuré) ou d'un PDF (parsé), on la ramène
toujours à ce même schéma. C'est lui qui alimente ensuite ta table `funds`
(colonnes srri/sri, ongoingCharges, kidParsedAt, etc.).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class CostBreakdown:
    """Ventilation des coûts telle qu'imposée par le règlement PRIIPs.

    Toutes les valeurs sont des pourcentages annualisés (ex. 1.85 = 1,85 %),
    exprimés à la période de détention recommandée (RHP) sauf mention contraire.
    """
    entry_costs: Optional[float] = None            # Coûts d'entrée
    exit_costs: Optional[float] = None             # Coûts de sortie
    ongoing_costs: Optional[float] = None          # Coûts récurrents (frais de gestion)
    transaction_costs: Optional[float] = None      # Coûts de transaction du portefeuille
    performance_fees: Optional[float] = None        # Commissions liées aux résultats
    carried_interest: Optional[float] = None        # Intéressement (private equity)

    # Vue "coûts au fil du temps" du DIC :
    #  - "Coûts totaux" est un MONTANT en euros (cumul sur l'horizon)
    #  - "Incidence des coûts annuels" est le POURCENTAGE annuel (le RIY)
    # aux deux horizons standards du tableau (1 an et RHP).
    total_cost_1y_eur: Optional[float] = None
    total_cost_rhp_eur: Optional[float] = None
    riy_1y_pct: Optional[float] = None             # Incidence des coûts annuels à 1 an
    riy_rhp_pct: Optional[float] = None            # Incidence des coûts annuels à la RHP


@dataclass
class PerformanceScenario:
    """Un scénario de performance (Tendu / Défavorable / Intermédiaire / Favorable)."""
    name: str
    return_1y_pct: Optional[float] = None          # Rendement annuel moyen à 1 an
    return_rhp_pct: Optional[float] = None         # Rendement annuel moyen à la RHP
    amount_1y: Optional[float] = None              # Ce que vous pourriez obtenir à 1 an (€)
    amount_rhp: Optional[float] = None             # Ce que vous pourriez obtenir à la RHP (€)


@dataclass
class KIDData:
    isin: Optional[str] = None
    product_name: Optional[str] = None
    manufacturer: Optional[str] = None             # Initiateur / société de gestion
    currency: Optional[str] = None

    sri: Optional[int] = None                      # Indicateur synthétique de risque 1..7
    rhp_years: Optional[float] = None              # Période de détention recommandée
    recommended_investment: Optional[float] = None  # Montant d'investissement de référence (svt 10 000 €)

    costs: CostBreakdown = field(default_factory=CostBreakdown)
    scenarios: list[PerformanceScenario] = field(default_factory=list)

    # Traçabilité (comme le `dataSource` / `kidParsedAt` de CHARLIE)
    source_type: Optional[str] = None              # "ept" | "kid_pdf"
    source_ref: Optional[str] = None               # chemin fichier / URL
    provider: Optional[str] = None                 # émetteur détecté
    document_date: Optional[str] = None            # date du DIC (ISO) si trouvée
    parse_warnings: list[str] = field(default_factory=list)

    def completeness(self) -> float:
        """Taux de remplissage réel des champs financiers clés (0..100).

        Contrairement au `dataCompleteness` de CHARLIE, celui-ci ne compte que
        ce qui est *effectivement* rempli — pas 100 par défaut.
        """
        key = [
            self.sri, self.rhp_years,
            self.costs.ongoing_costs, self.costs.entry_costs,
            self.costs.transaction_costs, self.costs.total_cost_rhp_eur,
            self.costs.riy_rhp_pct,
            len(self.scenarios) or None,
        ]
        filled = sum(1 for v in key if v is not None)
        return round(100 * filled / len(key), 1)

    def to_dict(self) -> dict:
        return asdict(self)
