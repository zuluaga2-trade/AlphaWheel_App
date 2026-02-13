# AlphaWheel Pro - Gauge (Análisis del riesgo) y texto copiable para compartir
"""
Gráfico tipo medidor (Gauge) para "Análisis del riesgo": Favorable / Desfavorable,
Ganando / Perdiendo. Estilo "reloj futurista" con líneas radiales de métricas.
"""
import math
import plotly.graph_objects as go


def risk_analysis_score(
    pnl_actual: float,
    mkt: float,
    be: float,
    is_put: bool,
    dte: int = 0,
    ret_pct: float = 0,
    earnings_ok: bool = True,
) -> int:
    """
    Calcula un score 0-100 para Análisis del riesgo usando lógica de opciones.

    - Moneyness (precio vs BE/strike) pesa más que el P&L.
    - CSP (put) está "mejor" cuando el precio está por encima de BE/strike.
    - CC (call) está "mejor" cuando el precio está por debajo de BE/strike.
    - DTE alto reduce riesgo; earnings cercanos lo aumentan.
    """
    score = 50.0

    # --- Moneyness: distancia del precio al BE en % del strike ---
    if strike := (be if be else mkt):
        # Para puts: positivo si precio > BE; para calls: positivo si precio < BE
        if is_put:
            dist = (mkt - be) if be else (mkt - strike)
        else:
            dist = (be - mkt) if be else (strike - mkt)
        # Normalizar a % del strike (clamp ±40%)
        moneyness_pct = 100.0 * dist / max(abs(strike), 1e-6)
        moneyness_pct = max(-40.0, min(40.0, moneyness_pct))
        # Moneyness aporta hasta ±25 puntos
        score += (moneyness_pct / 40.0) * 25.0

    # --- P&L actual: importante pero secundario frente a moneyness ---
    if pnl_actual >= 0:
        score += 10.0
    else:
        score -= 10.0

    # --- DTE: más días, más margen para gestionar ---
    if dte >= 30:
        score += 10.0
    elif dte >= 14:
        score += 7.0
    elif dte >= 7:
        score += 4.0
    elif dte <= 2:
        score -= 8.0
    elif dte <= 5:
        score -= 4.0

    # --- Retorno del periodo ---
    if (ret_pct or 0) > 0:
        score += 4.0
    elif (ret_pct or 0) < 0:
        score -= 4.0

    # --- Earnings en periodo ---
    if earnings_ok:
        score += 3.0
    else:
        score -= 7.0

    return max(0, min(100, int(round(score))))


# Alias para compatibilidad
position_health_score = risk_analysis_score


def build_gauge_figure(
    score: int,
    title: str = "Análisis del riesgo",
    pnl_actual: float | None = None,
    mode: str = "position",
    metrics_legend: str | None = None,
    metrics_positions: dict[str, float] | None = None,
) -> go.Figure:
    """
    Gráfico tipo medidor (Gauge) 0-100 para Análisis del riesgo.
    Zonas: 0-33 Desfavorable (rojo), 33-66 Evaluar (amarillo), 66-100 Favorable (verde).
    Opcional: pnl_actual para mostrar "Ganando" o "Perdiendo" en el subtítulo.
    """
    # Paleta más vistosa (rojo/ámbar/verde neón)
    if score <= 33:
        bar_color = "#ff3366"  # rojo neón
        zone_label = "Desfavorable"
    elif score <= 66:
        bar_color = "#ffcc33"  # ámbar brillante
        zone_label = "Evaluar"
    else:
        bar_color = "#00ff99"  # verde neón
        zone_label = "Favorable"

    pnl_label = ""
    if pnl_actual is not None:
        pnl_label = " — Ganando" if pnl_actual >= 0 else " — Perdiendo"

    if mode not in ("screener", "position"):
        mode = "position"

    if mode == "screener":
        subtitle_line = "Probabilidad de que la nueva posición sea favorable"
    else:
        subtitle_line = f"{zone_label}{pnl_label}"

    metrics_line = ""
    if metrics_legend:
        metrics_line = f"<br><span style='font-size:12px;color:#8b949e'>{metrics_legend}</span>"

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number={"suffix": " / 100", "font": {"size": 26}},
            title={
                "text": (
                    f"{title}"
                    f"<br><span style='font-size:14px;color:#8b949e'>Favorable ↔ Desfavorable</span>"
                    f"<br><span style='font-size:13px;color:{bar_color}'>{subtitle_line}</span>"
                    f"{metrics_line}"
                ),
                "font": {"size": 16},
            },
            gauge={
                "axis": {
                    "range": [0, 100],
                    "tickwidth": 1,
                    "tickvals": [0, 33, 66, 100],
                    "ticktext": ["Desfavorable", "Evaluar", "Favorable", ""],
                },
                "bar": {"color": bar_color, "thickness": 0.75},
                "bgcolor": "rgba(13,17,23,0.98)",
                "borderwidth": 2,
                "bordercolor": "#21262d",
                "steps": [
                    {"range": [0, 33], "color": "rgba(255,51,102,0.18)"},
                    {"range": [33, 66], "color": "rgba(255,204,51,0.18)"},
                    {"range": [66, 100], "color": "rgba(0,255,153,0.18)"},
                ],
                "threshold": {
                    "line": {"color": bar_color, "width": 4},
                    "thickness": 0.8,
                    "value": score,
                },
            },
        )
    )
    # --- Líneas radiales por métrica (reloj futurista) ---
    shapes: list[dict] = []
    if metrics_positions:
        # Centro aproximado del gauge en coordenadas de papel (0–1)
        cx, cy = 0.5, 0.12
        max_r = 0.6
        # Paleta neón por nombre de métrica
        palette = {
            "Precio": "#00e5ff",
            "Strike": "#ffb347",
            "BE": "#f0f6fc",
            "Prima": "#ff66c4",
            "Ret.%": "#a855f7",
            "P&L": "#39d353",
            "DTE": "#f9e2af",
            "Max gan.": "#7ee787",
        }
        fallback_colors = ["#00e5ff", "#ffb347", "#ff66c4", "#a855f7", "#39d353", "#f9e2af"]
        for idx, (name, raw_val) in enumerate(metrics_positions.items()):
            v = max(0.0, min(100.0, float(raw_val))) / 100.0  # 0–1
            # Mapear 0–1 a ángulo [-π, 0] (izq a der)
            angle = math.pi * (1.0 - v)
            r = max_r * (0.35 + 0.65 * v)  # más valor, más largo
            x1 = cx + r * math.cos(angle)
            y1 = cy + r * math.sin(angle)
            color = palette.get(name, fallback_colors[idx % len(fallback_colors)])
            shapes.append(
                {
                    "type": "line",
                    "xref": "paper",
                    "yref": "paper",
                    "x0": cx,
                    "y0": cy,
                    "x1": x1,
                    "y1": y1,
                    "line": {"color": color, "width": 2},
                }
            )

    fig.update_layout(
        template="plotly_dark",
        height=360 if mode == "position" else 330,
        margin=dict(l=50, r=50, t=80, b=50),
        paper_bgcolor="rgba(22,27,34,0.98)",
        font=dict(color="#e6edf3", size=14),
        shapes=shapes if shapes else None,
    )
    return fig


def _price_axis_position(price: float, min_val: float, max_val: float) -> float:
    """Mapea un precio al eje 0-100 del semicírculo."""
    if max_val <= min_val:
        return 50.0
    return max(0.0, min(100.0, 100.0 * (price - min_val) / (max_val - min_val)))


def build_gauge_price_axis(
    strike: float,
    be: float,
    precio: float,
    dte: int,
    status_label: str,
    title: str = "Análisis del riesgo",
    is_put: bool = True,
) -> go.Figure:
    """
    Medidor según boceto: semicírculo con escala, tres agujas (Strike, BE, Precio),
    DTE en el centro y caja de estado (Favorable / Evaluar / Desfavorable).
    Colores sutiles que no resaltan en fondo oscuro.
    """
    # Eje de precios: rango con margen
    vals = [v for v in (strike, be, precio) if v is not None and v > 0]
    if not vals:
        min_val, max_val = 0.0, 100.0
    else:
        mn, mx = min(vals), max(vals)
        margin = max((mx - mn) * 0.15, 1.0)
        min_val = mn - margin
        max_val = mx + margin

    pos_strike = _price_axis_position(strike or 0, min_val, max_val)
    pos_be = _price_axis_position(be or 0, min_val, max_val)
    pos_precio = _price_axis_position(precio or 0, min_val, max_val)

    # Zonas sutiles (no resaltan en oscuro)
    if status_label.lower().startswith("fav"):
        zone_color = "#3d6b4a"  # verde muy suave
        bar_color = "#5a8f6a"
    elif "eval" in status_label.lower():
        zone_color = "#6b5d3d"
        bar_color = "#8f7a4a"
    else:
        zone_color = "#6b3d3d"
        bar_color = "#8f5a5a"

    # Escala numérica en el arco: precios en 0, 25, 50, 75, 100
    def price_at(pos: float) -> float:
        return min_val + (pos / 100.0) * (max_val - min_val)

    tickvals = [0, 25, 50, 75, 100]
    ticktext = [f"{price_at(p):.0f}" for p in tickvals]

    # Zonas con contraste frente al fondo oscuro
    pos_be_clamp = max(1.0, min(99.0, pos_be))
    steps_zones = [
        {"range": [0, pos_be_clamp - 1], "color": "rgba(200,80,80,0.5)"},
        {"range": [pos_be_clamp - 1, pos_be_clamp + 1], "color": "rgba(180,160,80,0.5)"},
        {"range": [pos_be_clamp + 1, 100], "color": "rgba(80,180,100,0.5)"},
    ]

    fig = go.Figure(
        go.Indicator(
            mode="gauge",
            value=pos_precio,
            title={"text": title, "font": {"size": 15}},
            gauge={
                "axis": {
                    "range": [0, 100],
                    "tickwidth": 1,
                    "tickvals": tickvals,
                    "ticktext": ticktext,
                    "tickfont": {"size": 11, "color": "#8b949e"},
                },
                "bar": {"color": bar_color, "thickness": 0.5},
                "bgcolor": "rgba(24,28,36,0.98)",
                "borderwidth": 1,
                "bordercolor": "#30363d",
                "steps": steps_zones,
                "threshold": {
                    "line": {"color": "rgba(0,0,0,0)", "width": 0},
                    "thickness": 0,
                    "value": pos_precio,
                },
            },
        )
    )

    cx, cy = 0.5, 0.14
    r_inner = 0.17   # Origen de las agujas (no en el centro para no tapar el DTE)
    r_outer = 0.34   # Punta: misma longitud para Strike, BE y Precio

    def angle_rad(pos: float) -> float:
        return math.pi * (1.0 - pos / 100.0)

    def needle_segment(pos: float) -> tuple[float, float, float, float]:
        a = angle_rad(pos)
        x0 = cx + r_inner * math.cos(a)
        y0 = cy + r_inner * math.sin(a)
        x1 = cx + r_outer * math.cos(a)
        y1 = cy + r_outer * math.sin(a)
        return (x0, y0, x1, y1)

    color_strike = "#ff9f43"
    color_be = "#dfe6e9"
    color_precio = "#00d2d3"
    line_w = 2.5  # Mismo grosor para las tres agujas (Strike, BE, Precio)

    shapes: list[dict] = []
    tips: list[tuple[float, float]] = []

    # Las tres agujas iguales en todos los gráficos: mismo origen, misma longitud, sin círculos
    for pos, color in [(pos_strike, color_strike), (pos_be, color_be), (pos_precio, color_precio)]:
        x0, y0, x1, y1 = needle_segment(pos)
        tips.append((x1, y1))
        shapes.append({"type": "line", "xref": "paper", "yref": "paper",
            "x0": x0, "y0": y0, "x1": x1, "y1": y1,
            "line": {"color": color, "width": line_w}})

    def label_pos(x1: float, y1: float, k: float = 1.12) -> tuple[float, float]:
        dx, dy = x1 - cx, y1 - cy
        return (cx + k * dx, cy + k * dy)

    # tips orden: Strike, BE, Precio
    lx1, ly1 = label_pos(tips[0][0], tips[0][1])   # Strike
    lx2, ly2 = label_pos(tips[1][0], tips[1][1])   # BE
    lx3, ly3 = label_pos(tips[2][0], tips[2][1])   # Precio

    annotations: list[dict] = [
        {"text": "Strike", "xref": "paper", "yref": "paper", "x": lx1, "y": ly1,
         "showarrow": False, "font": {"size": 10, "color": color_strike},
         "xanchor": "center", "yanchor": "middle"},
        {"text": "BE", "xref": "paper", "yref": "paper", "x": lx2, "y": ly2,
         "showarrow": False, "font": {"size": 10, "color": color_be},
         "xanchor": "center", "yanchor": "middle"},
        {"text": "Precio", "xref": "paper", "yref": "paper", "x": lx3, "y": ly3,
         "showarrow": False, "font": {"size": 10, "color": color_precio},
         "xanchor": "center", "yanchor": "middle"},
        {
            "text": f"{dte} DTE",
            "xref": "paper", "yref": "paper",
            "x": 0.5, "y": 0.14,
            "showarrow": False,
            "font": {"size": 20, "color": "#e6edf3"},
            "xanchor": "center", "yanchor": "middle",
        },
        {
            "text": status_label,
            "xref": "paper", "yref": "paper",
            "x": 0.5, "y": 0.04,
            "showarrow": False,
            "font": {"size": 16, "color": zone_color},
            "xanchor": "center", "yanchor": "middle",
            "bgcolor": "rgba(22,27,34,0.9)",
            "borderpad": 4,
        },
    ]

    fig.update_layout(
        template="plotly_dark",
        height=340,
        margin=dict(l=55, r=55, t=60, b=50),
        paper_bgcolor="rgba(22,27,34,0.98)",
        font=dict(color="#b1bac4", size=13),
        shapes=shapes,
        annotations=annotations,
    )
    return fig


def _normalize_0_100(value: float, low: float, high: float) -> float:
    """Mapea value en [low, high] a 0-100. Si high==low devuelve 50."""
    if high <= low:
        return 50.0
    return max(0.0, min(100.0, 100.0 * (value - low) / (high - low)))


def metrics_for_screener_gauge(
    precio: float,
    strike: float,
    be: float,
    prima: float,
    dte: int,
    ret_pct: float,
    is_put: bool,
) -> list[tuple[str, float]]:
    """
    Métricas para el medidor del screener (probabilidad de entrada).
    Cada valor se normaliza 0-100 para llenar el arco.
    """
    metrics = []
    # Precio: qué tan lejos está del BE hacia el strike (put: precio > BE = bueno)
    if strike and strike != be:
        precio_n = _normalize_0_100(precio, be, strike) if is_put else _normalize_0_100(precio, strike, be)
    else:
        precio_n = 50.0
    metrics.append(("Precio", precio_n))
    # Strike (referencia): nivel fijo alto
    metrics.append(("Strike", 100.0))
    # BE (referencia)
    metrics.append(("BE", 100.0))
    # Prima por acción como % del strike: 0-5% -> 0-100
    if strike and strike > 0:
        prima_pct = (prima / strike) * 100.0
        prima_n = min(100.0, prima_pct * 20.0)  # 5% = 100
    else:
        prima_n = 50.0
    metrics.append(("Prima", prima_n))
    # DTE: 0-50 días -> 0-100
    metrics.append(("DTE", min(100.0, max(0.0, dte * 2.0))))
    # Retorno periodo: 0-10% -> 0-100
    metrics.append(("Ret.%", min(100.0, max(0.0, (ret_pct or 0) * 10.0))))
    return metrics


def metrics_for_position_gauge(
    precio: float,
    strike: float,
    be: float,
    prima: float,
    pnl_actual: float,
    dte: int,
    max_ganancia: float,
    max_perdida: float | None,
    is_put: bool,
) -> list[tuple[str, float]]:
    """
    Métricas para el medidor de cuentas (realidad de la posición).
    P&L normalizado entre max_perdida y max_ganancia.
    """
    metrics = []
    if strike and strike != be:
        precio_n = _normalize_0_100(precio, be, strike) if is_put else _normalize_0_100(precio, strike, be)
    else:
        precio_n = 50.0
    metrics.append(("Precio", precio_n))
    metrics.append(("Strike", 100.0))
    metrics.append(("BE", 100.0))
    if strike and strike > 0:
        # prima = prima total; prima/(strike*100) = % del colateral; 5% -> 100
        prima_n = min(100.0, (prima / (strike * 100)) * 2000.0)
    else:
        prima_n = 50.0
    metrics.append(("Prima", prima_n))
    # P&L: 0 = max pérdida, 100 = max ganancia
    if max_perdida is not None and max_ganancia is not None and max_ganancia != max_perdida:
        pnl_n = _normalize_0_100(pnl_actual, max_perdida, max_ganancia)
    elif max_ganancia and max_ganancia > 0:
        pnl_n = _normalize_0_100(pnl_actual, 0.0, max_ganancia)
    else:
        pnl_n = 50.0 if pnl_actual >= 0 else 20.0
    metrics.append(("P&L", pnl_n))
    metrics.append(("DTE", min(100.0, max(0.0, dte * 2.0))))
    metrics.append(("Max gan.", 100.0))
    return metrics


# Colores por métrica (arco radial)
RADIAL_COLORS = [
    "#58a6ff",  # Precio
    "#79c0ff",  # Strike
    "#3fb950",  # BE
    "#d29922",  # Prima
    "#a371f7",  # P&L / Ret.%
    "#2ea043",  # DTE
    "#56d364",  # Max gan
]


def build_gauge_spectacular(
    score: int,
    title: str = "Análisis del riesgo",
    mode: str = "position",
    pnl_actual: float | None = None,
    metrics: list[tuple[str, float]] | None = None,
) -> go.Figure:
    """
    Medidor espectacular: semicírculo con varias líneas (arcos) que se llenan según cada métrica.
    - screener: probabilidad de entrada (Precio, Strike, BE, Prima, DTE, Ret.%).
    - position: realidad de la posición (+ P&L, Max ganancia).
    Centro: score y zona (Favorable/Desfavorable) + Ganando/Perdiendo si aplica.
    """
    if metrics is None:
        metrics = []
    if score <= 33:
        zone_label = "Desfavorable"
        zone_color = "#f85149"
    elif score <= 66:
        zone_label = "Evaluar"
        zone_color = "#d29922"
    else:
        zone_label = "Favorable"
        zone_color = "#3fb950"
    pnl_text = ""
    if pnl_actual is not None:
        pnl_text = " — Ganando" if pnl_actual >= 0 else " — Perdiendo"
    if mode == "screener":
        subtitle = "Probabilidad de que la entrada sea favorable"
    else:
        subtitle = f"{zone_label}{pnl_text}"

    n = max(1, len(metrics))
    angle_span = 180.0 / n  # semicírculo
    base_angle = 90.0  # sector 90°–270° (semicírculo)
    theta_center_deg = [base_angle + (i + 0.5) * angle_span for i in range(n)]

    fig = go.Figure()
    for i, (label, value_0_100) in enumerate(metrics):
        r_val = max(1.0, min(100.0, value_0_100))
        color = RADIAL_COLORS[i % len(RADIAL_COLORS)]
        t0 = base_angle + i * angle_span
        t1 = base_angle + (i + 1) * angle_span
        # Wedge: theta en grados (Plotly polar), r de 0 a r_val
        theta_deg = [t0, t0, t1, t1]
        r = [0, r_val, r_val, 0]
        fig.add_trace(
            go.Scatterpolar(
                r=r,
                theta=theta_deg,
                fill="toself",
                fillcolor=color,
                line=dict(color=color, width=1.5),
                name=label,
                legendgroup=label,
            )
        )

    # Ejes: un tick por métrica con su etiqueta
    fig.update_layout(
        polar=dict(
            sector=[90, 270],  # semicírculo (90°–270°)
            radialaxis=dict(
                range=[0, 105],
                showticklabels=True,
                tickvals=[25, 50, 75, 100],
                tickfont=dict(size=10, color="#8b949e"),
                gridcolor="rgba(33,38,45,0.8)",
            ),
            angularaxis=dict(
                tickvals=theta_center_deg,
                ticktext=[m[0] for m in metrics],
                tickfont=dict(size=11, color="#e6edf3"),
                gridcolor="rgba(33,38,45,0.5)",
                rotation=0,
                direction="clockwise",
            ),
            bgcolor="rgba(13,17,23,0.98)",
        ),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="top",
            y=1.12,
            xanchor="center",
            x=0.5,
            font=dict(size=10),
        ),
        title=dict(
            text=f"{title}<br><span style='font-size:12px;color:#8b949e'>{subtitle}</span><br><span style='font-size:14px;color:{zone_color}'>Score: {score}/100</span>",
            x=0.5,
            xanchor="center",
        ),
        template="plotly_dark",
        height=420,
        margin=dict(l=80, r=80, t=100, b=60),
        paper_bgcolor="rgba(22,27,34,0.98)",
        font=dict(color="#e6edf3", size=12),
    )
    return fig


def build_copyable_summary_from_row(row: dict, estrategia: str = "CSP") -> str:
    """Resumen copiable a partir de un row del screener (contrato o ficha)."""
    ticker = row.get("Ticker", "")
    strike = float(row.get("Strike") or 0)
    be = float(row.get("BE") or 0)
    precio = float(row.get("Precio") or 0)
    prima = float(row.get("Prima") or 0)
    dte = int(row.get("DTE", 0) or 0)
    ret_pct = float(row.get("Ret. %", 0) or 0)
    exp = row.get("Exp", "")
    earnings = row.get("Earnings", "—")
    roi_ann = float(row.get("ROI Ann %", 0) or 0)
    delta = row.get("Delta", "")
    iv = row.get("iv")
    hv = row.get("hv")
    lines = [
        "——— AlphaWheel Pro — Resumen contrato/posición ———",
        f"Ticker: {ticker}  |  Estrategia: {estrategia}",
        f"Strike: ${strike:,.2f}  |  BE: ${be:,.2f}  |  Precio: ${precio:,.2f}",
        f"Prima: ${prima:,.2f}  |  DTE: {dte} días  |  Exp: {exp}",
        f"Retorno periodo: {ret_pct:,.2f}%  |  ROI anual: {roi_ann:,.2f}%",
        f"Earnings: {earnings}",
    ]
    if delta not in ("", None):
        lines.append(f"Delta: {delta}")
    if iv is not None and hv is not None:
        try:
            lines.append(f"IV: {float(iv):,.2f}%  |  HV: {float(hv):,.2f}%")
        except (TypeError, ValueError):
            pass
    lines.append("—————————————————————————————————————————")
    return "\n".join(lines)


def build_copyable_summary_position(
    ticker: str,
    estrategia: str,
    contracts: int,
    strike: float,
    be: float,
    mkt: float,
    prems: float,
    dte: int,
    pnl_actual: float,
    max_ganancia: float,
    max_perdida_label: str,
    estado_texto: str,
    diagnostico: str = "",
) -> str:
    """Resumen copiable a partir de datos de posición del dashboard (cuentas)."""
    lines = [
        "——— AlphaWheel Pro — Resumen posición ———",
        f"Ticker: {ticker}  |  Estrategia: {estrategia}  |  Contratos: {contracts}",
        f"Strike: ${strike:,.2f}  |  BE: ${be:,.2f}  |  Precio: ${mkt:,.2f}",
        f"Prima recibida: ${prems:,.2f}  |  DTE: {dte} días",
        f"P&L actual: ${pnl_actual:,.2f}  |  Estado: {estado_texto}",
        f"Max ganancia: ${max_ganancia:,.2f}  |  Max pérdida: {max_perdida_label}",
        f"Diagnóstico: {diagnostico}",
        "—————————————————————————————————————————",
    ]
    return "\n".join(lines)
