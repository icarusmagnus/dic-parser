"""Petites fonctions de normalisation — le nerf de la guerre sur les DIC français.

Les DIC mélangent formats FR ("1,85 %", "10 000 €") et parfois EN ("1.85%").
Une extraction fiable dépend à 80 % d'un parsing de nombres qui ne se trompe pas.
"""
from __future__ import annotations

import re
from typing import Optional

# ISIN : 2 lettres pays + 9 alphanum + 1 chiffre de contrôle
ISIN_RE = re.compile(r"\b([A-Z]{2}[A-Z0-9]{9}[0-9])\b")


def valid_isin(code: str) -> bool:
    """Validation par l'algorithme de Luhn (norme ISO 6166)."""
    if not code or not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", code):
        return False
    digits = "".join(str(int(c, 36)) if c.isalpha() else c for c in code)
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


def find_isin(text: str) -> Optional[str]:
    for m in ISIN_RE.finditer(text or ""):
        if valid_isin(m.group(1)):
            return m.group(1)
    return None


def parse_number(raw: str) -> Optional[float]:
    """Convertit un nombre écrit à la française ou à l'anglaise en float.

    "1,85" -> 1.85 ; "1 234,56" -> 1234.56 ; "1,234.56" -> 1234.56 ; "10 000" -> 10000
    """
    if raw is None:
        return None
    s = str(raw).strip()
    s = s.replace(" ", "").replace(" ", "").replace(" ", "")
    s = s.replace("€", "").replace("%", "").replace("EUR", "")
    if not s or not re.search(r"\d", s):
        return None
    has_comma, has_dot = "," in s, "." in s
    if has_comma and has_dot:
        # le dernier séparateur rencontré est le séparateur décimal
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif has_comma:
        # virgule seule = décimale FR (sauf si elle sert de séparateur de milliers)
        if re.fullmatch(r"\d{1,3}(,\d{3})+", s):
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_pct(raw: str) -> Optional[float]:
    """Extrait le premier pourcentage d'une chaîne. '1,85 %' -> 1.85"""
    if raw is None:
        return None
    m = re.search(r"-?\d[\d\s  .,]*\s*%", str(raw))
    if m:
        return parse_number(m.group(0))
    return parse_number(raw)


def clean_ws(text: str) -> str:
    return re.sub(r"[ \t  ]+", " ", (text or "")).strip()
