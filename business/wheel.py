# AlphaWheel Pro - Ciclo de vida de La Rueda y gestión de inventario
from datetime import date
from typing import List, Dict, Any, Optional

from database import db
from engine.calculations import round2, safe_float, net_cost_basis


def register_csp_opening(
    account_id: int,
    user_id: int,
    ticker: str,
    quantity: int,
    strike: float,
    premium: float,
    expiration_date: str,
    trade_date: str = None,
    comment: str = None,
    parent_trade_id: int = None,
) -> int:
    """Registra apertura de CSP (Cash-Secured Put). entry_type=OPENING. parent_trade_id enlaza con la pierna anterior (roll-over)."""
    trade_date = trade_date or str(date.today())
    return db.insert_trade(
        account_id=account_id,
        ticker=ticker,
        asset_type="OPTION",
        quantity=quantity,
        price=round2(premium),
        strike=round2(strike),
        expiration_date=expiration_date,
        strategy_type="CSP",
        status="OPEN",
        entry_type="OPENING",
        trade_date=trade_date,
        parent_trade_id=parent_trade_id,
        comment=comment,
    )


def register_assignment(
    account_id: int,
    user_id: int,
    parent_trade_id: int,
    ticker: str,
    quantity: int,
    assignment_price: float,
    trade_date: str = None,
    comment: str = None,
) -> int:
    """
    Registra asignación: Put expira ITM → se reciben acciones.
    Cierra el CSP (parent) y crea trade de stock con entry_type=ASSIGNMENT.
    """
    trade_date = trade_date or str(date.today())
    # Cerrar el CSP original
    db.close_trade(parent_trade_id, account_id, trade_date)
    # Registrar entrada de acciones por asignación
    return db.insert_trade(
        account_id=account_id,
        ticker=ticker,
        asset_type="STOCK",
        quantity=quantity,
        price=round2(assignment_price),
        strike=None,
        expiration_date=None,
        strategy_type="ASSIGNMENT",
        status="OPEN",
        entry_type="ASSIGNMENT",
        trade_date=trade_date,
        parent_trade_id=parent_trade_id,
        comment=comment,
    )


def register_direct_purchase(
    account_id: int,
    user_id: int,
    ticker: str,
    quantity: int,
    price: float,
    trade_date: str = None,
    comment: str = None,
) -> int:
    """Registra compra directa de acciones para iniciar Covered Call."""
    trade_date = trade_date or str(date.today())
    return db.insert_trade(
        account_id=account_id,
        ticker=ticker,
        asset_type="STOCK",
        quantity=quantity,
        price=round2(price),
        strike=None,
        expiration_date=None,
        strategy_type="STOCK",
        status="OPEN",
        entry_type="DIRECT_PURCHASE",
        trade_date=trade_date,
        comment=comment,
    )


def register_cc_opening(
    account_id: int,
    user_id: int,
    ticker: str,
    quantity: int,
    strike: float,
    premium: float,
    expiration_date: str,
    trade_date: str = None,
    comment: str = None,
    parent_trade_id: int = None,
) -> int:
    """
    Registra apertura de Covered Call.

    - entry_type=OPENING
    - parent_trade_id enlaza con la pierna anterior (roll-over).
    - Si parent_trade_id no viene informado, se intenta enlazar
      automáticamente con la **posición de acciones** más reciente
      (ASSIGNMENT o DIRECT_PURCHASE) para que toda la rueda
      (CSP → asignación → CC) quede dentro de la misma campaña.
    """
    trade_date = trade_date or str(date.today())

    # Auto‑link a la posición de acciones más reciente, si no se especifica
    # parent_trade_id explícitamente (ej. desde el formulario lateral).
    if parent_trade_id is None:
        conn = db.get_conn()
        try:
            cur = conn.execute(
                """
                SELECT trade_id
                FROM Trade
                WHERE account_id = ?
                  AND ticker = ?
                  AND asset_type = 'STOCK'
                  AND status = 'OPEN'
                ORDER BY trade_date DESC, trade_id DESC
                LIMIT 1
                """,
                (account_id, ticker.strip().upper()),
            )
            row = cur.fetchone()
            if row:
                parent_trade_id = row["trade_id"]
        finally:
            conn.close()
    return db.insert_trade(
        account_id=account_id,
        ticker=ticker,
        asset_type="OPTION",
        quantity=quantity,
        price=round2(premium),
        strike=round2(strike),
        expiration_date=expiration_date,
        strategy_type="CC",
        status="OPEN",
        entry_type="OPENING",
        trade_date=trade_date,
        parent_trade_id=parent_trade_id,
        comment=comment,
    )


def register_dividend(
    account_id: int,
    ticker: str,
    amount: float,
    ex_date: str,
    pay_date: str = None,
    note: str = None,
) -> int:
    """Registra dividendo que impacta en cost basis de la posición."""
    return db.insert_dividend(
        account_id=account_id,
        ticker=ticker,
        amount=round2(amount),
        ex_date=ex_date,
        pay_date=pay_date,
        note=note,
    )


def register_adjustment(
    account_id: int,
    ticker: str,
    adjustment_type: str,
    old_value: float = None,
    new_value: float = None,
    note: str = None,
    trade_id: int = None,
) -> int:
    """Ajuste de posición: Stock Split, corrección de cost basis, etc."""
    return db.insert_adjustment(
        account_id=account_id,
        ticker=ticker,
        adjustment_type=adjustment_type,
        old_value=round2(old_value) if old_value is not None else None,
        new_value=round2(new_value) if new_value is not None else None,
        note=note,
        trade_id=trade_id,
    )


def get_campaign_premiums(account_id: int, trade_id: int) -> float:
    """
    Suma de primas de toda la campaña: este trade + todos los ancestros (parent_trade_id).
    Así al hacer roll-over las primas se acumulan y el historial se conserva.
    """
    total = 0.0
    t = db.get_trade_by_id(account_id, trade_id)
    while t:
        if t.get("asset_type") == "OPTION":
            total += safe_float(t.get("price")) * int(t.get("quantity", 0)) * 100
        pid = t.get("parent_trade_id")
        t = db.get_trade_by_id(account_id, pid) if pid else None
    return round2(total)


def get_stock_quantity(account_id: int, ticker: str) -> int:
    """
    Acciones **libres** que posee la cuenta para el ticker (compra directa o
    asignación), descontando las ya comprometidas en Covered Calls abiertos.

    Se usa para validar nuevos CC: requiere tener al menos contratos × 100
    acciones **no cubiertas por otros CC**.
    """
    tk = ticker.strip().upper()
    trades = db.get_trades_by_account(account_id, status="OPEN", ticker=tk)
    if not trades:
        return 0

    total_shares = 0
    cc_contracts = 0
    for t in trades:
        if (t.get("asset_type") or "").upper() == "STOCK":
            total_shares += int(t.get("quantity") or 0)
        elif (t.get("asset_type") or "").upper() == "OPTION" and (t.get("strategy_type") or "").upper() == "CC":
            cc_contracts += int(t.get("quantity") or 0)

    shares_committed = max(0, cc_contracts * 100)
    free_shares = max(0, total_shares - shares_committed)
    return int(free_shares)


def get_campaign_start_date(account_id: int, trade_id: int) -> Optional[str]:
    """Fecha de inicio de la campaña: trade_date del trade más antiguo en la cadena (raíz)."""
    t = db.get_trade_by_id(account_id, trade_id)
    root_date = t.get("trade_date") if t else None
    while t:
        pid = t.get("parent_trade_id")
        if not pid:
            break
        t = db.get_trade_by_id(account_id, pid)
        if t and t.get("trade_date"):
            root_date = t["trade_date"]
    return root_date


def get_campaign_days(account_id: int, trade_id: int) -> int:
    """
    Suma de días de posición de toda la campaña (como se suman las primas).
    Por cada trade en la cadena: si CLOSED → (closed_date - trade_date).days; si OPEN → (hoy - trade_date).days.
    """
    today = date.today()
    total_days = 0
    t = db.get_trade_by_id(account_id, trade_id)
    while t:
        td = t.get("trade_date")
        if not td:
            pid = t.get("parent_trade_id")
            t = db.get_trade_by_id(account_id, pid) if pid else None
            continue
        try:
            d0 = date.fromisoformat(str(td)[:10])
        except (ValueError, TypeError):
            pid = t.get("parent_trade_id")
            t = db.get_trade_by_id(account_id, pid) if pid else None
            continue
        status = (t.get("status") or "").upper()
        if status == "CLOSED":
            cd = t.get("closed_date")
            if cd:
                try:
                    d1 = date.fromisoformat(str(cd)[:10])
                    total_days += max(0, (d1 - d0).days)
                except (ValueError, TypeError):
                    pass
        else:
            total_days += max(0, (today - d0).days)
        pid = t.get("parent_trade_id")
        t = db.get_trade_by_id(account_id, pid) if pid else None
    return total_days


def get_campaign_root_id(account_id: int, trade_id: int) -> Optional[int]:
    """
    Devuelve el trade_id de la **raíz** de la campaña (el primer trade de la
    cadena parent_trade_id). Sirve para:

    - agrupar en reportes toda la campaña de la rueda (CSP + rolls + asignación
      + CC + rolls + cierre),
    - etiquetar bitácoras por "Campaña".
    """
    t = db.get_trade_by_id(account_id, trade_id)
    if not t:
        return None
    root_id = t.get("trade_id")
    while t and t.get("parent_trade_id"):
        pid = t["parent_trade_id"]
        parent = db.get_trade_by_id(account_id, pid)
        if not parent:
            break
        root_id = parent.get("trade_id", root_id)
        t = parent
    return root_id


def get_position_summary(
    account_id: int,
    ticker: str = None,
) -> List[Dict[str, Any]]:
    """
    Resumen de posiciones **por campaña**, permitiendo varias campañas por
    ticker (por ejemplo, un CSP y uno o más CC sobre el mismo símbolo).

    - Cada opción abierta (CSP o CC) genera una fila/campaña independiente.
    - Las acciones se asignan **primero** a las campañas de CC (Propias + CC).
    - Las acciones restantes (no ligadas a CC) se muestran como campaña
      independiente con estrategia "PROPIAS".

    Esto evita mezclar en la misma línea una campaña de CSP con una de CC
    aunque compartan ticker, y permite tener múltiples campañas por símbolo.
    """
    trades = db.get_trades_by_account(account_id, status="OPEN", ticker=ticker)
    dividends = db.get_dividends_by_account(account_id, ticker=ticker)
    adjustments = db.get_adjustments_by_account(account_id, ticker=ticker)

    # Agrupar trades abiertos por ticker, separando stock y opciones
    by_ticker: Dict[str, Dict[str, Any]] = {}
    for t in trades:
        tk = t["ticker"]
        bucket = by_ticker.setdefault(
            tk,
            {
                "stocks": [],   # trades de acciones abiertos
                "options": [],  # trades de opciones abiertos
            },
        )
        if (t.get("asset_type") or "").upper() == "STOCK":
            bucket["stocks"].append(t)
        else:
            bucket["options"].append(t)

    # Dividendos y ajustes por ticker (se aplican sobre el paquete total de acciones)
    div_by_ticker = {}
    for d in dividends:
        tk = d["ticker"]
        div_by_ticker[tk] = div_by_ticker.get(tk, 0.0) + safe_float(d["amount"])

    adj_by_ticker = {}
    for a in adjustments:
        tk = a["ticker"]
        adj_by_ticker[tk] = adj_by_ticker.get(tk, 0.0) + safe_float(a.get("new_value") or 0) - safe_float(a.get("old_value") or 0)

    out = []
    for tk, buckets in by_ticker.items():
        stocks = buckets["stocks"]
        options = buckets["options"]

        # Totales de acciones y primas por ticker (para calcular cost basis global)
        total_stock_qty = sum(int(s.get("quantity") or 0) for s in stocks)
        total_stock_cost = sum(safe_float(s.get("price")) * int(s.get("quantity") or 0) for s in stocks)
        total_premiums_all = 0.0
        for opt in options:
            total_premiums_all += get_campaign_premiums(account_id, opt["trade_id"])

        div_total = div_by_ticker.get(tk, 0.0)
        adj_total = adj_by_ticker.get(tk, 0.0)

        if total_stock_qty > 0:
            avg_purchase_price = total_stock_cost / float(total_stock_qty)
            cost_net_total = net_cost_basis(
                avg_purchase_price,
                total_stock_qty,
                total_premiums_all,
                div_total,
                adj_total,
            )
            cost_net_total = safe_float(cost_net_total)
            cost_per_share = cost_net_total / float(total_stock_qty) if total_stock_qty else 0.0
        else:
            cost_net_total = 0.0
            cost_per_share = 0.0

        # Acciones disponibles para CC (se asignan primero a campañas de CC)
        shares_available_for_cc = total_stock_qty

        def _build_option_row(opt_trade: Dict[str, Any], assigned_shares: int) -> None:
            """Crea una fila de resumen para una campaña de opciones (CSP o CC)."""
            premiums_chain = get_campaign_premiums(account_id, opt_trade["trade_id"])
            strategy = opt_trade.get("strategy_type")
            is_cc = (strategy or "").upper() == "CC"

            # Datos base de la campaña
            row = {
                "ticker": tk,
                "premiums_received": safe_float(premiums_chain),
                "stock_quantity": int(assigned_shares or 0),
                "stock_cost_total": safe_float(cost_per_share * assigned_shares) if assigned_shares else 0.0,
                "option_contracts": int(opt_trade.get("quantity") or 0),
                "strike": opt_trade.get("strike"),
                "expiration_date": opt_trade.get("expiration_date"),
                "strategy_type": strategy,
                "trade_date": get_campaign_start_date(account_id, opt_trade["trade_id"]) or opt_trade.get("trade_date"),
                "trade_id_last": opt_trade.get("trade_id"),
                "campaign_days": get_campaign_days(account_id, opt_trade["trade_id"]),
            }

            # Distribuir cost basis, dividendos y ajustes proporcionalmente a las
            # acciones que cuelgan de esta campaña (si las hay).
            if total_stock_qty > 0 and assigned_shares > 0:
                weight = assigned_shares / float(total_stock_qty)
                row["dividends_received"] = round2(div_total * weight)
                row["adjustments"] = round2(adj_total * weight)
                row["net_cost_basis_total"] = safe_float(cost_net_total * weight)
            else:
                row["dividends_received"] = 0.0
                row["adjustments"] = 0.0
                row["net_cost_basis_total"] = 0.0

            out.append(row)

        # 1) Campañas de CC: se les vinculan acciones disponibles (Propias + CC).
        cc_options = [o for o in options if (o.get("strategy_type") or "").upper() == "CC"]
        other_options = [o for o in options if (o.get("strategy_type") or "").upper() != "CC"]

        for opt in cc_options:
            needed_shares = max(0, int(opt.get("quantity") or 0) * 100)
            assigned = min(shares_available_for_cc, needed_shares)
            _build_option_row(opt, assigned_shares=assigned)
            shares_available_for_cc -= assigned

        # 2) Otras campañas de opciones (CSP, PUT, etc.): no se mezclan con acciones.
        for opt in other_options:
            _build_option_row(opt, assigned_shares=0)

        # 3) Acciones restantes que no están ligadas a CC → campaña "PROPIAS".
        if shares_available_for_cc > 0:
            remaining_qty = shares_available_for_cc
            remaining_cost_total = safe_float(cost_per_share * remaining_qty) if cost_per_share else safe_float(total_stock_cost)
            # Fechas: tomamos la más antigua de las compras abiertas como inicio.
            trade_date_first = None
            for st in sorted(stocks, key=lambda x: (x.get("trade_date") or "", x.get("trade_id") or 0)):
                trade_date_first = st.get("trade_date")
                break

            # Proporción para dividendos/ajustes sobre estas acciones "libres".
            if total_stock_qty > 0:
                weight_rem = remaining_qty / float(total_stock_qty)
                div_rem = round2(div_total * weight_rem)
                adj_rem = round2(adj_total * weight_rem)
                net_cost_rem = safe_float(cost_net_total * weight_rem)
            else:
                div_rem = round2(div_total)
                adj_rem = round2(adj_total)
                net_cost_rem = remaining_cost_total

            out.append(
                {
                    "ticker": tk,
                    "premiums_received": 0.0,
                    "stock_quantity": int(remaining_qty),
                    "stock_cost_total": remaining_cost_total,
                    "option_contracts": 0,
                    "strike": None,
                    "expiration_date": None,
                    "strategy_type": "PROPIAS",
                    "trade_date": trade_date_first,
                    "trade_id_last": None,
                    "campaign_days": None,
                    "dividends_received": div_rem,
                    "adjustments": adj_rem,
                    "net_cost_basis_total": net_cost_rem,
                }
            )

    return out
