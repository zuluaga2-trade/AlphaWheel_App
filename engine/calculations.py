# AlphaWheel Pro - Motor de cálculos (regla: máximo 2 decimales)
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

import config

DECIMALS = getattr(config, "PRECISION_DECIMALS", 2)


def round2(value):
    """Aplica la regla de precisión: máximo 2 decimales en todos los valores mostrados."""
    if value is None:
        return None
    try:
        v = float(value)
        return float(Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    except (TypeError, ValueError):
        return 0.0


def safe_float(val, default=0.0):
    """Convierte a float seguro; si falla devuelve default (redondeado a 2 decimales)."""
    if val is None:
        return round2(default)
    try:
        return round2(float(val))
    except (TypeError, ValueError):
        return round2(default)


def calculate_dte(exp_date) -> int:
    """Días hasta expiración. Si no hay fecha o ya expiró, devuelve 0."""
    if not exp_date or str(exp_date).strip() in ("None", "", "N/A"):
        return 0
    try:
        exp = datetime.strptime(str(exp_date).strip(), "%Y-%m-%d")
        return max(0, (exp.date() - datetime.now().date()).days)
    except (ValueError, TypeError):
        return 0


def calculate_breakeven(
    strike: float,
    premiums_received: float,
    contracts: int,
    is_put: bool,
    cost_basis_per_share: float = None,
) -> float:
    """
    Breakeven para una posición de opciones.

    CSP: BE = strike - (primas / (contratos * 100))
        (precio de la acción al que no ganas ni pierdes si te asignan)

    CC (Covered Call): si se pasa cost_basis_per_share (valor de compra neto por acción),
        BE = cost_basis_per_share - (primas / (contratos * 100))
        así se tiene en cuenta el precio de adquisición de las acciones y las primas
        recibidas (CC + roll-overs) para un BE real. Si no hay cost basis, se usa
        BE = strike + prima/acción (referencia al strike actual).
    """
    if not contracts or contracts <= 0:
        return round2(strike)
    premium_per_share = premiums_received / (contracts * 100)
    if is_put:
        be = strike - premium_per_share
    else:
        # Covered Call: BE real = coste neto por acción menos prima por acción
        if cost_basis_per_share is not None and cost_basis_per_share > 0:
            be = cost_basis_per_share - premium_per_share
        else:
            be = strike + premium_per_share
    return round2(be)


def calculate_annualized_return(roc_pct: float, dte: int) -> float:
    """
    Retorno anualizado en %: (porcentaje de retorno / días hasta expiración) * 365.
    roc_pct = porcentaje de retorno (ej. 2.5 para 2.5%). Si DTE <= 0, devuelve 0.
    """
    if dte is None or dte <= 0:
        return round2(0.0)
    try:
        ann = (float(roc_pct) / float(dte)) * 365.0
        return round2(ann)
    except (TypeError, ZeroDivisionError):
        return round2(0.0)


def realized_pnl_buyback(premium_received_total: float, buyback_debit: float) -> float:
    """
    P&L realizado al cerrar una opción (CSP/CC) por recompra.
    premium_received_total = prima total recibida al abrir (price * quantity * 100).
    buyback_debit = importe total pagado por recomprar la opción.
    Devuelve: prima recibida - débito (positivo = ganancia, negativo = pérdida).
    """
    return round2(safe_float(premium_received_total) - safe_float(buyback_debit))


def calculate_return_on_capital(return_usd: float, capital_used: float) -> float:
    """Retorno sobre capital (porcentaje): (return_usd / capital_used) * 100. Si capital_used <= 0, devuelve 0."""
    if capital_used is None or capital_used <= 0:
        return round2(0.0)
    try:
        roc = (float(return_usd) / float(capital_used)) * 100.0
        return round2(roc)
    except (TypeError, ZeroDivisionError):
        return round2(0.0)


def net_cost_basis(
    purchase_price: float,
    quantity: int,
    premiums_received: float,
    dividends_received: float,
    adjustments: float = 0.0,
) -> float:
    """
    Net Cost Basis para la rueda: precio de compra original menos primas y dividendos, más ajustes.
    Por acción: (total_cost - premiums - dividends + adjustments) / quantity.
    Devuelve el cost basis total (no por acción) redondeado a 2 decimales.
    """
    total_cost = safe_float(purchase_price) * int(quantity)
    net = total_cost - safe_float(premiums_received) - safe_float(dividends_received) + safe_float(adjustments)
    return round2(net)


def delta_approx_itm_otm(strike: float, spot: float, is_put: bool) -> str:
    """
    Aproximación semántica: ITM/OTM para mostrar en UI.
    Put: spot < strike => ITM (en riesgo); spot >= strike => OTM (ganador).
    Call: spot > strike => ITM (en riesgo); spot <= strike => OTM (ganador).
    """
    if is_put:
        return "ITM" if spot < strike else "OTM"
    return "ITM" if spot > strike else "OTM"
