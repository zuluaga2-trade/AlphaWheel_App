# AlphaWheel Pro - Cockpit principal (Dashboard, Reportes, Mi cuenta)
# Multi-usuario: sesión por login; cada usuario gestiona sus propias cuentas
import html as html_module
import io
from datetime import datetime, date, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf

from database import db
from database.db import (
    get_trades_by_account,
    get_account_by_id,
    get_accounts_by_user,
    close_trade,
    delete_account,
    get_dividends_by_account,
    get_user_screener_settings,
    update_user_av_key,
    get_user_bunkers,
    get_bunker_by_id,
    create_bunker,
    update_bunker,
    delete_bunker,
)
from engine.calculations import (
    round2,
    safe_float,
    calculate_dte,
    calculate_breakeven,
    calculate_annualized_return,
    calculate_return_on_capital,
    delta_approx_itm_otm,
)
from providers.tradier import TradierProvider
from business.wheel import (
    register_csp_opening,
    register_assignment,
    register_direct_purchase,
    register_cc_opening,
    register_dividend,
    register_adjustment,
    get_position_summary,
    get_stock_quantity,
)
from reports.bitacora import (
    export_trades_csv,
    export_trades_excel,
    export_trades_pdf,
    tax_efficiency_summary,
    get_trades_for_report,
)
from app.styles import PROFESSIONAL_CSS
from app.session_helpers import (
    get_current_user_id,
    get_current_user_display_name,
    get_current_user_email,
    get_current_account_id,
    set_current_account_id,
    get_accounts_for_current_user,
)
from auth.auth import logout_user
import config


def _get_tradier_token_for_user(user_id: int) -> tuple:
    """Devuelve (token, environment) de la primera cuenta del usuario con token; (None, None) si no hay."""
    if not user_id:
        return None, None
    accounts = get_accounts_by_user(user_id)
    for a in accounts:
        tok = (a.get("access_token") or "").strip()
        if tok:
            return tok, a.get("environment") or "sandbox"
    return None, None


def fmt2(val):
    """Formatea número a 2 decimales con coma como separador de miles (ej. 360,000.50)."""
    if val is None:
        return "—"
    v = round2(val)
    return f"{v:,.2f}" if isinstance(v, (int, float)) else str(val)


def _parse_thinkorswim_symbol(s: str) -> dict | None:
    """
    Parsea símbolo tipo Thinkorswim: .NOW260227P105 (CSP) o .NOW260227C108 (CC).
    Formato: [.]ROOT + YYMMDD + P/C + STRIKE → ticker, exp (YYYY-MM-DD), option_type, strike.
    Devuelve dict con: ticker, exp_str, exp_date, option_type ('put'|'call'), strike, occ_symbol (para Tradier).
    """
    import re
    s = (s or "").strip().upper()
    if not s:
        return None
    s = s.lstrip(".")
    # ROOT (letras) + 6 dígitos (YYMMDD) + P o C + strike (número)
    m = re.match(r"^([A-Z]+)(\d{6})([PC])(\d+(?:\.\d+)?)$", s)
    if not m:
        return None
    root, yymmdd, pc, strike_str = m.group(1), m.group(2), m.group(3), m.group(4)
    strike = float(strike_str)
    yy, mm, dd = int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:6])
    year = 2000 + yy if yy < 50 else 1900 + yy
    try:
        exp_date = date(year, mm, dd)
    except ValueError:
        return None
    exp_str = exp_date.isoformat()
    option_type = "put" if pc == "P" else "call"
    # Tradier usa formato compacto: ROOT + YYMMDD + C/P + strike*1000 (8 dígitos), sin espacios (ej. NVDA250919C00175000)
    strike_occ = str(int(round(strike * 1000))).zfill(8)
    occ_symbol = f"{root}{yymmdd}{pc}{strike_occ}"
    return {
        "ticker": root,
        "exp_str": exp_str,
        "exp_date": exp_date,
        "option_type": option_type,
        "strike": strike,
        "occ_symbol": occ_symbol,
    }


def _render_tutorial_tab() -> None:
    """Pestaña Tutorial: guía completa para usuarios nuevos (incl. sin conocimiento en opciones)."""
    st.markdown(
        '<div class="report-hero"><span class="report-hero-icon">📖</span> Tutorial — Cómo usar AlphaWheel Pro</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        "Esta guía te lleva paso a paso por la aplicación. Si no conoces las opciones, empieza por **Conceptos básicos**."
    )

    with st.expander("🎯 ¿Qué es AlphaWheel Pro?", expanded=True):
        st.markdown("""
**AlphaWheel Pro** es una aplicación para gestionar la **estrategia de la rueda** (wheel) con opciones:

- **CSP (Cash Secured Put)**: vendes puts sobre acciones que te gustaría comprar. Cobras prima; si el precio baja y te asignan, compras la acción a un precio acordado (strike).
- **CC (Covered Call)**: si ya tienes acciones, vendes calls sobre ellas y cobras prima; limitas la subida pero ganas ingresos recurrentes.

La app te ayuda a **buscar oportunidades** (screener), **registrar posiciones**, ver **Análisis del riesgo** (medidor Favorable/Desfavorable, Ganando/Perdiendo) y **exportar reportes** para impuestos o seguimiento.
        """)

    with st.expander("📚 Conceptos básicos de opciones (para principiantes)", expanded=False):
        st.markdown("""
- **Opción**: contrato que da derecho (no obligación) a comprar o vender una acción a un precio fijo hasta una fecha.
- **Put**: opción de *vender* la acción al **strike**. Quien *vende* el put cobra **prima** y se compromete a comprar la acción si el comprador ejerce.
- **Call**: opción de *comprar* la acción al **strike**. Quien *vende* el call cobra prima y puede tener que entregar las acciones si suben.
- **Strike**: precio al que se compra/vende la acción si se ejerce la opción.
- **Prima**: dinero que cobras al vender la opción (tu ingreso).
- **Vencimiento (expiration)**: fecha límite de la opción. **DTE** = días hasta el vencimiento.
- **Delta**: probabilidad aproximada de que la opción termine en el dinero (ej. delta -0.20 put ≈ 20% de ser asignado). En CSP suelen usarse deltas bajos (p. ej. -0.10 a -0.30).
- **IV (volatilidad implícita)** vs **HV (histórica)**: si IV > HV, la opción suele estar "cara" y puede ser buen momento para vender prima.
- **Colateral**: en CSP, el broker reserva strike × 100 × contratos. Eso es lo que "bloqueas" hasta vencimiento o cierre.
        """)

    with st.expander("🔄 Estrategias: CSP y Covered Call", expanded=False):
        st.markdown("""
**CSP (Cash Secured Put)**  
Vendes un put y cobras prima. Si el precio de la acción está por encima del strike al vencimiento, te quedas con la prima. Si está por debajo, te asignan y compras 100 acciones por contrato al strike. Muchos usan CSP para "comprar" acciones a un precio objetivo (strike) mientras cobran prima.

**Covered Call (CC)**  
Tienes acciones (por compra directa o por asignación de un CSP). Vendes un call sobre esas acciones y cobras prima. Si el precio no supera el strike, te quedas con la prima. Si supera el strike, te pueden asignar y vender tus acciones al strike. La rueda continúa: tras asignación de put → tienes acciones → vendes call → si te asignan el call, vendes acciones y puedes volver a vender puts.
        """)

    with st.expander("🚀 Empezar: cuenta, token y capital", expanded=False):
        st.markdown("""
1. **Mi cuenta** (pestaña): crea una cuenta con un nombre (ej. "Cuenta principal"). Define **capital ($)**, **meta anual (%)** y **máx. por ticker (%)**.
2. **Token Tradier**: en Mi cuenta, pega tu **token de Tradier** (obtienes uno en tradier.com → API Access). Con eso la app puede mostrar precios en tiempo real y estado de las posiciones.
3. **Alpha Vantage** (opcional): si quieres filtros por earnings o datos fundamentales en el screener, añade tu clave en **Filtros del Screener** (arriba) y en Mi cuenta.
4. Selecciona la cuenta en el desplegable superior para ver su dashboard.
        """)

    with st.expander("🔎 El Screener: buscar oportunidades", expanded=False):
        st.markdown("""
El **Screener** es la vista "🔎 Screener" (selector arriba). En los **Filtros del Screener** (arriba):

- **Estrategia**: CSP o Covered Call.
- **DTE mínimo / máximo**: rango de días hasta vencimiento (ej. 7–30).
- **Delta mínimo / máximo**: rango de delta (CSP típ. -0.20 a -0.10; CC 0.10 a 0.20).
- **ROI anualizado mínimo (%)**: filtra por retorno anualizado.
- **Colateral disponible ($)**: solo opciones con colateral ≤ este valor (0 = sin filtro).
- **Búnkers**: crea en "Gestionar búnkers" listas de tickers (ej. Tech: AAPL, MSFT, NVDA). Elige un búnker para escanear solo esos símbolos.
- **Individual**: si eliges "INDIVIDUAL", escribe un solo ticker.
- **Strikes bajo SMA 200** / **Stoch < 30** / **Evitar earnings**: filtros adicionales de riesgo.

Pulsa **🚀 Iniciar barrido**. La tabla muestra resultados (ticker, expiración, DTE, precio, strike, prima, retorno, delta, earnings, etc.). **Earnings**: NO = verde (sin earnings en periodo), SÍ = rojo.

- **Analizar un contrato (Thinkorswim)**: en los **Filtros del Screener** (arriba), pega un símbolo tipo `.NOW260227P105` o `.NOW260227C108` y pulsa **Analizar contrato**. Verás la misma ficha (métricas, riesgos SMA200/Stoch/Earnings, medidor de Análisis del riesgo).
- **Ficha al hacer clic**: selecciona una fila en la tabla para ver la **Ficha Sniper** (métricas, volatilidad, medidor de Análisis del riesgo, métricas resumidas). Desde ahí puedes **copiar/compartir** el resumen del contrato y abrir un trade con el expander "Abrir trade desde esta ficha".
        """)

    with st.expander("📊 Dashboard: posiciones y Análisis del riesgo", expanded=False):
        st.markdown("""
En **📊 Dashboard** (pestaña Mi Cuenta):

- **Resumen de cuenta**: capital, meta anual, colateral en uso, prima recibida, utilización, número de posiciones.
- **Posiciones abiertas**: tabla con activo, estrategia, contratos, fechas, strike, prima, breakeven, diagnóstico (OK / Riesgo / Perdiendo), retorno, etc.
- **Seleccionar posición**: usa el desplegable "Posición a analizar" y el botón **Ver Gráfica de riesgo y editar**.
- **Análisis del riesgo (medidor)**: gráfico tipo termómetro que indica Favorable / Evaluar / Desfavorable y Ganando o Perdiendo según P&L. Resume P&L, precio vs BE, DTE, retorno y earnings.
- **Copiar / Compartir**: en el expander puedes copiar el resumen de la posición para compartir por mensaje o correo (útil en móvil).
- **Gestionar posición**: editar comentario, ver historial, cerrar posición o eliminar (según estado).
        """)

    with st.expander("📑 Reportes y exportar", expanded=False):
        st.markdown("""
En la pestaña **📑 Reportes**:

- Elige **Desde** y **Hasta** (fechas de los trades).
- Filtros opcionales: **Ticker**, **Estrategia**, **Estado** (Abierto/Cerrado).
- Vista previa de trades y **Tax Efficiency** (total realizado, por ticker, por estrategia).
- **Descargar**: CSV, Excel o PDF de la bitácora para impuestos o análisis externo.
        """)

    with st.expander("👤 Mi cuenta: configuración", expanded=False):
        st.markdown("""
- **Token Tradier**: pegar y guardar; elegir entorno **sandbox** (pruebas) o **prod** (real).
- **Capital, meta anual, máx. por ticker**: actualizar y guardar.
- **Alpha Vantage**: verificar/guardar clave para earnings y datos fundamentales en el screener.
        """)

    st.markdown("---")
    st.caption("¿Dudas? Revisa cada sección desplegable según lo que quieras hacer: buscar opciones, registrar una posición o ver el riesgo de una operación.")


def render_screener_page(user_id: int) -> None:
    """
    Screener por usuario: filtros y acciones en el contenido principal (web y móvil sin depender del sidebar).
    """
    token, env = _get_tradier_token_for_user(user_id)
    api_tradier = "https://api.tradier.com/v1/" if (env or "sandbox") == "prod" else "https://sandbox.tradier.com/v1/"
    headers_tradier = {"Authorization": f"Bearer {token.strip()}", "Accept": "application/json"} if token else {}
    settings = get_user_screener_settings(user_id) if user_id else {}
    saved_av = (settings.get("av_api_key") or "").strip()
    bunkers = get_user_bunkers(user_id) if user_id else []

    # ---------- Filtros del Screener en el contenido principal (funciona en web y móvil) ----------
    with st.expander("🔎 Filtros del Screener", expanded=True):
        estrategia = st.radio("Estrategia", ["Cash Secured Put (CSP)", "Covered Call (CC)"], horizontal=True, key="scr_estrategia")
        st.caption("DTE: días hasta vencimiento. Delta: rango objetivo (CSP típ. -0.35 a -0.10, CC 0.10 a 0.35).")
        col_dte1, col_dte2 = st.columns(2)
        with col_dte1:
            dte_min = st.number_input("DTE mínimo (días)", min_value=0, max_value=365, value=7, step=1, key="scr_dte_min")
        with col_dte2:
            dte_max = st.number_input("DTE máximo (días)", min_value=0, max_value=365, value=30, step=1, key="scr_dte_max")
        dte_r = (min(dte_min, dte_max), max(dte_min, dte_max))
        delta_default_lo = -0.20 if estrategia == "Cash Secured Put (CSP)" else 0.10
        delta_default_hi = -0.10 if estrategia == "Cash Secured Put (CSP)" else 0.20
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            delta_lo = st.number_input("Delta mínimo", min_value=-0.50, max_value=0.50, value=float(delta_default_lo), step=0.05, format="%.2f", key="scr_delta_lo")
        with col_dl2:
            delta_hi = st.number_input("Delta máximo", min_value=-0.50, max_value=0.50, value=float(delta_default_hi), step=0.05, format="%.2f", key="scr_delta_hi")
        delta_r = (min(delta_lo, delta_hi), max(delta_lo, delta_hi))
        roi_min_f = st.number_input("ROI anualizado mínimo (%)", value=20.0, step=1.0, key="scr_roi")
        colateral_disponible = st.number_input("Colateral disponible ($)", value=10000.0, min_value=0.0, step=1000.0, format="%.0f", key="scr_colateral", help="0 = sin filtro. Solo opciones con colateral ≤ este valor.")
        st.markdown("---")
        av_key = st.text_input("Alpha Vantage Key", value=saved_av, type="password", placeholder="API key", key="screener_av_key")
        if st.button("Verificar y guardar clave", key="scr_av_btn"):
            if av_key and av_key.strip() and user_id:
                try:
                    r = requests.get("https://www.alphavantage.co/query", params={"function": "OVERVIEW", "symbol": "IBM", "apikey": av_key.strip()}, timeout=10)
                    data = r.json() if r.ok else {}
                    if isinstance(data, dict) and data.get("Error Message"):
                        st.error("Clave inválida.")
                    elif isinstance(data, dict) and data.get("Symbol"):
                        update_user_av_key(user_id, av_key.strip())
                        st.success("Clave guardada.")
                        st.rerun()
                    elif isinstance(data, dict) and data.get("Note") and ("rate" in str(data.get("Note", "")).lower() or "frequency" in str(data.get("Note", "")).lower()):
                        update_user_av_key(user_id, av_key.strip())
                        st.warning("Clave válida (límite excedido). Guardada.")
                        st.rerun()
                    else:
                        st.error("No se pudo verificar la clave.")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("Escribe la clave y guarda.")
        f_sma = st.checkbox("Strikes bajo SMA 200", value=False, key="scr_sma")
        f_stoch = st.checkbox("Stoch < 30", value=False, key="scr_stoch")
        f_earnings = st.checkbox("Evitar earnings", value=False, key="scr_earn")

        bunker_options = [(b["bunker_id"], f"{b['name']} ({len([x for x in (b.get('tickers_text') or '').split(',') if x.strip()])} tickers)") for b in bunkers]
        if not bunker_options:
            selected_bunker_id = None
            st.caption("Sin búnkeres. Crea uno en **Gestionar búnkers** (abajo).")
        else:
            idx_sel = st.selectbox("Búnker para escaneo", range(len(bunker_options)), format_func=lambda i: bunker_options[i][1], key="scr_bunker_sel")
            selected_bunker_id = bunker_options[idx_sel][0]
        tickers_clean = []
        if selected_bunker_id:
            bunker_data = get_bunker_by_id(selected_bunker_id, user_id)
            if bunker_data and bunker_data.get("tickers_text"):
                tickers_clean = sorted({x.strip().upper() for x in bunker_data["tickers_text"].split(",") if x.strip()})

        with st.expander("🏗️ Gestionar búnkers", expanded=False):
            st.caption("Varios búnkeres permiten búsquedas selectivas y ahorran uso de datos (APIs gratuitas).")
            st.markdown("#### ➕ Crear búnker")
            new_bunker_name = st.text_input("Nombre del nuevo búnker", value="", placeholder="Ej. Tech, Dividendos", key="new_bunker_name")
            new_bunker_tickers = st.text_area("Tickers (separados por coma)", value="", height=80, key="new_bunker_ta", placeholder="AAPL, MSFT, NVDA")
            if st.button("➕ Crear búnker", key="create_bunker_btn"):
                if user_id and new_bunker_name and new_bunker_name.strip():
                    bid = create_bunker(user_id, new_bunker_name.strip(), new_bunker_tickers or "")
                    if bid:
                        st.success(f"Búnker «{new_bunker_name.strip()}» creado.")
                        st.rerun()
                    else:
                        st.warning("Nombre ya existe. Elige otro.")
                else:
                    st.warning("Escribe un nombre.")
            st.markdown("---")
            st.markdown("#### ✏️ Editar o eliminar búnker")
            if bunkers:
                edit_options = [(b["bunker_id"], b["name"]) for b in bunkers]
                edit_idx = st.selectbox("Editar búnker", range(len(edit_options)), format_func=lambda i: edit_options[i][1], key="edit_bunker_sel")
                edit_bunker_id = edit_options[edit_idx][0]
                edit_bunker = get_bunker_by_id(edit_bunker_id, user_id)
                edit_name = st.text_input("Nombre", value=edit_bunker.get("name", "") if edit_bunker else "", key="edit_bunker_name")
                edit_tickers = st.text_area("Tickers (coma)", value=edit_bunker.get("tickers_text", "") if edit_bunker else "", height=80, key="edit_bunker_ta")
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("💾 Guardar", key="save_edit_bunker_btn"):
                        if user_id and edit_name and edit_name.strip():
                            ok = update_bunker(edit_bunker_id, user_id, edit_name.strip(), edit_tickers or "")
                            if ok:
                                st.success("Búnker actualizado.")
                                st.rerun()
                with col_b:
                    if st.button("🗑️ Eliminar", key="del_bunker_btn"):
                        if delete_bunker(edit_bunker_id, user_id):
                            st.success("Búnker eliminado.")
                            st.rerun()

        st.markdown("---")
        origen_sel = st.selectbox("Origen", ["🏗️ BÚNKER", "🎯 INDIVIDUAL"], key="origen_escaneo")
        if origen_sel == "🎯 INDIVIDUAL" or estrategia == "Covered Call (CC)":
            single_ticker = st.text_input("Ticker individual", "NVDA", key="single_ticker").strip().upper()
            tickers_lista = [single_ticker] if single_ticker else []
        else:
            tickers_lista = list(tickers_clean)
        run_scan = st.button("🚀 Iniciar barrido", type="primary", use_container_width=True, key="scr_run_btn")

        st.markdown("---")
        st.caption("Analizar un contrato (formato Thinkorswim)")
        manual_symbol = st.text_input("Símbolo opción", value=st.session_state.get("screener_manual_symbol", ""), placeholder=".NOW260227P105 o .NOW260227C108", key="manual_option_symbol")
        col_an, col_cl = st.columns(2)
        with col_an:
            if st.button("Analizar contrato", key="analyze_manual_btn"):
                if manual_symbol and manual_symbol.strip():
                    st.session_state["screener_manual_symbol"] = manual_symbol.strip()
                    st.rerun()
        with col_cl:
            if st.button("Limpiar", key="clear_manual_btn"):
                if "screener_manual_symbol" in st.session_state:
                    del st.session_state["screener_manual_symbol"]
                st.rerun()

    # ---------- Mensajes si falta config o datos ----------
    if not token:
        st.info("Configura el **token Tradier** en **Mi cuenta** (cambia de vista arriba) para ejecutar el barrido.")
        return
    if not tickers_lista and not st.session_state.get("screener_manual_symbol"):
        st.info("Arriba: crea un **búnker** en **Gestionar búnkers** y selecciónalo, o elige **Individual** y escribe un ticker, o pega un símbolo Thinkorswim para analizar un contrato.")
        return

    @st.cache_data(ttl=86400, show_spinner=False)
    def _sync_global_earnings(av_key_local: str):
        if not av_key_local:
            return {}
        try:
            r = requests.get(
                "https://www.alphavantage.co/query",
                params={
                    "function": "EARNINGS_CALENDAR",
                    "horizon": "3month",
                    "apikey": av_key_local,
                },
                timeout=15,
            )
            return pd.read_csv(io.StringIO(r.text)).set_index("symbol")["reportDate"].to_dict()
        except Exception:
            return {}

    @st.cache_data(ttl=86400, show_spinner=False)
    def _get_hybrid_overview(sym: str, av_key_local: str):
        if av_key_local:
            try:
                r = requests.get(
                    "https://www.alphavantage.co/query",
                    params={"function": "OVERVIEW", "symbol": sym, "apikey": av_key_local},
                    timeout=8,
                ).json()
                if "Symbol" in r and float(r.get("AnalystTargetPrice", 0)) > 0:
                    return {
                        "target": round(float(r.get("AnalystTargetPrice", 0)), 2),
                        "margin": round(float(r.get("OperatingMarginTTM", 0)) * 100, 2),
                        "roe": round(float(r.get("ReturnOnEquityTTM", 0)) * 100, 2),
                        "debt": round(float(r.get("DebtToEquityRatio", 0)), 2),
                        "source": "Alpha Vantage",
                    }
            except Exception:
                pass
        try:
            t = yf.Ticker(sym)
            info = t.info
            return {
                "target": round(info.get("targetMeanPrice", 0), 2),
                "margin": round(info.get("operatingMargins", 0) * 100, 2),
                "roe": round(info.get("returnOnEquity", 0) * 100, 2),
                "debt": round((info.get("debtToEquity", 0) or 0) / 100, 2),
                "source": "Yahoo Finance",
            }
        except Exception:
            return None

    @st.cache_data(ttl=3600, show_spinner=False)
    def _get_market_techs(sym: str):
        params = {
            "symbol": sym,
            "interval": "daily",
            "start": (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d"),
        }
        try:
            r = requests.get(
                f"{api_tradier}markets/history",
                params=params,
                headers=headers_tradier,
                timeout=10,
            ).json()
            df = pd.DataFrame(r["history"]["day"])
            close = df["close"].astype(float)
            sma200 = close.iloc[-200:].mean()
            sma40 = close.iloc[-40:].mean()
            low_14 = df["low"].astype(float).rolling(14).min()
            high_14 = df["high"].astype(float).rolling(14).max()
            stoch = 100 * ((close - low_14) / (high_14 - low_14))
            tr = np.maximum(
                df["high"].astype(float) - df["low"].astype(float),
                abs(df["high"].astype(float) - close.shift(1)),
            )
            hv = np.log(close / close.shift(1)).std() * np.sqrt(252) * 100
            return round(sma200, 2), round(sma40, 2), round(stoch.rolling(3).mean().iloc[-1], 2), round(
                tr.rolling(14).mean().iloc[-1], 2
            ), round(hv, 2)
        except Exception:
            return None, None, 50.0, 0.0, 0.0

    earnings_db = _sync_global_earnings(av_key)

    # Analizar contrato manual (formato Thinkorswim)
    manual_sym = st.session_state.get("screener_manual_symbol")
    if manual_sym:
        col_back_tos, _ = st.columns([1, 4])
        with col_back_tos:
            if st.button("← Volver al menú", type="secondary", key="back_from_tos", use_container_width=True):
                if "screener_manual_symbol" in st.session_state:
                    del st.session_state["screener_manual_symbol"]
                st.rerun()
        parsed = _parse_thinkorswim_symbol(manual_sym)
        if not parsed:
            st.error("Formato de símbolo no válido. Usa formato Thinkorswim: .ROOTYYMMDDP/CSTRIKE (ej. .NOW260227P105 o .NOW260227C108)")
        else:
            occ = parsed["occ_symbol"]
            ticker = parsed["ticker"]
            exp_str = parsed["exp_str"]
            exp_date = parsed["exp_date"]
            option_type = parsed["option_type"]
            strike = parsed["strike"]
            today = datetime.now()
            dte = (exp_date - today.date()).days

            try:
                opt_q = requests.get(
                    f"{api_tradier}markets/quotes",
                    params={"symbols": occ},
                    headers=headers_tradier,
                    timeout=10,
                ).json()
                und_q = requests.get(
                    f"{api_tradier}markets/quotes",
                    params={"symbols": ticker},
                    headers=headers_tradier,
                    timeout=10,
                ).json()
            except Exception as e:
                st.error(f"Error al obtener cotizaciones: {e}")
            else:
                # Tradier puede devolver quote como objeto o como lista de uno
                def _normalize_quote(resp: dict, key: str = "quote") -> dict | None:
                    q = (resp.get("quotes") or {}).get(key) or resp.get(key)
                    if q is None:
                        return None
                    if isinstance(q, list):
                        return q[0] if q else None
                    return q

                opt_quote = _normalize_quote(opt_q)
                und_quote = _normalize_quote(und_q)
                if not und_quote:
                    st.error("No se pudo obtener cotización del subyacente. Comprueba que el ticker sea correcto.")
                elif not opt_quote:
                    # Fallback: obtener contrato desde la chain de opciones (símbolo + vencimiento)
                    try:
                        chain = requests.get(
                            f"{api_tradier}markets/options/chains",
                            params={"symbol": ticker, "expiration": exp_str, "greeks": "true"},
                            headers=headers_tradier,
                            timeout=10,
                        ).json()
                    except Exception as e:
                        st.error(f"No se encontró el contrato y falló la chain: {e}")
                    else:
                        opts = (chain or {}).get("options", {}).get("option")
                        if not opts:
                            st.error("No se pudo obtener cotización de la opción. Ese vencimiento o strike puede no existir en Tradier.")
                        else:
                            if isinstance(opts, dict):
                                opts = [opts]
                            opt = None
                            for o in opts:
                                if o.get("option_type") == option_type and abs(float(o.get("strike", 0)) - strike) < 0.01:
                                    opt = o
                                    break
                            if not opt:
                                st.error("No se encontró ese strike/tipo en la chain. Comprueba el símbolo.")
                            else:
                                price = float(und_quote.get("last") or und_quote.get("close") or 0)
                                bid = float(opt.get("bid") or 0)
                                ask = float(opt.get("ask") or 0)
                                premium = round((bid + ask) / 2, 2) if (bid or ask) else 0.0
                                greeks = opt.get("greeks") or {}
                                delta = float(greeks.get("delta") or 0) if isinstance(greeks, dict) else 0.0
                                mid_iv = float(greeks.get("mid_iv") or 0) * 100 if isinstance(greeks, dict) else 0.0
                                sma200, sma40, stoch_v, atr_v, hv_v = _get_market_techs(ticker) or (None, None, 50.0, 0.0, 0.0)
                                e_date = earnings_db.get(ticker)
                                es_earn = "SÍ" if e_date and exp_str >= e_date >= today.strftime("%Y-%m-%d") else "NO"
                                is_put = option_type == "put"
                                base = strike if is_put else price
                                be_val = round(strike - premium, 2) if is_put else round(price - premium, 2)
                                roi_a = round(((premium / base) * 100) * (365 / max(dte, 1)), 2)
                                row = {
                                    "Ticker": ticker,
                                    "Exp": exp_str,
                                    "DTE": dte,
                                    "Precio": price,
                                    "Strike": strike,
                                    "Prima": premium,
                                    "Ret. %": round((premium / base) * 100, 2),
                                    "ROI Ann %": roi_a,
                                    "Delta": round(delta, 2),
                                    "POP %": round((1 + delta) * 100, 2),
                                    "BE": be_val,
                                    "Earnings": es_earn,
                                    "earn_date": e_date,
                                    "Stoch": stoch_v or 50.0,
                                    "sma200_val": sma200,
                                    "sma40_val": sma40,
                                    "atr_val": atr_v or 0.0,
                                    "hv": hv_v or 0.0,
                                    "iv": mid_iv,
                                }
                                st.markdown("### 🔍 Análisis de contrato (Thinkorswim)")
                                st.caption(f"Símbolo: {manual_sym} (desde chain)")
                                st.markdown("---")
                                st.subheader(f"🔍 Ficha Sniper: {row['Ticker']} · Strike ${row['Strike']:,.2f}")
                                c1, c2, c3, c4 = st.columns(4)
                                with c1:
                                    st.markdown(f"<div class='metric-card'><b style='color:#2ecc71'>ROI ANUAL</b><br><h3>{row['ROI Ann %']:,.2f}%</h3><b>DTE: {row['DTE']}</b></div>", unsafe_allow_html=True)
                                with c2:
                                    st.markdown(f"<div class='metric-card'><b>RETORNO PERIODO</b><br><h3>{row['Ret. %']:,.2f}%</h3><b>{int(row.get('DTE', 0))} días</b></div>", unsafe_allow_html=True)
                                with c3:
                                    st.markdown(f"<div class='metric-card'><b>COLLATERAL</b><br><h3>${(row['Strike']*100):,.2f}</h3><b>PRIMA: ${(row['Prima']*100):,.2f}</b></div>", unsafe_allow_html=True)
                                with c4:
                                    st.markdown(f"<div class='metric-card'><b style='color:#e74c3c'>CAPITAL RIESGO</b><br><h3>${(row['Strike'] - row['Prima']) * 100:,.2f}</h3><b>BE: ${row['BE']:,.2f}</b></div>", unsafe_allow_html=True)
                                st.markdown(f"""<div class='vola-master'><h3 style='margin:0; color:#9b59b6;'>📡 Radar de Volatilidad & Riesgo</h3><table style='width:100%; border-collapse: collapse; margin-top:15px;'><tr style='font-size:16px;'><td style='padding:8px;'><b>IV actual:</b> {row['iv']:,.2f}%</td><td style='padding:8px;'><b>HV (histórica):</b> {row['hv']:,.2f}%</td><td style='padding:8px;'><b>ATR (14D):</b> ${row['atr_val']:,.2f}</td><td style='padding:8px; background: rgba(0,242,255,0.1); border-radius:10px; text-align:center;'>{'🎯 <b style="color:#2ecc71">RECOMENDACIÓN: vender prima</b>' if row['iv'] > row['hv'] and row['Earnings'] == 'NO' else '⚖️ <b style="color:#f39c12">RECOMENDACIÓN: evaluar riesgo</b>'}</td></tr></table></div>""", unsafe_allow_html=True)
                                sma200_cf = row.get("sma200_val")
                                strike_ok_cf = (sma200_cf is None or (isinstance(sma200_cf, float) and np.isnan(sma200_cf)) or float(row["Strike"]) < float(sma200_cf))
                                stoch_cf = row.get("Stoch") or 50.0
                                stoch_ok_cf = float(stoch_cf) < 30 if stoch_cf is not None else False
                                earn_ok_cf = row.get("Earnings") != "SÍ"
                                st.markdown(f"""<div class='vola-master' style='margin-top:12px;'><h3 style='margin:0; color:#9b59b6;'>⚠️ Riesgos del contrato</h3><table style='width:100%; border-collapse: collapse; margin-top:10px;'><tr style='font-size:15px;'><td style='padding:8px;'><b>SMA 200:</b> {'✅ Strike bajo SMA 200' if strike_ok_cf else '⚠️ Strike sobre SMA 200'}</td><td style='padding:8px;'><b>Stochastic full &lt;30:</b> {'✅ Cumple' if stoch_ok_cf else '⚠️ No cumple'}</td><td style='padding:8px;'><b>Earnings:</b> {'✅ No hay' if earn_ok_cf else '⚠️ Hay earnings'}</td></tr></table></div>""", unsafe_allow_html=True)
                                if av_key:
                                    av = _get_hybrid_overview(row["Ticker"], av_key)
                                    if av:
                                        up = round(((av["target"] - row["Precio"]) / row["Precio"]) * 100, 2)
                                        st.markdown(f"""<div class='fundamental-box'><b>📊 Perfil financiero ({av['source']}):</b><br>Márgenes: <b class='status-ok'>{av['margin']:,.2f}%</b> · ROE: <b class='status-ok'>{av['roe']:,.2f}%</b> · Deuda/Eq: <b class='status-ok'>{av['debt']:,.2f}</b><br>Target analistas: <b class='status-ok'>${av['target']:,.2f}</b> · Potencial: <b class='status-ok'>{up:,.2f}%</b></div>""", unsafe_allow_html=True)
                                st.markdown("### Análisis del riesgo (medidor)")
                                prems_f = row["Prima"] * 100
                                strk_f, be_f, mkt_f = strike, row["BE"], row["Precio"]
                                is_put_f = option_type == "put"
                                pnl_f = prems_f - (max(0, (strk_f - mkt_f) * 100) if is_put_f else max(0, (mkt_f - strk_f) * 100))
                                dte_f = int(row.get("DTE", 0) or 0)
                                ret_pct_f = float(row.get("Ret. %", 0))
                                earnings_ok_f = row.get("Earnings") != "SÍ"
                                from app.position_chart_utils import risk_analysis_score, build_gauge_price_axis, build_copyable_summary_from_row
                                score_f = risk_analysis_score(pnl_f, mkt_f, be_f, is_put_f, dte_f, ret_pct_f, earnings_ok_f)
                                status_f = "Favorable" if score_f > 66 else ("Evaluar" if score_f > 33 else "Desfavorable")
                                fig_gauge_f = build_gauge_price_axis(
                                    strike, be_f, mkt_f, dte_f, status_f,
                                    title="Análisis del riesgo",
                                    is_put=is_put_f,
                                )
                                st.plotly_chart(fig_gauge_f, use_container_width=True)
                                pop_f = float(row.get("POP %", 0) or 0)
                                st.markdown(f"""<div class="rad-metrics rad-metrics-grid"><div class="rad-metric"><span class="k">Precio (actual)</span><span class="v">${fmt2(mkt_f)}</span></div><div class="rad-metric"><span class="k">Strike (ejercicio)</span><span class="v">${fmt2(strike)}</span></div><div class="rad-metric"><span class="k">BE (breakeven)</span><span class="v">${fmt2(be_f)}</span></div><div class="rad-metric"><span class="k">DTE (días a venc.)</span><span class="v">{dte_f} días</span></div><div class="rad-metric"><span class="k">Ret. periodo (%)</span><span class="v">{ret_pct_f:,.2f}%</span></div><div class="rad-metric"><span class="k">POP %</span><span class="v">{pop_f:,.2f}%</span></div><div class="rad-metric"><span class="k">P&L actual ($)</span><span class="v">${fmt2(pnl_f)}</span></div><div class="rad-metric"><span class="k">Max ganancia ($)</span><span class="v" style="color:#3fb950">${fmt2(prems_f)}</span></div></div>""", unsafe_allow_html=True)
                                with st.expander("📋 Copiar / Compartir resumen del contrato", expanded=False):
                                    copy_text_f = build_copyable_summary_from_row(row, "CSP" if is_put_f else "CC")
                                    st.text_area("Resumen", value=copy_text_f, height=160, key="copy_chain_fallback", disabled=True, label_visibility="collapsed")
                                    st.caption("Selecciona todo el texto y cópialo para compartir.")
                else:
                    price = float(und_quote.get("last") or und_quote.get("close") or 0)
                    bid = float(opt_quote.get("bid") or 0)
                    ask = float(opt_quote.get("ask") or 0)
                    premium = round((bid + ask) / 2, 2) if (bid or ask) else 0.0
                    greeks = opt_quote.get("greeks") or {}
                    if isinstance(greeks, dict):
                        delta = float(greeks.get("delta") or 0)
                        mid_iv = float(greeks.get("mid_iv") or 0) * 100
                    else:
                        delta = 0.0
                        mid_iv = 0.0
                    sma200, sma40, stoch_v, atr_v, hv_v = _get_market_techs(ticker) or (None, None, 50.0, 0.0, 0.0)
                    e_date = earnings_db.get(ticker)
                    es_earn = "SÍ" if e_date and exp_str >= e_date >= today.strftime("%Y-%m-%d") else "NO"
                    is_put = option_type == "put"
                    base = strike if is_put else price
                    be_val = round(strike - premium, 2) if is_put else round(price - premium, 2)
                    roi_a = round(((premium / base) * 100) * (365 / max(dte, 1)), 2)
                    row = {
                        "Ticker": ticker,
                        "Exp": exp_str,
                        "DTE": dte,
                        "Precio": price,
                        "Strike": strike,
                        "Prima": premium,
                        "Ret. %": round((premium / base) * 100, 2),
                        "ROI Ann %": roi_a,
                        "Delta": round(delta, 2),
                        "POP %": round((1 + delta) * 100, 2),
                        "BE": be_val,
                        "Earnings": es_earn,
                        "earn_date": e_date,
                        "Stoch": stoch_v or 50.0,
                        "sma200_val": sma200,
                        "sma40_val": sma40,
                        "atr_val": atr_v or 0.0,
                        "hv": hv_v or 0.0,
                        "iv": mid_iv,
                    }
                    st.markdown("### 🔍 Análisis de contrato (Thinkorswim)")
                    st.caption(f"Símbolo: {manual_sym}")
                    st.markdown("---")
                    st.subheader(f"🔍 Ficha Sniper: {row['Ticker']} · Strike ${row['Strike']:,.2f}")

                    c1, c2, c3, c4 = st.columns(4)
                    with c1:
                        st.markdown(
                            f"<div class='metric-card'><b style='color:#2ecc71'>ROI ANUAL</b><br><h3>{row['ROI Ann %']:,.2f}%</h3><b>DTE: {row['DTE']}</b></div>",
                            unsafe_allow_html=True,
                        )
                    with c2:
                        st.markdown(
                            f"<div class='metric-card'><b>RETORNO PERIODO</b><br><h3>{row['Ret. %']:,.2f}%</h3><b>{int(row.get('DTE', 0))} días</b></div>",
                            unsafe_allow_html=True,
                        )
                    with c3:
                        st.markdown(
                            f"<div class='metric-card'><b>COLLATERAL</b><br><h3>${(row['Strike']*100):,.2f}</h3><b>PRIMA: ${(row['Prima']*100):,.2f}</b></div>",
                            unsafe_allow_html=True,
                        )
                    with c4:
                        st.markdown(
                            f"<div class='metric-card'><b style='color:#e74c3c'>CAPITAL RIESGO</b><br><h3>${(row['Strike'] - row['Prima']) * 100:,.2f}</h3><b>BE: ${row['BE']:,.2f}</b></div>",
                            unsafe_allow_html=True,
                        )

                    st.markdown(
                        f"""
                        <div class='vola-master'>
                            <h3 style='margin:0; color:#9b59b6;'>📡 Radar de Volatilidad & Riesgo</h3>
                            <table style='width:100%; border-collapse: collapse; margin-top:15px;'>
                                <tr style='font-size:16px;'>
                                    <td style='padding:8px;'><b>IV actual:</b> {row['iv']:,.2f}%</td>
                                    <td style='padding:8px;'><b>HV (histórica):</b> {row['hv']:,.2f}%</td>
                                    <td style='padding:8px;'><b>ATR (14D):</b> ${row['atr_val']:,.2f}</td>
                                    <td style='padding:8px; background: rgba(0,242,255,0.1); border-radius:10px; text-align:center;'>
                                        {'🎯 <b style="color:#2ecc71">RECOMENDACIÓN: vender prima</b>' if row['iv'] > row['hv'] and row['Earnings'] == 'NO' else '⚖️ <b style="color:#f39c12">RECOMENDACIÓN: evaluar riesgo</b>'}
                                    </td>
                                </tr>
                            </table>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    # Riesgos: SMA200, Stochastic full <30, Earnings
                    sma200_r = row.get("sma200_val")
                    strike_ok_sma = (sma200_r is None or (isinstance(sma200_r, float) and np.isnan(sma200_r)) or float(row["Strike"]) < float(sma200_r))
                    stoch_v = row.get("Stoch") or 50.0
                    stoch_ok = float(stoch_v) < 30 if stoch_v is not None else False
                    earn_ok = row.get("Earnings") != "SÍ"
                    st.markdown(
                        f"""
                        <div class='vola-master' style='margin-top:12px;'>
                            <h3 style='margin:0; color:#9b59b6;'>⚠️ Riesgos del contrato</h3>
                            <table style='width:100%; border-collapse: collapse; margin-top:10px;'>
                                <tr style='font-size:15px;'>
                                    <td style='padding:8px;'><b>SMA 200:</b> {'✅ Strike bajo SMA 200 (sin riesgo)' if strike_ok_sma else '⚠️ Strike sobre SMA 200 (riesgo)'}</td>
                                    <td style='padding:8px;'><b>Stochastic full &lt;30:</b> {'✅ Cumple (sobreventa)' if stoch_ok else '⚠️ No cumple'}</td>
                                    <td style='padding:8px;'><b>Earnings:</b> {'✅ No hay en periodo' if earn_ok else '⚠️ Hay earnings en el periodo'}</td>
                                </tr>
                            </table>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    if av_key:
                        av = _get_hybrid_overview(row["Ticker"], av_key)
                        if av:
                            up = round(((av["target"] - row["Precio"]) / row["Precio"]) * 100, 2)
                            st.markdown(
                                f"""
                                <div class='fundamental-box'>
                                   <b>📊 Perfil financiero ({av['source']}):</b><br>
                                   Márgenes: <b class='status-ok'>{av['margin']:,.2f}%</b> · ROE: <b class='status-ok'>{av['roe']:,.2f}%</b> · Deuda/Eq: <b class='status-ok'>{av['debt']:,.2f}</b><br>
                                   Target analistas: <b class='status-ok'>${av['target']:,.2f}</b> · Potencial: <b class='status-ok'>{up:,.2f}%</b>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                    st.markdown("### Análisis del riesgo (medidor)")
                    is_put_chart = option_type == "put"
                    prems_m = row["Prima"] * 100
                    strk_m = strike
                    be_m = row["BE"]
                    mkt_m = row["Precio"]
                    pnl_m = prems_m - (max(0, (strk_m - mkt_m) * 100) if is_put_chart else max(0, (mkt_m - strk_m) * 100))
                    dte_m = int(row.get("DTE", 0) or 0)
                    ret_pct_m = float(row.get("Ret. %", 0))
                    earnings_ok_m = row.get("Earnings") != "SÍ"
                    from app.position_chart_utils import risk_analysis_score, build_gauge_price_axis, build_copyable_summary_from_row
                    score_m = risk_analysis_score(pnl_m, mkt_m, be_m, is_put_chart, dte_m, ret_pct_m, earnings_ok_m)
                    status_m = "Favorable" if score_m > 66 else ("Evaluar" if score_m > 33 else "Desfavorable")
                    fig_gauge_m = build_gauge_price_axis(
                        strike, be_m, mkt_m, dte_m, status_m,
                        title="Análisis del riesgo",
                        is_put=is_put_chart,
                    )
                    st.plotly_chart(fig_gauge_m, use_container_width=True)
                    pop_m = float(row.get("POP %", 0) or 0)
                    st.markdown(
                        f"""
                        <div class="rad-metrics rad-metrics-grid">
                            <div class="rad-metric"><span class="k">Precio (actual)</span><span class="v">${fmt2(mkt_m)}</span></div>
                            <div class="rad-metric"><span class="k">Strike (ejercicio)</span><span class="v">${fmt2(strike)}</span></div>
                            <div class="rad-metric"><span class="k">BE (breakeven)</span><span class="v">${fmt2(be_m)}</span></div>
                            <div class="rad-metric"><span class="k">DTE (días a venc.)</span><span class="v">{dte_m} días</span></div>
                            <div class="rad-metric"><span class="k">Ret. periodo (%)</span><span class="v">{ret_pct_m:,.2f}%</span></div>
                            <div class="rad-metric"><span class="k">POP %</span><span class="v">{pop_m:,.2f}%</span></div>
                            <div class="rad-metric"><span class="k">P&L actual ($)</span><span class="v">${fmt2(pnl_m)}</span></div>
                            <div class="rad-metric"><span class="k">Max ganancia ($)</span><span class="v" style="color:#3fb950">${fmt2(prems_m)}</span></div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    with st.expander("📋 Copiar / Compartir resumen del contrato", expanded=False):
                        copy_text_m = build_copyable_summary_from_row(row, "CSP" if is_put_chart else "CC")
                        st.text_area("Resumen (selecciona y copia)", value=copy_text_m, height=160, key="copy_manual_quote", disabled=True, label_visibility="collapsed")
                        st.caption("Selecciona todo el texto y cópialo para compartir (móvil: mantén pulsado).")
        return

    if run_scan:
        res_list = []
        st.markdown("### 🔎 Screener — Resultados del barrido")
        prog = st.progress(0.0)
        today = datetime.now()
        total = len(tickers_lista)

        for idx, sym in enumerate(tickers_lista):
            if not sym:
                continue
            try:
                q_res = requests.get(
                    f"{api_tradier}markets/quotes",
                    params={"symbols": sym},
                    headers=headers_tradier,
                    timeout=10,
                ).json()
            except Exception:
                continue
            quote_data = q_res.get("quotes", {}).get("quote")
            if not quote_data:
                continue
            price = float(quote_data.get("last", 0) or 0)
            sma200, sma40, stoch_v, atr_v, hv_v = _get_market_techs(sym)

            e_date = earnings_db.get(sym)
            try:
                exps = requests.get(
                    f"{api_tradier}markets/options/expirations",
                    params={"symbol": sym},
                    headers=headers_tradier,
                    timeout=10,
                ).json()
            except Exception:
                continue
            if not exps or "expirations" not in exps:
                continue

            for d_str in exps["expirations"]["date"]:
                dte = (datetime.strptime(d_str, "%Y-%m-%d") - today).days
                if not (dte_r[0] <= dte <= dte_r[1]):
                    continue
                try:
                    chain = requests.get(
                        f"{api_tradier}markets/options/chains",
                        params={"symbol": sym, "expiration": d_str, "greeks": "true"},
                        headers=headers_tradier,
                        timeout=10,
                    ).json()
                except Exception:
                    continue
                if not chain or "options" not in chain or not chain["options"]:
                    continue
                opts = chain["options"]["option"]
                if isinstance(opts, dict):
                    opts = [opts]

                for opt in opts:
                    opt_type = "put" if estrategia == "Cash Secured Put (CSP)" else "call"
                    if opt.get("option_type") != opt_type:
                        continue
                    strike = float(opt["strike"])
                    bid = opt.get("bid") or 0.0
                    ask = opt.get("ask") or 0.0
                    premium = round(float((bid + ask) / 2), 2)

                    if estrategia == "Cash Secured Put (CSP)":
                        base = strike
                        delta = float(opt.get("greeks", {}).get("delta", 0) or 0.0)
                    else:
                        base = price
                        delta = float(opt.get("greeks", {}).get("delta", 0) or 0.0)

                    lo, hi = min(delta_r[0], delta_r[1]), max(delta_r[0], delta_r[1])
                    if not (lo <= delta <= hi):
                        continue

                    if f_sma and sma200 and strike >= sma200:
                        continue
                    if f_stoch and stoch_v >= 30:
                        continue

                    es_earn = "SÍ" if e_date and d_str >= e_date >= today.strftime("%Y-%m-%d") else "NO"
                    if f_earnings and es_earn == "SÍ":
                        continue

                    roi_a = round(((premium / base) * 100) * (365 / max(dte, 1)), 2)
                    if roi_a < roi_min_f:
                        continue
                    colateral_req = strike * 100 if estrategia == "Cash Secured Put (CSP)" else price * 100
                    if colateral_disponible and colateral_disponible > 0 and colateral_req > colateral_disponible:
                        continue
                    be_val = (
                        round(strike - premium, 2)
                        if estrategia == "Cash Secured Put (CSP)"
                        else round(price - premium, 2)
                    )
                    res_list.append(
                        {
                            "Ticker": sym,
                            "Exp": d_str,
                            "DTE": dte,
                            "Precio": price,
                            "Strike": strike,
                            "Prima": premium,
                            "Ret. %": round((premium / base) * 100, 2),
                            "ROI Ann %": roi_a,
                            "Delta": round(delta, 2),
                            "POP %": round((1 + delta) * 100, 2),
                            "BE": be_val,
                            "Earnings": es_earn,
                            "earn_date": e_date,
                            "Stoch": stoch_v,
                            "sma200_val": sma200,
                            "sma40_val": sma40,
                            "atr_val": atr_v,
                            "hv": hv_v,
                            "iv": (opt.get("greeks", {}).get("mid_iv", 0) or 0.0) * 100
                            if isinstance(opt.get("greeks"), dict)
                            else 0.0,
                        }
                    )
            prog.progress((idx + 1) / float(total))

        df_res = pd.DataFrame(res_list)
        st.session_state["screener_res"] = df_res

    df = st.session_state.get("screener_res")
    if df is None or df.empty:
        st.markdown("### 🔎 Screener")
        st.caption("Usa el botón **Iniciar barrido** en **Filtros del Screener** (arriba) para ejecutar el escaneo. Los resultados aparecerán aquí.")
        return

    st.markdown("### 📊 Dashboard de resultados")
    df_v = df.copy()
    df_v["SMA 200"] = df_v.apply(
        lambda r: "✅" if r["sma200_val"] and r["Strike"] < r["sma200_val"] else "⚠️",
        axis=1,
    )
    df_v["Stoch 📉"] = df_v["Stoch"].map(lambda v: "✅" if v < 30 else "⚠️")
    for col in ["Precio", "Strike", "Prima", "BE", "Delta", "ROI Ann %", "Ret. %", "POP %"]:
        df_v[col] = df_v[col].map("{:,.2f}".format)

    df_show_scr = df_v[
        [
            "Ticker",
            "Exp",
            "DTE",
            "Precio",
            "Strike",
            "Prima",
            "Ret. %",
            "ROI Ann %",
            "Delta",
            "POP %",
            "BE",
            "Earnings",
            "SMA 200",
            "Stoch 📉",
        ]
    ]

    def _style_earnings(s):
        if s.name != "Earnings":
            return [""] * len(s)
        return [
            "background-color: rgba(63,185,80,0.22); color: #3fb950; font-weight: 600;"
            if v == "NO"
            else "background-color: rgba(248,81,73,0.25); color: #f85149; font-weight: 600;"
            for v in s
        ]

    styled_scr = df_show_scr.style.apply(_style_earnings, axis=0)

    event = st.dataframe(
        styled_scr,
        width="stretch",
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="screener_results_df",
    )

    # Acceso a filas seleccionadas: por atributos o por dict (según versión Streamlit); key persiste selección
    selected_rows = None
    try:
        sel_obj = getattr(event, "selection", None) or (event.get("selection") if isinstance(event, dict) else None)
        if sel_obj is not None:
            selected_rows = getattr(sel_obj, "rows", None) or (sel_obj.get("rows") if isinstance(sel_obj, dict) else None)
    except Exception:
        pass
    if not selected_rows and "screener_results_df" in st.session_state:
        try:
            ss = st.session_state.get("screener_results_df") or {}
            selected_rows = (ss.get("selection") or {}).get("rows")
        except Exception:
            pass
    if selected_rows:
        # Al seleccionar otra fila distinta a la que se cerró, volver a mostrar la ficha
        if selected_rows[0] != st.session_state.get("screener_closed_row_index", -1):
            st.session_state["screener_show_ficha"] = True
    if selected_rows and st.session_state.get("screener_show_ficha", True):
        row = df.iloc[selected_rows[0]]
        col_back_scr, _ = st.columns([1, 4])
        with col_back_scr:
            if st.button("← Volver a resultados", type="secondary", key="back_from_screener_ficha", use_container_width=True):
                st.session_state["screener_show_ficha"] = False
                st.session_state["screener_closed_row_index"] = selected_rows[0]
                st.rerun()
        st.markdown("---")
        st.subheader(f"🔍 Ficha Sniper: {row['Ticker']} · Strike ${row['Strike']:,.2f}")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(
                f"<div class='metric-card'><b style='color:#2ecc71'>ROI ANUAL</b><br><h3>{row['ROI Ann %']:,.2f}%</h3><b>DTE: {row['DTE']}</b></div>",
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                f"<div class='metric-card'><b>RETORNO PERIODO</b><br><h3>{row['Ret. %']:,.2f}%</h3><b>Prima/base · {int(row.get('DTE', 0))} días</b></div>",
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                f"<div class='metric-card'><b>COLLATERAL</b><br><h3>${(row['Strike']*100):,.2f}</h3><b>PRIMA: ${(row['Prima']*100):,.2f}</b></div>",
                unsafe_allow_html=True,
            )
        with c4:
            st.markdown(
                f"<div class='metric-card'><b style='color:#e74c3c'>CAPITAL RIESGO</b><br><h3>${(row['Strike'] - row['Prima']) * 100:,.2f}</h3><b>BE: ${row['BE']:,.2f}</b></div>",
                unsafe_allow_html=True,
            )

        st.markdown(
            f"""
            <div class='vola-master'>
                <h3 style='margin:0; color:#9b59b6;'>📡 Radar de Volatilidad & Riesgo</h3>
                <table style='width:100%; border-collapse: collapse; margin-top:15px;'>
                    <tr style='font-size:16px;'>
                        <td style='padding:8px;'><b>IV actual:</b> {row['iv']:,.2f}%</td>
                        <td style='padding:8px;'><b>HV (histórica):</b> {row['hv']:,.2f}%</td>
                        <td style='padding:8px;'><b>ATR (14D):</b> ${row['atr_val']:,.2f}</td>
                        <td style='padding:8px; background: rgba(0,242,255,0.1); border-radius:10px; text-align:center;'>
                            {'🎯 <b style="color:#2ecc71">RECOMENDACIÓN: vender prima</b>' if row['iv'] > row['hv'] and row['Earnings'] == 'NO' else '⚖️ <b style="color:#f39c12">RECOMENDACIÓN: evaluar riesgo</b>'}
                        </td>
                    </tr>
                </table>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if av_key:
            av = _get_hybrid_overview(row["Ticker"], av_key)
            if av:
                up = round(((av["target"] - row["Precio"]) / row["Precio"]) * 100, 2)
                st.markdown(
                    f"""
                    <div class='fundamental-box'>
                       <b>📊 Perfil financiero ({av['source']}):</b><br>
                       Márgenes: <b class='status-ok'>{av['margin']:,.2f}%</b> · ROE: <b class='status-ok'>{av['roe']:,.2f}%</b> · Deuda/Eq: <b class='status-ok'>{av['debt']:,.2f}</b><br>
                       Target analistas: <b class='status-ok'>${av['target']:,.2f}</b> · Potencial: <b class='status-ok'>{up:,.2f}%</b>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown("### Análisis del riesgo (medidor)")
        is_put = estrategia == "Cash Secured Put (CSP)"
        prems = row["Prima"] * 100
        strike = float(row["Strike"])
        be = float(row["BE"])
        mkt = float(row["Precio"])
        strk = strike or (mkt * 0.9)
        pnl_scr = prems - (max(0, (strk - mkt) * 100) if is_put else max(0, (mkt - strk) * 100))
        dte_scr = int(row.get("DTE", 0) or 0)
        ret_pct = float(row.get("Ret. %", 0))
        earnings_ok_scr = row.get("Earnings") != "SÍ"
        from app.position_chart_utils import risk_analysis_score, build_gauge_price_axis, build_copyable_summary_from_row
        score_scr = risk_analysis_score(pnl_scr, mkt, be, is_put, dte_scr, ret_pct, earnings_ok_scr)
        status_scr = "Favorable" if score_scr > 66 else ("Evaluar" if score_scr > 33 else "Desfavorable")
        fig_gauge_scr = build_gauge_price_axis(
            strike, be, mkt, dte_scr, status_scr,
            title="Análisis del riesgo",
            is_put=is_put,
        )
        st.plotly_chart(fig_gauge_scr, use_container_width=True)
        pop_scr = float(row.get("POP %", 0) or 0)
        st.markdown(
            f"""
            <div class="rad-metrics rad-metrics-grid">
                <div class="rad-metric"><span class="k">Precio (actual)</span><span class="v">${fmt2(mkt)}</span></div>
                <div class="rad-metric"><span class="k">Strike (ejercicio)</span><span class="v">${fmt2(strike)}</span></div>
                <div class="rad-metric"><span class="k">BE (breakeven)</span><span class="v">${fmt2(be)}</span></div>
                <div class="rad-metric"><span class="k">DTE (días a venc.)</span><span class="v">{dte_scr} días</span></div>
                <div class="rad-metric"><span class="k">Ret. periodo (%)</span><span class="v">{ret_pct:,.2f}%</span></div>
                <div class="rad-metric"><span class="k">POP %</span><span class="v">{pop_scr:,.2f}%</span></div>
                <div class="rad-metric"><span class="k">P&L actual ($)</span><span class="v">${fmt2(pnl_scr)}</span></div>
                <div class="rad-metric"><span class="k">Max ganancia ($)</span><span class="v" style="color:#3fb950">${fmt2(prems)}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.expander("📋 Copiar / Compartir resumen del contrato", expanded=False):
            copy_text_scr = build_copyable_summary_from_row(row, "CSP" if is_put else "CC")
            st.text_area("Resumen (selecciona y copia para compartir)", value=copy_text_scr, height=180, key="copy_screener_row", disabled=True, label_visibility="collapsed")
            st.caption("Selecciona todo el texto de arriba y cópialo (Ctrl+C o mantén pulsado en móvil) para compartir por mensaje o correo.")

        account_id_scr = get_current_account_id()
        with st.expander("📝 Abrir trade desde esta ficha", expanded=False):
            if not account_id_scr:
                st.info("Selecciona una cuenta en **Mi cuenta** (pestaña Dashboard) para poder registrar el trade aquí.")
            else:
                st.caption("Pre-rellenado con los datos del contrato seleccionado. Ajusta si quieres y registra.")
                try:
                    exp_date_row = datetime.strptime(str(row["Exp"])[:10], "%Y-%m-%d").date()
                except Exception:
                    exp_date_row = date.today() + timedelta(days=30)
                trade_date_scr = st.date_input("Fecha", value=date.today(), key="scr_trade_date").isoformat()
                ticker_scr = st.text_input("Ticker", value=str(row["Ticker"]), key="scr_ticker").strip().upper()
                qty_scr = st.number_input("Contratos", min_value=1, value=1, key="scr_qty")
                strike_scr = st.number_input("Strike", min_value=0.0, value=float(row["Strike"]), step=0.5, key="scr_strike")
                premium_scr = st.number_input("Prima por contrato", min_value=0.0, value=float(row["Prima"]), step=0.01, key="scr_premium")
                exp_scr = st.date_input("Expiración", value=exp_date_row, key="scr_exp")
                comment_scr = st.text_area("Comentario", value="", key="scr_comment")
                if estrategia == "Cash Secured Put (CSP)":
                    if st.button("Registrar CSP desde ficha", key="scr_btn_csp"):
                        if ticker_scr and strike_scr > 0:
                            register_csp_opening(account_id_scr, user_id, ticker_scr, qty_scr, strike_scr, premium_scr, exp_scr.isoformat(), trade_date_scr, comment_scr or None)
                            st.success("CSP registrado.")
                            st.rerun()
                        else:
                            st.error("Ticker y strike obligatorios.")
                else:
                    shares_needed_scr = qty_scr * 100
                    shares_now_scr = get_stock_quantity(account_id_scr, ticker_scr) if ticker_scr else 0
                    if ticker_scr and shares_now_scr < shares_needed_scr:
                        st.warning(f"Covered Call requiere tener las acciones. Tienes **{shares_now_scr}** de {ticker_scr}; necesitas **{shares_needed_scr}**.")
                    if st.button("Registrar CC desde ficha", key="scr_btn_cc"):
                        if not ticker_scr:
                            st.error("Indica el ticker.")
                        elif strike_scr <= 0:
                            st.error("Strike mayor que 0.")
                        elif get_stock_quantity(account_id_scr, ticker_scr) < qty_scr * 100:
                            st.error("No tienes suficientes acciones. Registra antes compra directa o asignación.")
                        else:
                            register_cc_opening(account_id_scr, user_id, ticker_scr, qty_scr, strike_scr, premium_scr, exp_scr.isoformat(), trade_date_scr, comment_scr or None)
                            st.success("CC registrado.")
                            st.rerun()


def run():
    st.markdown(PROFESSIONAL_CSS, unsafe_allow_html=True)
    # Override visual para la línea de vencimientos (tooltips en vez de círculo fijo)
    st.markdown(
        """
        <style>
        .timeline-60-marker .bubble { display: none; }
        .timeline-hover-label { display: none; }
        .timeline-60-seg { cursor: pointer; position: relative; }
        .timeline-60-seg::after {
            content: attr(data-tooltip);
            position: absolute;
            left: 50%;
            top: -6px;
            transform: translate(-50%, -120%);
            background: #21262d;
            border: 1px solid #e3b341;
            border-radius: 8px;
            padding: 4px 8px;
            font-size: 0.75rem;
            color: #e6edf3;
            white-space: nowrap;
            max-width: 260px;
            overflow: hidden;
            text-overflow: ellipsis;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.15s ease, transform 0.15s ease;
            z-index: 20;
        }
        .timeline-60-seg:hover::after {
            opacity: 1;
            transform: translate(-50%, -150%);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    user_id = get_current_user_id()
    if not user_id:
        st.warning("Sesión no válida. Vuelve a iniciar sesión.")
        return

    # En web/móvil el sidebar puede no verse: vista por defecto Mi Cuenta para no dejar atrapado al usuario
    if "main_view_radio" not in st.session_state:
        st.session_state["main_view_radio"] = "📊 Mi Cuenta"

    with st.sidebar:
        st.header("🦅 Alpha Control")
        st.markdown(
            f'<div class="user-badge">👤 {html_module.escape(get_current_user_display_name() or get_current_user_email())}</div>',
            unsafe_allow_html=True,
        )
        st.caption(get_current_user_email())

        # Navegación: Screener o Mi Cuenta (sidebar mínimo para que local siga viendo el radio)
        main_view = st.radio("Ir a", ["🔎 Screener", "📊 Mi Cuenta"], key="main_view_radio", horizontal=True)
        show_screener_page = main_view == "🔎 Screener"

    # ---------- Contenido principal: cuenta, Roll-over, Añadir posición (web y móvil sin depender del sidebar) ----------
    account_id = None
    acc_data = {}
    token = ""
    if not show_screener_page:
        accounts = get_accounts_for_current_user()
        if not accounts:
            st.warning("Sin cuentas. Ve a la pestaña **Mi cuenta** (abajo) para crear una.")
        else:
            acc_names = [a["name"] for a in accounts]
            idx = 0
            if get_current_account_id():
                for i, a in enumerate(accounts):
                    if a["account_id"] == get_current_account_id():
                        idx = i
                        break
            sel_acc_name = st.selectbox("Cuenta activa", acc_names, index=idx, key="sel_acc")
            acc_data = next(a for a in accounts if a["name"] == sel_acc_name)
            set_current_account_id(acc_data["account_id"])
            account_id = acc_data["account_id"]
            token = (acc_data.get("access_token") or "").strip() if account_id else ""

            if account_id and token:
                provider = TradierProvider(token, acc_data.get("environment") or "sandbox")
                status = provider.validate_connection()
                if status.online:
                    st.success("🟢 Online")
                    db.set_account_connection_status(account_id, "online")
                else:
                    st.error(f"🔴 Offline — {status.message}")
                    db.set_account_connection_status(account_id, "offline")
            elif account_id:
                st.caption("Token no configurado. Pestaña **Mi cuenta** (abajo) → Token Tradier")

        if not show_screener_page:
            with st.expander("🔄 Roll-over", expanded=False):
                if not account_id:
                    st.caption("Selecciona una cuenta para hacer roll-over.")
                else:
                    roll_type = st.radio("Tipo de posición a hacer roll", ["CSP", "CC"], horizontal=True, key="roll_type")
                    trades_open_roll = get_trades_by_account(account_id, status="OPEN")
                    roll_list = [t for t in trades_open_roll if (t.get("strategy_type") or "").upper() == roll_type]
                    if not roll_list:
                        st.info(f"No hay posiciones abiertas de tipo **{roll_type}** para hacer roll.")
                    else:
                        roll_options = [f"{t['ticker']} | Strike ${fmt2(t.get('strike'))} | Exp {str(t.get('expiration_date') or '')[:10]} | Prima ${fmt2(t.get('price'))}" for t in roll_list]
                        roll_idx = st.selectbox("Seleccionar posición a hacer roll", range(len(roll_list)), format_func=lambda i: roll_options[i], key="roll_sel")
                        tr = roll_list[roll_idx]
                        st.caption(f"**{tr['ticker']}** · {tr['quantity']} contrato(s) · Strike ${fmt2(tr.get('strike'))} · Exp {str(tr.get('expiration_date') or '')[:10]}")
                        new_strike = st.number_input("Nuevo strike", value=float(tr.get("strike") or 0), min_value=0.0, step=0.5, format="%.2f", key="roll_new_strike")
                        new_exp_d = st.date_input("Nueva expiración", value=date.today() + timedelta(days=30), key="roll_new_exp")
                        new_premium = st.number_input("Nueva prima por contrato", value=float(tr.get("price") or 0), min_value=0.0, step=0.01, format="%.2f", key="roll_new_premium")
                        roll_comment = st.text_area("Comentario (bitácora)", value=f"Roll desde Strike {fmt2(tr.get('strike'))}", key="roll_comment")
                        if st.button("Ejecutar roll-over"):
                            close_trade(tr["trade_id"], account_id, date.today().isoformat())
                            if roll_type == "CSP":
                                register_csp_opening(account_id, user_id, tr["ticker"], tr["quantity"], new_strike, new_premium, new_exp_d.isoformat(), date.today().isoformat(), roll_comment or None, parent_trade_id=tr["trade_id"])
                            else:
                                register_cc_opening(account_id, user_id, tr["ticker"], tr["quantity"], new_strike, new_premium, new_exp_d.isoformat(), date.today().isoformat(), roll_comment or None, parent_trade_id=tr["trade_id"])
                            for k in ["roll_sel", "roll_new_strike", "roll_new_exp", "roll_new_premium", "roll_comment"]:
                                if k in st.session_state:
                                    del st.session_state[k]
                            st.success("Roll-over ejecutado: posición anterior cerrada y nueva registrada. Bitácora actualizada.")
                            st.rerun()

            with st.expander("➕ Añadir posición", expanded=False):
                if not account_id:
                    st.info("Crea una cuenta en **Mi cuenta** para registrar movimientos.")
                else:
                    st.caption("**CSP** = vender put (colateral; no requiere acciones). **CC** = poseer acciones y vender call (registra antes compra directa o asignación).")
                    reg_type = st.radio("Tipo", ["CSP", "CC", "Compra directa", "Asignación CSP", "Asignación CC", "Dividendo", "Ajuste"], horizontal=False, key="add_reg_type")
                    trade_date = st.date_input("Fecha", value=date.today(), key="add_trade_date").isoformat()
                    if reg_type == "CSP":
                        ticker = st.text_input("Ticker", value="", key="add_csp_ticker", placeholder="Ej. AAPL", help="CSP: vendes un put; colateral = strike × 100 × contratos.").strip().upper()
                        qty = st.number_input("Contratos", min_value=1, value=1, key="add_csp_qty")
                        strike = st.number_input("Strike", min_value=0.0, value=0.0, step=0.5, key="add_csp_strike", help="Obligatorio: precio de ejercicio del put.")
                        premium = st.number_input("Prima por contrato", min_value=0.0, value=0.0, step=0.01, key="add_csp_premium")
                        exp_date = st.date_input("Expiración", value=date.today() + timedelta(days=30), key="add_csp_exp")
                        comment = st.text_area("Comentario", value="", key="add_csp_comment")
                        if st.button("Registrar CSP"):
                            if ticker and strike and strike > 0:
                                register_csp_opening(account_id, user_id, ticker, qty, strike, premium, exp_date.isoformat(), trade_date, comment or None)
                                for k in ["add_trade_date", "add_csp_ticker", "add_csp_qty", "add_csp_strike", "add_csp_premium", "add_csp_exp", "add_csp_comment"]:
                                    if k in st.session_state:
                                        del st.session_state[k]
                                st.success("CSP registrado. Formulario borrado.")
                                st.rerun()
                            else:
                                st.error("Ticker y strike obligatorios.")
                    elif reg_type == "CC":
                        ticker = st.text_input("Ticker", value="", key="add_cc_ticker", placeholder="Ej. AAPL", help="Covered Call: necesitas al menos contratos × 100 acciones.").strip().upper()
                        qty = st.number_input("Contratos", min_value=1, value=1, key="add_cc_qty")
                        shares_needed = qty * 100
                        if ticker:
                            shares_now = get_stock_quantity(account_id, ticker)
                            if shares_now < shares_needed:
                                st.warning(f"**Covered Call requiere tener las acciones.** Tienes **{shares_now}** de {ticker}; necesitas **{shares_needed}**. Registra antes compra directa o asignación.")
                            else:
                                st.caption(f"Acciones de {ticker}: **{shares_now}** (necesitas {shares_needed}).")
                        strike = st.number_input("Strike", min_value=0.0, value=0.0, step=0.5, key="add_cc_strike", help="Obligatorio: precio de ejercicio de la call.")
                        premium = st.number_input("Prima por contrato", min_value=0.0, value=0.0, step=0.01, key="add_cc_premium")
                        exp_date = st.date_input("Expiración", value=date.today() + timedelta(days=30), key="add_cc_exp")
                        comment = st.text_area("Comentario", value="", key="add_cc_comment")
                        if st.button("Registrar CC"):
                            if not ticker:
                                st.error("Indica el ticker.")
                            elif not strike or strike <= 0:
                                st.error("Indica el strike (mayor que 0).")
                            elif get_stock_quantity(account_id, ticker) < qty * 100:
                                st.error(f"No tienes suficientes acciones. Necesitas **{qty * 100}** de **{ticker}**. Registra antes compra directa o asignación.")
                            else:
                                register_cc_opening(account_id, user_id, ticker, qty, strike, premium, exp_date.isoformat(), trade_date, comment or None)
                                for k in ["add_trade_date", "add_cc_ticker", "add_cc_qty", "add_cc_strike", "add_cc_premium", "add_cc_exp", "add_cc_comment"]:
                                    if k in st.session_state:
                                        del st.session_state[k]
                                st.success("CC registrado. Formulario borrado.")
                                st.rerun()
                    elif reg_type == "Compra directa":
                        ticker = st.text_input("Ticker", value="", key="add_buy_ticker", placeholder="Ej. AAPL", help="Obligatorio.").strip().upper()
                        qty = st.number_input("Acciones", min_value=1, value=1, key="add_buy_qty", help="Obligatorio: al menos 1.")
                        price = st.number_input("Precio por acción", min_value=0.0, value=0.0, step=0.01, key="add_buy_price", help="Obligatorio: debe ser mayor que 0.")
                        comment = st.text_area("Comentario", value="", key="add_buy_comment")
                        if st.button("Registrar compra"):
                            if not ticker:
                                st.error("Indica el **ticker** (ej. AAPL).")
                            elif not price or price <= 0:
                                st.error("Indica el **precio por acción** (debe ser mayor que 0).")
                            else:
                                register_direct_purchase(account_id, user_id, ticker, qty, price, trade_date, comment or None)
                                for k in ["add_trade_date", "add_buy_ticker", "add_buy_qty", "add_buy_price", "add_buy_comment"]:
                                    if k in st.session_state:
                                        del st.session_state[k]
                                st.success("Compra registrada. Formulario borrado.")
                                st.rerun()
                    elif reg_type == "Asignación CSP":
                        st.caption("**Asignación de put**: te ejercieron el put (CSP) y recibiste las acciones. Elige el CSP que fue asignado.")
                        trades_open_add = get_trades_by_account(account_id, status="OPEN") or []
                        csp_open = [t for t in trades_open_add if (t.get("strategy_type") or "").upper() == "CSP"]
                        if not csp_open:
                            st.info("No tienes CSP abiertos. Solo puedes registrar asignación de un put que tenías vendido (CSP) y que expiró en el dinero.")
                        else:
                            opts = [(t["trade_id"], f"{t['ticker']} | Strike ${t.get('strike') or 0:,.2f} | Exp {t.get('expiration_date') or '—'} | {t.get('quantity') or 0} contrato(s)") for t in csp_open]
                            idx_sel = st.selectbox("CSP asignado", range(len(opts)), format_func=lambda i: opts[i][1], key="add_assign_csp_sel")
                            parent_trade_id = opts[idx_sel][0]
                            tr = next(t for t in csp_open if t["trade_id"] == parent_trade_id)
                            assign_price = st.number_input("Precio de asignación (por acción)", min_value=0.0, value=float(tr.get("strike") or 0), step=0.01, key="add_assign_price", help="Suele ser el strike del put.")
                            comment_assign = st.text_area("Comentario", value="", key="add_assign_comment")
                            if st.button("Registrar asignación CSP"):
                                register_assignment(account_id, user_id, parent_trade_id, tr["ticker"], (tr.get("quantity") or 0) * 100, assign_price, trade_date, comment_assign or None)
                                for k in ["add_assign_csp_sel", "add_assign_price", "add_assign_comment"]:
                                    if k in st.session_state:
                                        del st.session_state[k]
                                st.success("Asignación registrada: CSP cerrado y acciones recibidas en la cuenta.")
                                st.rerun()
                    elif reg_type == "Asignación CC":
                        st.caption("**Asignación de Covered Call**: te asignaron el call y te compraron las acciones al strike. Registra el cierre del CC.")
                        trades_open_cc = get_trades_by_account(account_id, status="OPEN") or []
                        cc_open = [t for t in trades_open_cc if (t.get("strategy_type") or "").upper() == "CC"]
                        if not cc_open:
                            st.info("No tienes Covered Calls abiertos. Solo puedes registrar asignación cuando te asignan un call que habías vendido.")
                        else:
                            opts_cc = [(t["trade_id"], f"{t['ticker']} | Strike ${t.get('strike') or 0:,.2f} | Exp {t.get('expiration_date') or '—'} | {t.get('quantity') or 0} contrato(s)") for t in cc_open]
                            idx_cc = st.selectbox("CC asignado", range(len(opts_cc)), format_func=lambda i: opts_cc[i][1], key="add_exercise_cc_sel")
                            cc_trade_id = opts_cc[idx_cc][0]
                            comment_cc = st.text_area("Comentario", value="", key="add_exercise_cc_comment")
                            if st.button("Registrar asignación CC (cerrar posición)"):
                                close_trade(cc_trade_id, account_id, trade_date)
                                for k in ["add_exercise_cc_sel", "add_exercise_cc_comment"]:
                                    if k in st.session_state:
                                        del st.session_state[k]
                                st.success("Asignación de CC registrada: posición cerrada. Las acciones fueron vendidas al strike.")
                                st.rerun()
                    elif reg_type == "Dividendo":
                        tickers_owned = [s["ticker"] for s in get_position_summary(account_id)] if account_id else []
                        if not tickers_owned:
                            st.caption("Solo puedes registrar dividendos de tickers que posees. No tienes posiciones; registra antes una compra directa o CSP/CC.")
                        else:
                            ticker_sel = st.selectbox("Ticker (solo posiciones que posees)", options=[""] + sorted(tickers_owned), key="add_div_ticker_sel", format_func=lambda x: x if x else "— Elige un ticker —")
                            ticker = (ticker_sel or "").strip().upper()
                            amount = st.number_input("Monto total", min_value=0.0, value=0.0, step=0.01, key="add_div_amount")
                            ex_date_w = st.date_input("Ex-date", value=date.today(), key="add_div_ex_date")
                            pay_date_w = st.date_input("Pay-date (opcional)", value=None, key="add_div_pay_date")
                            note = st.text_area("Nota", value="", key="add_div_note")
                            if st.button("Registrar dividendo"):
                                if not ticker:
                                    st.error("Elige un ticker de la lista (posiciones que posees).")
                                else:
                                    register_dividend(account_id, ticker, amount, ex_date_w.isoformat(), pay_date_w.isoformat() if pay_date_w else None, note or None)
                                    for k in ["add_div_ticker", "add_div_ticker_sel", "add_div_amount", "add_div_ex_date", "add_div_pay_date", "add_div_note"]:
                                        if k in st.session_state:
                                            del st.session_state[k]
                                    st.success("Dividendo registrado. Formulario borrado.")
                                    st.rerun()
                    elif reg_type == "Ajuste":
                        st.caption("**Ajuste**: para splits de acciones, corrección de cost basis u otros ajustes de posición en un ticker.")
                        ticker = st.text_input("Ticker", value="", key="add_adj_ticker", placeholder="Ej. AAPL").strip().upper()
                        adj_type = st.selectbox("Tipo", ["SPLIT", "COST_BASIS_CORRECTION", "OTHER"], key="add_adj_type")
                        old_val = st.number_input("Valor anterior", value=0.0, step=0.01, key="add_adj_old")
                        new_val = st.number_input("Valor nuevo", value=0.0, step=0.01, key="add_adj_new")
                        note = st.text_area("Nota", value="", key="add_adj_note")
                        if st.button("Registrar ajuste"):
                            if ticker:
                                register_adjustment(account_id, ticker, adj_type, old_val, new_val, note or None)
                                for k in ["add_adj_ticker", "add_adj_type", "add_adj_old", "add_adj_new", "add_adj_note"]:
                                    if k in st.session_state:
                                        del st.session_state[k]
                                st.success("Ajuste registrado. Formulario borrado.")
                                st.rerun()
                            else:
                                st.error("Indica el ticker.")

            if st.button("Cerrar sesión", type="primary", use_container_width=True):
                logout_user()
                st.rerun()

    account_id = get_current_account_id()
    accounts = get_accounts_for_current_user()
    acc_data = next((a for a in accounts if a["account_id"] == account_id), {}) if account_id else {}
    token = (acc_data.get("access_token") or "").strip() if account_id else ""

    # Navegación principal (visible en web, móvil y local)
    st.caption("Cambiar de vista:")
    nc1, nc2 = st.columns(2)
    with nc1:
        if st.button("🔎 Screener", key="nav_content_screener", use_container_width=True):
            st.session_state["main_view_radio"] = "🔎 Screener"
            st.rerun()
    with nc2:
        if st.button("📊 Mi Cuenta", key="nav_content_micuenta", use_container_width=True):
            st.session_state["main_view_radio"] = "📊 Mi Cuenta"
            st.rerun()
    st.markdown("---")

    # Screener es por usuario y se muestra como vista separada (no pestaña de cuenta)
    if show_screener_page:
        render_screener_page(user_id)
        return

    tab_dash, tab_tutorial, tab_report, tab_settings = st.tabs(
        ["📊 Dashboard", "📖 Tutorial", "📑 Reportes", "👤 Mi cuenta"]
    )

    with tab_tutorial:
        _render_tutorial_tab()

    with tab_dash:
        if not account_id:
            st.info("Crea o selecciona una cuenta en **Mi cuenta** para ver el dashboard.")
        else:
            trades_open = get_trades_by_account(account_id, status="OPEN")
            summaries = get_position_summary(account_id)
            cap_total = safe_float(acc_data.get("cap_total"))
            target_ann = safe_float(acc_data.get("target_ann"))
            target_usd = round2(cap_total * (target_ann / 100))
            colateral = 0.0
            for s in summaries:
                if s.get("strategy_type") == "CSP" and s.get("strike"):
                    colateral += safe_float(s["strike"]) * 100 * s.get("option_contracts", 0)
                elif s.get("stock_quantity", 0) > 0:
                    colateral += safe_float(s.get("stock_cost_total") or 0)
            colateral = round2(colateral)
            cash_libre = round2(max(0, cap_total - colateral))
            max_per_ticker_pct = safe_float(acc_data.get("max_per_ticker"))

            st.markdown(f'<div style="margin-bottom:1rem;"><span style="font-size:1.5rem;font-weight:600;color:#58a6ff;">AlphaWheel Pro</span> <span style="color:#8b949e;font-size:0.9rem;">— {acc_data.get("name", "Cuenta")}</span></div>', unsafe_allow_html=True)
            resumen_perf_cards = (
                f'<div class="perf-card"><div class="label">CAPITAL</div><div class="value">${fmt2(cap_total)}</div></div>'
                f'<div class="perf-card"><div class="label">META ANUAL</div><div class="value">{fmt2(target_ann)}%</div></div>'
                f'<div class="perf-card"><div class="label">MÁX. POR TICKER</div><div class="value">{fmt2(max_per_ticker_pct)}%</div></div>'
            )
            if trades_open:
                total_primas_res = round2(sum((s.get("premiums_received") or 0) for s in summaries))
                util_pct = (colateral / cap_total * 100) if cap_total else 0.0
                resumen_perf_cards += (
                    f'<div class="perf-card"><div class="label">PREMIUM</div><div class="value">${fmt2(total_primas_res)}</div></div>'
                    f'<div class="perf-card"><div class="label">COLLATERAL</div><div class="value">${fmt2(colateral)}</div></div>'
                    f'<div class="perf-card"><div class="label">UTILIZATION</div><div class="value">{fmt2(util_pct)}%</div></div>'
                    f'<div class="perf-card"><div class="label">POSITIONS</div><div class="value">{len(summaries)}</div></div>'
                )
            st.markdown(
                f'<div class="dashboard-card resumen-cuenta-card">'
                f'<h3>Resumen de cuenta</h3>'
                f'<div class="summary-strip">Total invertido <strong>${fmt2(colateral)}</strong> · Disponible <strong>${fmt2(cash_libre)}</strong> · Total <strong>${fmt2(cap_total)}</strong></div>'
                f'<div class="perf-cards">{resumen_perf_cards}</div></div>',
                unsafe_allow_html=True,
            )

            if not trades_open:
                st.info("No hay posiciones abiertas. Usa el sidebar para registrar CSP, CC o compra directa.")
            else:
                unique_tickers = list({t["ticker"] for t in trades_open})
                mkt_prices = {}
                if token:
                    provider = TradierProvider(token, acc_data.get("environment") or "sandbox")
                    for t in unique_tickers:
                        q = provider.get_quote(t)
                        mkt_prices[t] = q if isinstance(q, (int, float)) else 0.0
                else:
                    mkt_prices = {t: 0.0 for t in unique_tickers}

                # Valor a precios actuales vs invertido (realidad del dinero)
                valor_actual = cash_libre
                for s in summaries:
                    ticker_s = s["ticker"]
                    mkt_s = mkt_prices.get(ticker_s, 0.0)
                    stock_q = s.get("stock_quantity") or 0
                    opt_q = s.get("option_contracts") or 0
                    strk = s.get("strike") or 0
                    is_put_s = (s.get("strategy_type") or "").upper() in ("CSP", "PUT")
                    valor_actual += stock_q * mkt_s
                    if opt_q and strk:
                        if is_put_s:
                            collat_s = strk * 100 * opt_q
                            intrinsic_put = max(0.0, strk - mkt_s) * 100 * opt_q
                            valor_actual += collat_s - intrinsic_put
                        else:
                            intrinsic_call = max(0.0, mkt_s - strk) * 100 * opt_q
                            valor_actual -= intrinsic_call
                valor_actual = round2(valor_actual)
                pnl_real = round2(valor_actual - cap_total)
                pnl_pct = (100.0 * (valor_actual - cap_total) / cap_total) if cap_total else 0.0
                pnl_pct = round2(pnl_pct)
                st.markdown(
                    f'<div class="dashboard-card" style="border-left: 4px solid #58a6ff;">'
                    f'<h3 style="margin-top:0;">Valor actual vs invertido</h3>'
                    f'<div class="summary-strip">'
                    f'Valor a precios actuales <strong>${fmt2(valor_actual)}</strong> · '
                    f'Capital cuenta (invertido) <strong>${fmt2(cap_total)}</strong> · '
                    f'P&L no realizado <strong style="color:{"#3fb950" if pnl_real >= 0 else "#f85149"}">${fmt2(pnl_real)} ({fmt2(pnl_pct)}%)</strong>'
                    f'</div>'
                    f'<div class="timeline-section-sub">Efectivo disponible + valor de posiciones a precio de mercado (acciones y opciones).</div></div>',
                    unsafe_allow_html=True,
                )

                total_primas = round2(sum((s.get("premiums_received") or 0) for s in summaries))
                dte_list = [calculate_dte(s.get("expiration_date")) for s in summaries]
                avg_dte = sum(dte_list) / len(dte_list) if dte_list else 0
                total_roc_pct = (total_primas / colateral * 100) if colateral else 0.0
                ann_ret_approx = calculate_annualized_return(total_roc_pct, int(avg_dte)) if avg_dte else 0.0
                total_return_pct = (total_primas / colateral * 100) if colateral else 0.0
                utilization_pct = (colateral / cap_total * 100) if cap_total else 0.0
                on_track = ann_ret_approx >= target_ann if target_ann else False

                rows = []
                for s in summaries:
                    ticker = s["ticker"]
                    mkt = mkt_prices.get(ticker, 0.0)
                    strike = s.get("strike")
                    prems = s.get("premiums_received", 0) or 0
                    contracts = s.get("option_contracts", 0) or 0
                    dte = calculate_dte(s.get("expiration_date"))
                    is_put = (s.get("strategy_type") or "").upper() in ("CSP", "PUT")
                    be = calculate_breakeven(strike or 0, prems, contracts, is_put) if strike else 0.0
                    zone = delta_approx_itm_otm(strike or 0, mkt, is_put) if strike else "—"
                    collat = (strike or 0) * 100 * contracts if is_put else (s.get("stock_cost_total") or 0)
                    alloc_pct = (collat / cap_total * 100) if cap_total else 0.0
                    open_date = s.get("trade_date") or ""
                    exp_date = s.get("expiration_date") or ""
                    campaign_days = s.get("campaign_days")
                    if campaign_days is not None and campaign_days >= 0:
                        dias_posicion = int(campaign_days)
                    else:
                        try:
                            d0 = datetime.strptime(str(open_date)[:10], "%Y-%m-%d").date()
                            d1 = datetime.strptime(str(exp_date)[:10], "%Y-%m-%d").date()
                            dias_posicion = max(0, (d1 - d0).days)
                        except (ValueError, TypeError):
                            dias_posicion = 0
                    roc = calculate_return_on_capital(prems, collat) if collat else 0.0
                    dias_num = dias_posicion if isinstance(dias_posicion, int) and dias_posicion > 0 else dte
                    ann_ret = calculate_annualized_return(roc, dias_num) if dias_num else 0.0
                    stock_qty = s.get("stock_quantity") or 0
                    net_cost_total = s.get("net_cost_basis_total") or 0
                    cost_per_share = (net_cost_total / max(1, stock_qty)) if stock_qty else 0
                    if stock_qty:
                        diagnostico = "Riesgo" if zone == "ITM" else ("Ganando" if (mkt or 0) >= cost_per_share else "Perdiendo")
                    else:
                        diagnostico = "Riesgo" if zone == "ITM" else "OK"
                    pop_label = "N/A" if zone == "—" or not strike else f"~{min(99, max(1, round2(50 + abs((mkt or 0) - strike) / strike * 100 * 0.5)))}%"
                    estrategia_raw = s.get("strategy_type") or "—"
                    is_cc = (estrategia_raw or "").upper() == "CC"
                    if stock_qty and contracts and is_cc:
                        estrategia_label = "Propias + CC"
                    elif stock_qty and contracts and (estrategia_raw or "").upper() in ("CSP", "PUT"):
                        estrategia_label = "Propias + CSP"
                    elif estrategia_raw == "PROPIAS":
                        estrategia_label = "Propias"
                    else:
                        estrategia_label = estrategia_raw
                    acciones_libres = get_stock_quantity(account_id, ticker)
                    rows.append({
                        "Activo": ticker,
                        "Estrategia": estrategia_label,
                        "Contratos": contracts,
                        "Acciones libres": acciones_libres,
                        "Fecha inicio": str(open_date)[:10] if open_date else "—",
                        "Fecha exp.": str(exp_date)[:10] if exp_date else "—",
                        "Días posición": dias_posicion,
                        "Precio MKT": round2(mkt),
                        "Strike": round2(strike) if strike else "—",
                        "Prima recibida": round2(prems),
                        "Breakeven": round2(be),
                        "Diagnostico": diagnostico,
                        "Retorno": round2(roc),
                        "Anualizado": round2(ann_ret),
                        "POP": pop_label,
                        "SYMBOL": ticker,
                        "QTY": contracts,
                        "NET PREM": round2(prems),
                        "COLLAT": round2(collat),
                        "ALLOC %": round2(alloc_pct),
                        "BE": round2(be),
                        "MKT": round2(mkt),
                        "Estrategia_raw": estrategia_raw,
                        "Zona": zone,
                        "Exp_Date": exp_date,
                        "Open_Date": open_date,
                        "_DTE": dte,
                        "_collat": collat,
                        "_prems": prems,
                    })
                df_dash = pd.DataFrame(rows)
                df_dash["_sort_diag"] = df_dash["Diagnostico"].apply(lambda x: (0 if x == "Riesgo" else (1 if x == "Perdiendo" else 2)))
                df_dash = df_dash.sort_values("_sort_diag").drop(columns=["_sort_diag"])

                ticker_collat = df_dash.groupby("Activo")["COLLAT"].sum()
                n_symbols = len(ticker_collat.index)
                shared_chart_height = max(300, 40 * max(1, n_symbols))

                # --- Position Performance (estilo captura) ---
                prog_meta = max(0.0, min(1.0, total_primas / target_usd)) if target_usd > 0 else 0.0
                prog_meta_pct = min(100, max(0, prog_meta * 100))
                perf_class = "" if on_track else " behind"
                badge_class = "" if on_track else " behind"
                st.markdown(
                    f'<div class="position-performance{perf_class}">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.5rem;">'
                    f'<h3>Rendimiento de posiciones</h3><span class="on-track-badge{badge_class}">{"AL DÍA" if on_track else "ATRASADO"}</span></div>'
                    f'<div class="total-return-label">Progreso hacia la meta</div>'
                    f'<div style="font-size:1.25rem;font-weight:700;color:#58a6ff;margin-bottom:0.35rem;">{fmt2(prog_meta_pct)}%</div>'
                    f'<div class="timeline-bar-wrap" title="Prima cobrada ${fmt2(total_primas)} de ${fmt2(target_usd)} meta anual"><div class="timeline-bar-fill" style="width: {prog_meta_pct:.1f}%"></div></div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                # --- Capital por ticker y Por símbolo: una al lado de la otra debajo de Rendimiento ---
                col_cap, col_sym = st.columns(2)
                with col_cap:
                    pie_labels = list(ticker_collat.index)
                    pie_values = [float(ticker_collat[t]) for t in pie_labels]
                    pie_colors = ["#58a6ff", "#79c0ff", "#3fb950", "#56d364", "#d29922", "#e3b341"][:len(pie_labels)]
                    w_avail_pct = (cash_libre / cap_total * 100) if cap_total else 0
                    pull = [0.04] * len(pie_labels)
                    if pie_labels and sum(pie_values) > 0:
                        fig_pie = go.Figure(
                            data=[
                                go.Pie(
                                    labels=pie_labels,
                                    values=pie_values,
                                    hole=0.5,
                                    marker_colors=pie_colors,
                                    pull=pull,
                                    textinfo="label+percent",
                                    textposition="outside",
                                    outsidetextfont=dict(color="#e6edf3", size=12),
                                )
                            ]
                        )
                        fig_pie.update_layout(
                            template="plotly_dark",
                            height=shared_chart_height,
                            margin=dict(l=10, r=10, t=30, b=50),
                            showlegend=True,
                            legend=dict(orientation="h", yanchor="top", y=-0.02),
                            paper_bgcolor="rgba(22,27,34,0.98)",
                            plot_bgcolor="rgba(22,27,34,0.98)",
                            font=dict(color="#e6edf3"),
                        )
                        fig_pie.update_traces(textfont_color="#e6edf3")
                        center_text = f"Disponible<br>${fmt2(cash_libre)}<br>({fmt2(w_avail_pct)}%)"
                        fig_pie.add_annotation(
                            text=center_text,
                            x=0.5,
                            y=0.5,
                            font=dict(size=13, color="#8b949e"),
                            showarrow=False,
                        )
                    else:
                        fig_pie = go.Figure()
                        fig_pie.add_annotation(
                            text=f"Sin posiciones.<br>Disponible: ${fmt2(cash_libre)} (100%)",
                            x=0.5,
                            y=0.5,
                            font=dict(size=14, color="#8b949e"),
                            showarrow=False,
                        )
                        fig_pie.update_layout(
                            template="plotly_dark",
                            height=shared_chart_height,
                            paper_bgcolor="rgba(22,27,34,0.98)",
                            plot_bgcolor="rgba(22,27,34,0.98)",
                        )
                    st.markdown('<div class="dashboard-card"><h3>Capital por ticker y disponible</h3>', unsafe_allow_html=True)
                    st.plotly_chart(fig_pie, use_container_width=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                with col_sym:
                    allocs_by_ticker = df_dash.groupby("Activo")["ALLOC %"].sum()
                    symbols = allocs_by_ticker.index.tolist()
                    allocs = [float(allocs_by_ticker[s]) for s in symbols] if symbols else []
                    bar_colors = ["#f85149" if a > max_per_ticker_pct else "#58a6ff" for a in allocs]
                    fig_bars = go.Figure(go.Bar(x=allocs, y=symbols, orientation="h", marker_color=bar_colors, text=[f"{fmt2(a)}%" for a in allocs], textposition="outside", textfont=dict(color="#e6edf3")))
                    fig_bars.update_layout(
                        template="plotly_dark",
                        height=shared_chart_height,
                        margin=dict(l=50, r=50, t=30, b=20),
                        xaxis_title="% del capital (rojo = supera máx. por ticker)",
                        showlegend=False,
                        paper_bgcolor="rgba(22,27,34,0.98)",
                        plot_bgcolor="rgba(22,27,34,0.98)",
                        font=dict(color="#e6edf3"),
                        xaxis=dict(gridcolor="rgba(48,54,61,0.5)", zerolinecolor="rgba(48,54,61,0.5)"),
                        yaxis=dict(autorange="reversed", gridcolor="rgba(48,54,61,0.5)"),
                    )
                    if max_per_ticker_pct and max_per_ticker_pct > 0:
                        fig_bars.add_vline(x=float(max_per_ticker_pct), line_dash="dash", line_color="#e3b341", line_width=2, annotation_text=f" Límite {fmt2(max_per_ticker_pct)}% ", annotation_position="top")
                    st.markdown('<div class="dashboard-card"><h3>Por símbolo (% del capital total)</h3>', unsafe_allow_html=True)
                    st.plotly_chart(fig_bars, use_container_width=True)
                    st.markdown(f'<div class="card-sub">Máx. por ticker: {fmt2(max_per_ticker_pct)}%. En rojo: tickers que superan el límite.</div></div>', unsafe_allow_html=True)

                # Alertas expiración cercana (justo encima de la línea de vencimientos)
                for s in summaries:
                    dte = calculate_dte(s.get("expiration_date"))
                    if dte > 0 and dte < config.ALERT_DTE_THRESHOLD:
                        st.markdown(f'<div class="alert-danger">⚠️ Expiración cercana: {s["ticker"]} — {dte} DTE</div>', unsafe_allow_html=True)

                # --- Línea de vencimientos: solo opciones (CSP/CC), no Propias; círculo en 0-3 DTE ---
                if "_DTE" in df_dash.columns and "QTY" in df_dash.columns:
                    df_opts = df_dash[df_dash["QTY"].fillna(0) > 0]
                    dte_col = df_opts["_DTE"] if len(df_opts) else pd.Series(dtype=int)
                else:
                    df_opts = pd.DataFrame()
                    dte_col = pd.Series(dtype=int)
                if "_DTE" in df_dash.columns:
                    b0 = int((dte_col <= 3).sum())
                    b1 = int(((dte_col > 3) & (dte_col <= 7)).sum())
                    b2 = int(((dte_col > 7) & (dte_col <= 14)).sum())
                    b3 = int((dte_col > 14).sum())
                    if len(df_opts) and "Activo" in df_opts.columns:
                        tickers_b0 = df_opts.loc[dte_col <= 3, "Activo"].unique().tolist()
                        tickers_b1 = df_opts.loc[(dte_col > 3) & (dte_col <= 7), "Activo"].unique().tolist()
                        tickers_b2 = df_opts.loc[(dte_col > 7) & (dte_col <= 14), "Activo"].unique().tolist()
                        tickers_b3 = df_opts.loc[dte_col > 14, "Activo"].unique().tolist()
                    else:
                        tickers_b0 = tickers_b1 = tickers_b2 = tickers_b3 = []
                else:
                    b0 = b1 = b2 = b3 = 0
                    tickers_b0 = tickers_b1 = tickers_b2 = tickers_b3 = []
                t0 = ", ".join(tickers_b0) if tickers_b0 else "—"
                t1 = ", ".join(tickers_b1) if tickers_b1 else "—"
                t2 = ", ".join(tickers_b2) if tickers_b2 else "—"
                t3 = ", ".join(tickers_b3) if tickers_b3 else "—"
                pos0, pos1, pos2, pos3 = 2.5, 8.35, 17.5, 61.7
                t0_esc = html_module.escape(t0)
                t1_esc = html_module.escape(t1)
                t2_esc = html_module.escape(t2)
                t3_esc = html_module.escape(t3)
                tip0_esc = html_module.escape(f"0-3 DTE: {b0} pos · {t0}")
                tip1_esc = html_module.escape(f"4-7 DTE: {b1} pos · {t1}")
                tip2_esc = html_module.escape(f"8-14 DTE: {b2} pos · {t2}")
                tip3_esc = html_module.escape(f"15+ DTE: {b3} pos · {t3}")
                st.markdown(
                    f'<div class="expiration-timeline" id="exp-timeline">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;">'
                    f'<h3>Línea de vencimientos</h3><span class="next-days">Arrastra el círculo o pasa el ratón por cada periodo para ver posiciones y tickers a vencer</span></div>'
                    f'<div class="timeline-60-labels"><span>TODAY</span><span>15D</span><span>30D</span><span>45D</span><span>60D</span></div>'
                    f'<div class="timeline-60-bar">'
                    f'<div class="timeline-60-seg s0" data-count="{b0}" data-tickers="{t0_esc}" data-left="{pos0}" data-tooltip="{tip0_esc}" title="0-3 DTE: {b0} pos. Tickers: {t0}"></div>'
                    f'<div class="timeline-60-seg s1" data-count="{b1}" data-tickers="{t1_esc}" data-left="{pos1}" data-tooltip="{tip1_esc}" title="4-7 DTE: {b1} pos. Tickers: {t1}"></div>'
                    f'<div class="timeline-60-seg s2" data-count="{b2}" data-tickers="{t2_esc}" data-left="{pos2}" data-tooltip="{tip2_esc}" title="8-14 DTE: {b2} pos. Tickers: {t2}"></div>'
                    f'<div class="timeline-60-seg s3" data-count="{b3}" data-tickers="{t3_esc}" data-left="{pos3}" data-tooltip="{tip3_esc}" title="15+ DTE: {b3} pos. Tickers: {t3}"></div></div>'
                    f'<div class="timeline-legend">'
                    f'<span><span class="dot red"></span> 0-3d</span><span><span class="dot orange"></span> 4-7d</span>'
                    f'<span><span class="dot yellow"></span> 8-14d</span><span><span class="dot green"></span> 15+d</span></div></div>',
                    unsafe_allow_html=True,
                )

                # --- Posiciones abiertas ---
                st.markdown('<div class="dashboard-card"><h3>Posiciones abiertas</h3>', unsafe_allow_html=True)
                table_cols = ["Activo", "Estrategia", "Contratos", "Acciones libres", "Fecha inicio", "Fecha exp.", "Días posición", "Precio MKT", "Strike", "Prima recibida", "Breakeven", "Diagnostico", "Retorno", "Anualizado", "POP"]
                df_show = df_dash[[c for c in table_cols if c in df_dash.columns]].copy()
                # Asegurar columnas numéricas para PyArrow (evitar ArrowInvalid: no convertir '-' a int64)
                if "Días posición" in df_show.columns:
                    df_show["Días posición"] = pd.to_numeric(df_show["Días posición"], errors="coerce").fillna(0).astype(int)
                if "Contratos" in df_show.columns:
                    df_show["Contratos"] = pd.to_numeric(df_show["Contratos"], errors="coerce").fillna(0).astype(int)
                if "Acciones libres" in df_show.columns:
                    df_show["Acciones libres"] = pd.to_numeric(df_show["Acciones libres"], errors="coerce").fillna(0).astype(int)
                for col in ["Precio MKT", "Strike", "Prima recibida", "Breakeven"]:
                    if col in df_show.columns:
                        df_show[col] = df_show[col].apply(lambda x: fmt2(x) if x is not None and not isinstance(x, str) else ("—" if x == "—" or x is None else str(x)))
                for col in ["Retorno", "Anualizado"]:
                    if col in df_show.columns:
                        df_show[col] = df_show[col].apply(lambda x: f"{fmt2(x)}%" if x is not None and not isinstance(x, str) else "—")
                def highlight_risk(row):
                    n = len(row)
                    if row["Diagnostico"] == "Riesgo":
                        return ["background-color: #2d1a1a; color: #ff7b72"] * n
                    if row["Diagnostico"] == "Perdiendo":
                        return ["background-color: #2d251a; color: #d29922"] * n
                    return [""] * n
                styled = df_show.style.apply(highlight_risk, axis=1)
                st.dataframe(
                    styled,
                    width="stretch",
                    hide_index=True,
                    on_select="ignore",
                )
                st.markdown('</div>', unsafe_allow_html=True)  # dashboard-card Open Positions

                # Selección solo por desplegable + botón (sin columna de cuadro en la tabla)
                row_options = list(range(len(df_dash)))
                prev_sel = st.session_state.get("dashboard_selected_row_index")
                if prev_sel is not None and (prev_sel < 0 or prev_sel >= len(df_dash)):
                    prev_sel = None

                def _row_label(i):
                    if i == -1:
                        return "— Elige una posición —"
                    r = df_dash.iloc[i]
                    return f"{r['Activo']} · {r.get('Estrategia', '')} · Strike ${fmt2(r.get('Strike'))}"

                col_sel, col_btn = st.columns([3, 1])
                with col_sel:
                    sel_opts = [-1] + row_options
                    default_ix = (row_options.index(prev_sel) + 1) if prev_sel is not None and prev_sel in row_options else 0
                    chosen_row = st.selectbox(
                        "Posición a analizar",
                        options=sel_opts,
                        format_func=_row_label,
                        index=min(default_ix, len(sel_opts) - 1),
                        key="dashboard_position_selector",
                    )
                with col_btn:
                    st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)
                    ver_detalle = st.button("Ver Gráfica de riesgo y editar", type="primary", key="dashboard_ver_detalle")

                if ver_detalle and chosen_row >= 0:
                    st.session_state["dashboard_selected_row_index"] = chosen_row
                    st.rerun()
                sel_idx = st.session_state.get("dashboard_selected_row_index")
                if sel_idx is None or sel_idx < 0 or sel_idx >= len(df_dash):
                    sel_idx = None
                if sel_idx is not None and 0 <= sel_idx < len(df_dash):
                    if st.button("← Cerrar detalle", key="dashboard_cerrar_detalle"):
                        st.session_state["dashboard_selected_row_index"] = None
                        st.rerun()
                    sel_data = df_dash.iloc[sel_idx]
                    ticker = sel_data["Activo"]
                    estrategia = str(sel_data.get("Estrategia") or "CSP")
                    trades_ticker = [t for t in trades_open if t["ticker"] == ticker]
                    all_trades_historial = sorted(get_trades_by_account(account_id, ticker=ticker), key=lambda x: (x.get("trade_date") or "", x.get("trade_id") or 0))
                    be = safe_float(sel_data.get("BE"))
                    strike = safe_float(sel_data.get("Strike"))
                    if (strike is None or strike == 0) and trades_ticker:
                        for t in trades_ticker:
                            if t.get("strike"):
                                strike = safe_float(t["strike"])
                                break
                    strike = strike or 0
                    mkt = safe_float(sel_data.get("MKT"))
                    prems = safe_float(sel_data.get("_prems"))
                    collat = safe_float(sel_data.get("_collat"))
                    contracts = int(sel_data.get("QTY") or 1)
                    dte = int(sel_data.get("_DTE") or 0)
                    diagnostico = str(sel_data.get("Diagnostico") or "OK")
                    is_put = "CSP" in estrategia or "PUT" in estrategia.upper()
                    # Dividendos del ticker seleccionado
                    dividends_ticker = get_dividends_by_account(account_id, ticker=ticker)
                    if dividends_ticker:
                        st.markdown("#### Dividendos de " + ticker)
                        st.caption("Dividendos registrados para este ticker (reducen el cost basis).")
                        div_df = pd.DataFrame(dividends_ticker)
                        if not div_df.empty:
                            div_cols = [c for c in ["ex_date", "pay_date", "amount", "note"] if c in div_df.columns]
                            if div_cols:
                                div_df_show = div_df[div_cols].copy()
                                div_df_show = div_df_show.rename(columns={"ex_date": "Ex-date", "pay_date": "Pay-date", "amount": "Monto", "note": "Nota"})
                                st.dataframe(div_df_show, use_container_width=True, hide_index=True)
                        st.markdown("---")
                    st.markdown("### Análisis del riesgo (medidor)")
                    pnl_actual = prems - (max(0, (strike - mkt) * 100 * contracts) if is_put else max(0, (mkt - strike) * 100 * contracts))
                    estado_texto = "Ganando" if pnl_actual >= 0 else "Perdiendo"
                    max_ganancia = prems
                    max_perdida_put = (prems - strike * 100 * contracts) if is_put and strike else None
                    max_perdida_label = f"${fmt2(max_perdida_put)}" if is_put and max_perdida_put is not None else "Ilimitado"
                    hero_class = "win" if pnl_actual >= 0 else "loss"
                    st.markdown(f'<div class="rad-hero {hero_class}">P&L actual: ${fmt2(pnl_actual)} — {estado_texto}</div>', unsafe_allow_html=True)
                    st.markdown('<div class="rad-card">', unsafe_allow_html=True)
                    st.markdown(f"**{ticker} ({estrategia}) · {contracts} contrato(s)**")
                    from app.position_chart_utils import risk_analysis_score, build_gauge_price_axis, build_copyable_summary_position
                    score_dash = risk_analysis_score(pnl_actual, mkt, be, is_put, dte, 0, True)
                    status_dash = "Favorable" if score_dash > 66 else ("Evaluar" if score_dash > 33 else "Desfavorable")
                    fig_gauge_dash = build_gauge_price_axis(
                        strike or 0, be, mkt, dte, status_dash,
                        title="Análisis del riesgo",
                        is_put=is_put,
                    )
                    st.plotly_chart(fig_gauge_dash, use_container_width=True)
                    st.markdown(f"""
                    <div class="rad-metrics rad-metrics-grid">
                        <div class="rad-metric"><span class="k">Cumplimiento</span><span class="v">{score_dash}%</span></div>
                        <div class="rad-metric"><span class="k">Precio (actual)</span><span class="v">${fmt2(mkt)}</span></div>
                        <div class="rad-metric"><span class="k">Strike (ejercicio)</span><span class="v">${fmt2(strike)}</span></div>
                        <div class="rad-metric"><span class="k">BE (breakeven)</span><span class="v">${fmt2(be)}</span></div>
                        <div class="rad-metric"><span class="k">DTE (días a venc.)</span><span class="v">{dte} días</span></div>
                        <div class="rad-metric"><span class="k">P&L actual ($)</span><span class="v">${fmt2(pnl_actual)}</span></div>
                        <div class="rad-metric"><span class="k">Max ganancia ($)</span><span class="v" style="color:#3fb950">${fmt2(max_ganancia)}</span></div>
                        <div class="rad-metric"><span class="k">Max pérdida ($)</span><span class="v" style="color:#f85149">{max_perdida_label}</span></div>
                    </div>
                    """, unsafe_allow_html=True)
                    with st.expander("📋 Copiar / Compartir resumen de la posición", expanded=False):
                        copy_text_dash = build_copyable_summary_position(ticker, estrategia, contracts, strike or 0, be, mkt, prems, dte, pnl_actual, max_ganancia, max_perdida_label, estado_texto, diagnostico)
                        st.text_area("Resumen (selecciona y copia)", value=copy_text_dash, height=160, key="copy_dashboard_pos", disabled=True, label_visibility="collapsed")
                        st.caption("Selecciona todo el texto y cópialo para compartir (móvil: mantén pulsado).")
                    st.markdown('</div>', unsafe_allow_html=True)

                    if all_trades_historial:
                        st.markdown("### Gestionar posición (historial de la campaña)")
                        st.caption("Todos los pasos de la posición (apertura + rolls). Cada roll conserva el registro anterior y enlaza con parent_trade_id.")
                        trade_options = [(t["trade_id"], f"{str(t.get('trade_date', ''))[:10]} | {t.get('strategy_type', '')} | Strike ${fmt2(t.get('strike'))} | {t.get('status', '')}") for t in all_trades_historial]
                        sel_trade_idx = st.selectbox("Trade a editar/cerrar", range(len(trade_options)), format_func=lambda i: trade_options[i][1], key="sel_trade_gest")
                        selected_trade_id = trade_options[sel_trade_idx][0]
                        tr = next(t for t in all_trades_historial if t["trade_id"] == selected_trade_id)
                        is_open = (tr.get("status") or "").upper() == "OPEN"
                        is_stock = (tr.get("asset_type") or "").upper() == "STOCK"
                        with st.form(key=f"edit_trade_{selected_trade_id}"):
                            if is_stock:
                                try:
                                    trade_date_val = datetime.strptime(str(tr.get("trade_date") or date.today())[:10], "%Y-%m-%d").date()
                                except Exception:
                                    trade_date_val = date.today()
                                c1, c2 = st.columns(2)
                                with c1:
                                    edit_quantity = st.number_input("Cantidad (acciones)", value=int(tr.get("quantity") or 0), min_value=1, step=1, key=f"edit_qty_{selected_trade_id}")
                                    edit_price = st.number_input("Precio por acción", value=float(tr.get("price") or 0), min_value=0.0, step=0.01, format="%.2f", key=f"edit_price_{selected_trade_id}")
                                with c2:
                                    edit_trade_date = st.date_input("Fecha", value=trade_date_val, key=f"trade_date_{selected_trade_id}")
                                    edit_comment = st.text_area("Comentario", value=str(tr.get("comment") or ""), height=80, key=f"edit_comment_stock_{selected_trade_id}")
                            else:
                                try:
                                    exp_date_val = datetime.strptime(str(tr.get("expiration_date") or date.today())[:10], "%Y-%m-%d").date()
                                except Exception:
                                    exp_date_val = date.today()
                                try:
                                    trade_date_opt_val = datetime.strptime(str(tr.get("trade_date") or date.today())[:10], "%Y-%m-%d").date()
                                except Exception:
                                    trade_date_opt_val = date.today()
                                c1, c2 = st.columns(2)
                                with c1:
                                    edit_strike = st.number_input("Strike", value=float(tr.get("strike") or 0), min_value=0.0, step=0.5, format="%.2f", key=f"edit_strike_{selected_trade_id}")
                                    edit_price = st.number_input("Prima por contrato", value=float(tr.get("price") or 0), min_value=0.0, step=0.01, format="%.2f", key=f"edit_price_{selected_trade_id}")
                                    edit_trade_date_opt = st.date_input("Fecha inicio", value=trade_date_opt_val, key=f"trade_date_opt_{selected_trade_id}")
                                with c2:
                                    edit_exp = st.date_input("Expiración", value=exp_date_val, key=f"exp_date_{selected_trade_id}")
                                    edit_comment = st.text_area("Comentario", value=str(tr.get("comment") or ""), height=80, key=f"edit_comment_opt_{selected_trade_id}")
                            col_save, col_del, col_close, _ = st.columns([1, 1, 1, 2])
                            with col_save:
                                if st.form_submit_button("Guardar"):
                                    if is_stock:
                                        if edit_quantity < 1:
                                            st.error("La cantidad debe ser al menos 1.")
                                        elif not edit_price or edit_price <= 0:
                                            st.error("El precio por acción debe ser mayor que 0.")
                                        else:
                                            db.update_trade(selected_trade_id, account_id, price=round2(edit_price), quantity=edit_quantity, trade_date=edit_trade_date.isoformat(), comment=edit_comment or None)
                                            st.success("Guardado.")
                                            st.rerun()
                                    else:
                                        db.update_trade(selected_trade_id, account_id, price=round2(edit_price), strike=round2(edit_strike), expiration_date=edit_exp.isoformat(), trade_date=edit_trade_date_opt.isoformat(), comment=edit_comment or None)
                                        st.success("Guardado.")
                                        st.rerun()
                            with col_del:
                                if st.form_submit_button("Borrar"):
                                    conn = db.get_conn()
                                    conn.execute("DELETE FROM Trade WHERE trade_id = ?", (selected_trade_id,))
                                    conn.commit()
                                    conn.close()
                                    st.success("Trade borrado.")
                                    st.rerun()
                            with col_close:
                                if is_open and st.form_submit_button("Cerrar posición"):
                                    close_trade(selected_trade_id, account_id, date.today().isoformat())
                                    st.success("Posición cerrada.")
                                    st.rerun()
                                elif not is_open:
                                    st.caption("(Ya cerrado)")

    with tab_report:
        st.markdown('<div class="report-hero"><span class="report-hero-icon">📋</span> Bitácora y reportes</div>', unsafe_allow_html=True)
        st.markdown('<div class="dashboard-card"><h3>Reportes</h3>', unsafe_allow_html=True)
        if not account_id:
            st.info("Selecciona o crea una cuenta para ver reportes.")
        else:
            date_from = st.date_input("Desde", value=date.today().replace(month=1, day=1), key="report_date_from")
            date_to = st.date_input("Hasta", value=date.today(), key="report_date_to")
            date_from_s = date_from.isoformat()
            date_to_s = date_to.isoformat()
            account_name = acc_data.get("name", "")

            # Filtros adicionales para construir la bitácora por campañas
            all_trades_for_filters = get_trades_for_report(account_id, "1900-01-01", "2100-12-31")
            tickers_for_filter = sorted({t["ticker"] for t in all_trades_for_filters}) if all_trades_for_filters else []
            c_f1, c_f2, c_f3 = st.columns([1, 1, 1])
            with c_f1:
                ticker_filter = st.selectbox(
                    "Ticker (opcional)",
                    options=[""] + tickers_for_filter,
                    format_func=lambda x: x if x else "— Todos —",
                    key="report_ticker_filter",
                )
            with c_f2:
                strategy_filter = st.selectbox(
                    "Estrategia (opcional)",
                    options=["", "CSP", "CC", "STOCK", "ASSIGNMENT"],
                    format_func=lambda x: x if x else "— Todas —",
                    key="report_strategy_filter",
                )
            with c_f3:
                status_filter = st.selectbox(
                    "Estado (opcional)",
                    options=["", "OPEN", "CLOSED"],
                    format_func=lambda x: x if x else "— Ambos —",
                    key="report_status_filter",
                )

            report_trades = get_trades_for_report(
                account_id,
                date_from_s,
                date_to_s,
                ticker=ticker_filter or None,
                strategy=strategy_filter or None,
                status=status_filter or None,
            )
            if report_trades:
                prev_df = pd.DataFrame(report_trades)
                prev_df = prev_df.rename(
                    columns={
                        "trade_date": "Fecha",
                        "ticker": "Ticker",
                        "strategy_type": "Estrategia",
                        "quantity": "Cant.",
                        "price": "Prima",
                        "strike": "Strike",
                        "expiration_date": "Expiración",
                        "status": "Estado",
                        "campaign_root_id": "Campaña_id",
                        "campaign_start_date": "Inicio_campaña",
                    }
                )
                st.dataframe(prev_df[["Fecha", "Ticker", "Estrategia", "Cant.", "Prima", "Strike", "Expiración", "Estado"]], use_container_width=True, height=220)
            else:
                st.info("No hay trades en este rango.")
            tax = tax_efficiency_summary(account_id, date_from_s, date_to_s)
            st.json({"Total realizado": tax["total_realized_gain_loss"], "Trades cerrados": tax["closed_trades_count"], "Por ticker": tax["by_ticker"]})
            col1, col2, col3 = st.columns(3)
            csv_data = export_trades_csv(account_id, date_from_s, date_to_s, account_name)
            if csv_data:
                col1.download_button("📥 CSV", csv_data, file_name=f"alphawheel_trades_{date_from_s}_{date_to_s}.csv", mime="text/csv")
            excel_bytes = export_trades_excel(account_id, date_from_s, date_to_s, account_name)
            if excel_bytes:
                col2.download_button("📥 Excel", excel_bytes, file_name=f"alphawheel_bitacora_{date_from_s}_{date_to_s}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            pdf_bytes = export_trades_pdf(account_id, date_from_s, date_to_s, account_name)
            if pdf_bytes:
                col3.download_button("📥 PDF", pdf_bytes, file_name=f"alphawheel_bitacora_{date_from_s}_{date_to_s}.pdf", mime="application/pdf")
        st.markdown('</div>', unsafe_allow_html=True)  # dashboard-card Reportes

    with tab_settings:
        st.markdown('<div class="dashboard-card"><h3>Mi cuenta</h3>', unsafe_allow_html=True)
        if account_id:
            acc = get_account_by_id(account_id, user_id)
        else:
            acc = None
        if acc:
            new_token = st.text_input("Token de acceso (Tradier)", value=(acc.get("access_token") or ""), type="password", placeholder="Token Tradier", key="token_mi_cuenta")
            env = st.selectbox("Entorno", ["sandbox (pruebas)", "prod (real)"], index=0 if (acc.get("environment") or "sandbox") == "sandbox" else 1, key="env_tradier")
            env_val = "sandbox" if "sandbox" in (env or "") else "prod"
            cap = st.number_input("Capital ($)", value=float(acc.get("cap_total") or 100000), step=1000.0, format="%.2f", key="cap_mi_cuenta")
            target = st.number_input("Meta anual (%)", value=float(acc.get("target_ann") or 20), step=0.5, format="%.2f", key="target_mi_cuenta")
            max_ticker = st.number_input("Máx. por ticker (%)", value=float(acc.get("max_per_ticker") or 10), step=0.5, format="%.2f", key="max_ticker_mi_cuenta")
            if st.button("Guardar token y datos"):
                db.update_account_token(account_id, user_id, new_token or "", env_val)
                db.update_account_config(account_id, user_id, cap, target, max_ticker)
                for k in ["token_mi_cuenta", "cap_mi_cuenta", "target_mi_cuenta", "max_ticker_mi_cuenta"]:
                    if k in st.session_state:
                        del st.session_state[k]
                st.success("Guardado. Los datos de la cuenta y el token se han actualizado.")
                st.rerun()
            # Borrar cuenta: solo si hay más de una
            accounts_list = get_accounts_for_current_user()
            if len(accounts_list) > 1:
                st.markdown("---")
                if st.button("🗑️ Borrar esta cuenta", type="secondary", key="delete_acc_btn"):
                    if delete_account(account_id, user_id):
                        if get_current_account_id() == account_id:
                            remaining = [a for a in accounts_list if a["account_id"] != account_id]
                            set_current_account_id(remaining[0]["account_id"] if remaining else None)
                        st.success("Cuenta borrada.")
                        st.rerun()
        st.markdown("---")
        st.subheader("Nueva cuenta")
        new_name = st.text_input("Nombre cuenta (ej. Estrategia Rueda, IRA)", key="new_acc_name")
        if st.button("Crear cuenta"):
            if new_name:
                db.create_account(user_id, new_name.strip())
                if "new_acc_name" in st.session_state:
                    del st.session_state["new_acc_name"]
                st.success("Cuenta creada. Selecciónala en el sidebar.")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)  # dashboard-card Mi cuenta
