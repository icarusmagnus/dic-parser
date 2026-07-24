"""dic_parser — extraction de DIC / KID PRIIPs (EPT structuré + PDF).

    from dic_parser import parse_document, parse_ept, parse_kid_pdf

    kid = parse_kid_pdf("samples/amundi.pdf")   # -> KIDData
    kids = parse_ept("samples/feed.xlsx")        # -> list[KIDData]
"""
from pathlib import Path

from .models import KIDData, CostBreakdown, PerformanceScenario
from .ept import parse_ept
from .kid_pdf import parse_kid_pdf

__all__ = ["KIDData", "CostBreakdown", "PerformanceScenario",
           "parse_ept", "parse_kid_pdf", "parse_document"]


def parse_document(path):
    """Aiguillage automatique EPT vs PDF selon l'extension."""
    ext = Path(path).suffix.lower()
    if ext in (".xlsx", ".xlsm", ".csv"):
        return parse_ept(path)
    if ext == ".pdf":
        return parse_kid_pdf(path)
    raise ValueError(f"Extension non gérée : {ext}")
