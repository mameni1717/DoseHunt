"""Contrôles de cohérence : une teneur ou un prix suspect part en revue humaine, pas dans l'index."""
from __future__ import annotations

from typing import Optional

from .config import categories
from .models import ActiveContent, Format

MIN_CONFIDENCE_FOR_INDEX = 0.55


def check_active(ac: ActiveContent) -> Optional[str]:
    """Renvoie la raison du rejet, ou None si la teneur est plausible."""
    c = categories()[ac.category]
    if ac.basis == "per_100g":
        lo, hi = c.get("range", [0, 100])
        if not lo <= ac.amount <= hi:
            return f"{ac.amount:g} {ac.unit} pour 100 g hors fourchette [{lo}, {hi}]"
    else:
        rng = c.get("range_per_unit_mg") if ac.unit == "mg" and ac.category in ("creatine", "collagene", "glutamine") else c.get("range_per_unit")
        if rng:
            lo, hi = rng
            if not lo <= ac.amount <= hi:
                hint = ""
                if ac.unit == "mg" and lo <= ac.amount / 1000 <= hi:
                    hint = " (probable erreur d'unité sur la fiche : g au lieu de mg)"
                return f"{ac.amount:g} {ac.unit} par unité hors fourchette [{lo}, {hi}]{hint}"
    if ac.confidence < MIN_CONFIDENCE_FOR_INDEX:
        return f"confiance trop faible ({ac.confidence:.2f})"
    return None


def check_format(fmt: Format, basis: str) -> Optional[str]:
    if fmt.confidence == 0:
        return f"format illisible : « {fmt.raw} »"
    if basis == "per_100g" and fmt.total_grams is None:
        return f"poids net introuvable : « {fmt.raw} »"
    if basis == "per_unit" and fmt.total_units is None:
        return f"nombre d'unités introuvable : « {fmt.raw} »"
    if fmt.total_grams is not None and not 20 <= fmt.total_grams <= 15000:
        return f"poids net improbable : {fmt.total_grams:g} g"
    return None


def check_price_jump(previous: Optional[float], current: float) -> Optional[str]:
    """Une baisse de plus de 60 % d'un relevé à l'autre ressemble plus à une erreur qu'à une promo."""
    if previous and current < previous * 0.4:
        return f"prix passé de {previous:.2f} € à {current:.2f} € (-{(1 - current / previous) * 100:.0f} %)"
    return None
