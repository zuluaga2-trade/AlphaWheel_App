# AlphaWheel Pro - Interfaz "Alpha Radar" (The Cockpit)
# Multi-usuario, aislamiento por User_ID / Account_ID, Tradier modular, bitácora y reportes
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import html as html_module
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, date, timedelta

from database import db
from database.db import init_db, get_accounts_by_user, get_trades_by_account, get_account_by_id, close_trade, delete_account, get_dividends_by_account
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
from reports.bitacora import export_trades_csv, export_trades_excel, export_trades_pdf, tax_efficiency_summary, get_trades_for_report
from app.cockpit import render_screener_page, _render_screener_sidebar_form, _render_tutorial_tab
import config

# Inicializar BD al arranque
init_db()

st.set_page_config(
    page_title="AlphaWheel Pro",
    layout="wide",
    page_icon="🦅",
    initial_sidebar_state="expanded",
    menu_items={"Get help": None, "Report a Bug": None, "About": None},
)

# --- Regla: cifras con 2 decimales y coma como separador de miles ---
def fmt2(val):
    """Formatea número a 2 decimales con coma como separador de miles (ej. 360,000.50)."""
    if val is None: return "—"
    v = round2(val)
    return f"{v:,.2f}" if isinstance(v, (int, float)) else str(v)

# --- Estética profesional: dashboard listo para GitHub, multi-cuenta ---
st.markdown("""
<style>
    .stApp { background: linear-gradient(180deg, #0d1117 0%, #161b22 100%); color: #e6edf3; min-height: 100vh; }
    [data-testid="stMetricValue"] { font-family: 'JetBrains Mono', 'Consolas', monospace !important; color: #58a6ff !important; font-size: 1.35rem; font-weight: 600; letter-spacing: 0.02em; }
    [data-testid="stMetricLabel"] { color: #8b949e; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .status-container { background: #161b22; padding: 1.25rem 1.5rem; border-radius: 12px; border: 1px solid #21262d; margin-bottom: 1.5rem; box-shadow: 0 1px 2px rgba(0,0,0,0.2); }
    .capital-ring { background: #161b22; border: 1px solid #21262d; border-radius: 12px; padding: 1rem 1.25rem; margin-bottom: 1.5rem; box-shadow: 0 1px 2px rgba(0,0,0,0.2); }
    [data-testid="stProgressBar"] { background: #21262d !important; border-radius: 8px; }
    [data-testid="stProgressBar"] > div { background: linear-gradient(90deg, #238636, #58a6ff) !important; min-width: 2% !important; border-radius: 8px; }
    .prog-annual-wrap { margin-bottom: 10px; }
    .prog-annual-bar { height: 10px; background: #21262d; border-radius: 8px; overflow: hidden; }
    .prog-annual-fill { height: 100%; background: linear-gradient(90deg, #238636, #58a6ff); border-radius: 8px; }
    .prog-exp-bar { height: 12px; border-radius: 8px; display: flex; overflow: hidden; }
    .prog-exp-seg { height: 100%; min-width: 2px; }
    .prog-exp-seg.red { background: #c85a54; }
    .prog-exp-seg.yellow { background: #c9b84a; }
    .prog-exp-seg.green { background: #4ab85a; }
    .prog-exp-seg.orange { background: #d29922; }
    /* Position Performance (estilo captura) */
    .position-performance { background: #161b22; border-radius: 14px; padding: 1.25rem 1.5rem; margin-bottom: 1.5rem; border: 2px solid rgba(63,185,80,0.5); box-shadow: 0 4px 14px rgba(0,0,0,0.25); }
    .position-performance.behind { border-color: rgba(248,81,73,0.5); }
    .position-performance h3 { color: #e6edf3; font-size: 1.1rem; margin: 0 0 1rem 0; font-weight: 600; }
    .on-track-badge { display: inline-block; padding: 0.35rem 0.75rem; border-radius: 8px; font-size: 0.85rem; font-weight: 700; background: #238636; color: #fff; }
    .on-track-badge.behind { background: #da3633; }
    .annual-vs-target { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 0.75rem; }
    .annual-vs-target .big-pct { font-size: 1.5rem; font-weight: 700; color: #58a6ff; font-family: 'JetBrains Mono', monospace; }
    .annual-vs-target .vs { color: #8b949e; font-size: 1rem; }
    .annual-vs-target .target-pct { font-size: 1.5rem; font-weight: 700; color: #8b949e; font-family: 'JetBrains Mono', monospace; }
    .total-return-label { font-size: 0.9rem; color: #8b949e; margin-top: 0.25rem; }
    .total-return-value { font-size: 1rem; font-weight: 600; color: #3fb950; }
    .perf-cards { display: flex; gap: 1rem; flex-wrap: wrap; margin-top: 1rem; }
    .perf-card { background: #0d1117; border: 1px solid #21262d; border-radius: 10px; padding: 0.75rem 1rem; min-width: 100px; }
    .perf-card .label { font-size: 0.7rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.25rem; }
    .perf-card .value { font-size: 1.1rem; font-weight: 700; color: #e6edf3; font-family: 'JetBrains Mono', monospace; }
    /* Objetivo anual bar (mismo estilo que timeline) */
    .timeline-bar-wrap { height: 28px; border-radius: 14px; overflow: hidden; background: #21262d; margin: 0.5rem 0 1rem 0; }
    .timeline-bar-fill { height: 100%; border-radius: 14px; background: linear-gradient(90deg, #238636, #58a6ff); transition: width 0.2s ease; }
    .timeline-section-title { font-size: 0.95rem; color: #e6edf3; margin-bottom: 0.35rem; font-weight: 600; }
    .timeline-section-sub { font-size: 0.8rem; color: #8b949e; }
    /* Expiration Timeline (60 días, segmentos 0-3, 4-7, 8-14, 15+) */
    .expiration-timeline { background: #161b22; border: 1px solid #21262d; border-radius: 14px; padding: 1.25rem 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 4px 14px rgba(0,0,0,0.25); }
    .expiration-timeline h3 { color: #e6edf3; font-size: 1.1rem; margin: 0 0 0.5rem 0; font-weight: 600; }
    .expiration-timeline .next-days { color: #8b949e; font-size: 0.85rem; }
    .timeline-60-bar { height: 28px; border-radius: 14px; display: flex; overflow: hidden; margin: 0.75rem 0 0.25rem 0; background: #0d1117; }
    .timeline-60-seg { height: 100%; min-width: 4px; }
    .timeline-60-seg.s0 { background: #c85a54; width: 5%; }
    .timeline-60-seg.s1 { background: #d29922; width: 6.67%; }
    .timeline-60-seg.s2 { background: #c9b84a; width: 11.67%; }
    .timeline-60-seg.s3 { background: #4ab85a; width: 76.66%; }
    .timeline-60-marker { position: relative; margin-top: -36px; margin-bottom: 8px; display: flex; justify-content: var(--marker-pos, 30%); }
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
    .timeline-60-labels { display: flex; justify-content: space-between; font-size: 0.7rem; color: #8b949e; margin-bottom: 0.5rem; }
    .timeline-legend { display: flex; gap: 1rem; flex-wrap: wrap; margin-top: 0.75rem; font-size: 0.8rem; color: #8b949e; }
    .timeline-legend span { display: flex; align-items: center; gap: 0.35rem; }
    .timeline-legend .dot { width: 8px; height: 8px; border-radius: 50%; }
    .timeline-legend .dot.red { background: #c85a54; }
    .timeline-legend .dot.orange { background: #d29922; }
    .timeline-legend .dot.yellow { background: #c9b84a; }
    .timeline-legend .dot.green { background: #4ab85a; }
    /* Capital allocation bar (segmented, same style as timeline) */
    .capital-allocation-bar .capital-segments { display: flex; width: 100%; height: 100%; }
    .capital-allocation-bar .capital-seg { display: block; height: 100%; min-width: 2px; font-size: 0.7rem; color: #0d1117; text-align: center; line-height: 28px; white-space: nowrap; overflow: hidden; }
    .capital-legend .capital-legend-item { display: inline-flex; align-items: center; gap: 0.35rem; margin-right: 1rem; }
    .capital-legend .swatch { width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0; }
    .dashboard-card { background: #161b22; border: 1px solid #21262d; border-radius: 14px; padding: 1.25rem 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 4px 14px rgba(0,0,0,0.25); }
    .dashboard-card.resumen-cuenta-card { border: 2px solid rgba(63,185,80,0.5); }
    .dashboard-card h3 { color: #e6edf3; font-size: 1.1rem; margin: 0 0 0.75rem 0; font-weight: 600; }
    .dashboard-card .card-sub { color: #8b949e; font-size: 0.85rem; margin-top: 0.5rem; }
    .summary-strip { background: #0d1117; border-radius: 10px; padding: 0.75rem 1rem; margin: 0.5rem 0 0 0; font-size: 0.95rem; color: #e6edf3; font-family: 'JetBrains Mono', monospace; }
    .summary-strip strong { color: #58a6ff; }
    .card-panel { background: #161b22; border: 1px solid #21262d; border-radius: 12px; padding: 1.25rem; margin: 1rem 0; box-shadow: 0 1px 2px rgba(0,0,0,0.2); }
    .card-panel h3 { color: #58a6ff; font-size: 1rem; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 1px solid #21262d; }
    .rad-status-strip { display: flex; gap: 1rem; flex-wrap: wrap; padding: 0.75rem 1rem; background: #0d1117; border-radius: 8px; margin-bottom: 1rem; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; }
    .rad-status-item { display: flex; align-items: center; gap: 0.35rem; }
    .rad-status-item .label { color: #8b949e; }
    .rad-status-item .value { color: #e6edf3; font-weight: 600; }
    .rad-status-item.ok .value { color: #3fb950; }
    .rad-status-item.risk .value { color: #f85149; }
    .sidebar .stSelectbox label { font-size: 0.85rem; color: #8b949e; }
    div[data-testid="stDataFrame"] { border-radius: 8px; overflow: hidden; border: 1px solid #21262d; }
    .alert-danger { background: rgba(248,81,73,0.12); border: 1px solid #f85149; border-radius: 8px; padding: 10px; margin: 8px 0; color: #ff7b72; }
    /* Tabla gestión: diseño profesional */
    .gest-table-wrap { background: #161b22; border: 1px solid #21262d; border-radius: 14px; overflow: hidden; margin: 1.5rem 0 2rem 0; box-shadow: 0 6px 20px rgba(0,0,0,0.3); padding: 0; }
    .gest-table { width: 100%; border-collapse: collapse; font-size: 0.95rem; }
    .gest-table thead { background: linear-gradient(180deg, #21262d 0%, #30363d 100%); color: #e6edf3; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; font-size: 0.8rem; }
    .gest-table th { padding: 16px 20px; text-align: left; border-bottom: 2px solid #58a6ff; }
    .gest-table td { padding: 14px 20px; border-bottom: 1px solid #21262d; color: #c9d1d9; line-height: 1.4; }
    .gest-table tbody tr:hover { background: rgba(88,166,255,0.06); }
    .gest-table tbody tr:nth-child(even) { background: rgba(22,27,34,0.5); }
    .gest-table tbody tr:nth-child(even):hover { background: rgba(88,166,255,0.08); }
    .gest-table .num { font-family: 'JetBrains Mono', monospace; color: #58a6ff; font-weight: 500; }
    .gest-table .date { font-family: 'JetBrains Mono', monospace; color: #8b949e; }
    .gest-table tbody tr.selected { background: rgba(88,166,255,0.18) !important; border-left: 4px solid #58a6ff; }
    .gest-table tbody tr.selected:hover { background: rgba(88,166,255,0.22) !important; }
    .section-title { font-size: 1.1rem; font-weight: 600; color: #58a6ff; margin-bottom: 0.5rem; padding-bottom: 0.5rem; border-bottom: 1px solid #21262d; }
    .rad-hero { padding: 1.25rem 1.5rem; border-radius: 12px; margin-bottom: 1.25rem; font-family: 'JetBrains Mono', monospace; font-size: 1.15rem; font-weight: 600; text-align: center; }
    .rad-hero.win { background: linear-gradient(135deg, rgba(63,185,80,0.25) 0%, rgba(63,185,80,0.08) 100%); border: 1px solid rgba(63,185,80,0.5); color: #3fb950; }
    .rad-hero.loss { background: linear-gradient(135deg, rgba(248,81,73,0.25) 0%, rgba(248,81,73,0.08) 100%); border: 1px solid rgba(248,81,73,0.5); color: #f85149; }
    .rad-card { background: #161b22; border: 1px solid #21262d; border-radius: 12px; padding: 1.5rem; margin: 1.5rem 0; box-shadow: 0 4px 12px rgba(0,0,0,0.25); }
    .rad-metrics { display: flex; flex-wrap: wrap; gap: 1.5rem; padding: 1rem 1.25rem; background: #0d1117; border-radius: 10px; margin-top: 1rem; font-family: 'JetBrains Mono', monospace; }
    .rad-metric { display: flex; flex-direction: column; gap: 0.25rem; min-width: 0; }
    .rad-metric .k { font-size: 0.75rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.05em; }
    .rad-metric .v { font-size: 1.1rem; font-weight: 600; color: #e6edf3; }
    .rad-metric.ok .v { color: #3fb950; }
    .rad-metric.risk .v { color: #f85149; }
    .rad-metrics-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 1rem; }
    @media (max-width: 768px) {
        .rad-metrics-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.5rem 0.75rem; padding: 0.75rem 1rem; }
        .rad-metric .k { font-size: 0.7rem; }
        .rad-metric .v { font-size: 1rem; word-break: break-word; }
    }
    .rad-thermometer-wrap { margin: 1.5rem 0; display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; }
    .rad-thermometer-label { font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: #8b949e; }
    .rad-thermometer-bar { flex: 1; min-width: 180px; height: 28px; background: linear-gradient(90deg, #f85149 0%, #8b949e 50%, #3fb950 100%); border-radius: 14px; position: relative; }
    .rad-thermometer-fill { position: absolute; left: 0; top: 0; bottom: 0; width: 50%; background: rgba(88,166,255,0.4); border-radius: 14px 0 0 14px; pointer-events: none; }
    .rad-thermometer-marker { position: absolute; top: -24px; transform: translateX(-50%); font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; font-weight: 600; color: #58a6ff; white-space: nowrap; background: #161b22; padding: 2px 8px; border-radius: 6px; border: 1px solid #58a6ff; }
    .rad-thermometer-caption { font-size: 0.8rem; color: #8b949e; margin-top: 0.5rem; }
    .rad-scenarios { width: 100%; max-width: 360px; border-collapse: collapse; font-size: 0.9rem; margin: 0.75rem 0; }
    .rad-scenarios th, .rad-scenarios td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #21262d; }
    .rad-scenarios th { color: #8b949e; font-weight: 600; }
    .rad-scenarios .num { font-family: 'JetBrains Mono', monospace; color: #58a6ff; }
    .rad-scenarios .tag { color: #3fb950; font-size: 0.85rem; }
    .rad-ruler-wrap { margin: 1rem 0; }
    .rad-ruler-bar { position: relative; height: 36px; background: linear-gradient(90deg, rgba(248,81,73,0.3) 0%, rgba(63,185,80,0.3) 100%); border-radius: 8px; margin-bottom: 4px; }
    .rad-ruler-tick { position: absolute; top: 50%; transform: translate(-50%, -50%); font-size: 0.75rem; font-weight: 600; padding: 2px 6px; border-radius: 4px; background: #161b22; border: 1px solid #30363d; }
    .rad-ruler-tick.current { background: #58a6ff; color: #fff; border-color: #58a6ff; }
    .rad-ruler-labels { display: flex; justify-content: space-between; font-size: 0.75rem; color: #8b949e; }
    /* Reportes: hero y cards */
    .report-hero { background: linear-gradient(135deg, #1a2332 0%, #0d1117 50%); border: 1px solid #30363d; border-radius: 14px; padding: 1.25rem 1.5rem; margin-bottom: 1.5rem; font-size: 1.25rem; font-weight: 600; color: #e6edf3; display: flex; align-items: center; gap: 0.75rem; box-shadow: 0 4px 16px rgba(0,0,0,0.3); }
    .report-hero-icon { font-size: 1.5rem; filter: drop-shadow(0 0 8px rgba(88,166,255,0.4)); }
    /* Brand header: barra superior sutil */
    [data-testid="stSidebar"] > div:first-child { background: linear-gradient(180deg, #161b22 0%, #0d1117 100%); border-right: 1px solid #21262d; }
    [data-testid="stSidebar"] [data-testid="stMarkdown"] h1:first-of-type { background: linear-gradient(90deg, #58a6ff, #79c0ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; font-weight: 700; letter-spacing: 0.02em; }
    .stApp > header { background: linear-gradient(90deg, #0d1117 0%, #161b22 100%); border-bottom: 1px solid #21262d; }
    /* Cards con ligera elevación */
    .card-panel, .rad-card, .capital-ring, .status-container { box-shadow: 0 4px 14px rgba(0,0,0,0.25); transition: box-shadow 0.2s ease; }
    .card-panel:hover, .rad-card:hover { box-shadow: 0 6px 20px rgba(88,166,255,0.08); }
</style>
""", unsafe_allow_html=True)


def get_current_user_id():
    """Usuario actual (session). Por defecto primer usuario; en producción vendría de auth."""
    users = db.get_users()
    if not users:
        uid = db.ensure_user("usuario@alphawheel.local", "Usuario Principal")
        users = db.get_users()
    if "current_user_id" not in st.session_state and users:
        st.session_state["current_user_id"] = users[0]["user_id"]
    return st.session_state.get("current_user_id")


def get_current_account_id():
    if "current_account_id" not in st.session_state:
        return None
    return st.session_state["current_account_id"]


# --- Sidebar: usuario, cuentas, token, formularios ---
with st.sidebar:
    st.header("🦅 Alpha Control")
    user_id = get_current_user_id()
    users = db.get_users()
    if users:
        user_options = {f"{u['display_name'] or u['email']}": u["user_id"] for u in users}
        sel_user = st.selectbox("Usuario", list(user_options.keys()), key="sel_user")
        st.session_state["current_user_id"] = user_options[sel_user]
        user_id = st.session_state["current_user_id"]

    main_view = st.radio("Ir a", ["🔎 Screener", "📊 Mi Cuenta"], key="main_view_radio_m", horizontal=True)
    show_screener_page = main_view == "🔎 Screener"

    run_scan = False
    account_id = None
    acc_data = {}
    token = ""
    if show_screener_page:
        st.caption("**Filtros del Screener** — Configura y pulsa **Iniciar barrido**.")
        try:
            run_scan = _render_screener_sidebar_form(user_id)
        except Exception as e:
            st.error(f"Error al cargar filtros: {e}")
    else:
        accounts = get_accounts_by_user(user_id) if user_id else []
        if not accounts:
            st.warning("Sin cuentas. Ve a la pestaña **Mi cuenta** para crear una.")
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
            st.session_state["current_account_id"] = acc_data["account_id"]
            account_id = acc_data["account_id"]

        # Estado conexión (Online/Offline) — solo si hay cuenta seleccionada
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
            st.caption("Token no configurado. Pestaña **Mi cuenta** → Token Tradier")

        if account_id:
            st.caption("Para conectar Tradier y actualizar datos → pestaña **Mi cuenta**")

        # Roll-over (arriba para que se vea bien)
        with st.expander("🔄 Roll-over", expanded=False):
            if not account_id:
                st.caption("Selecciona una cuenta para hacer roll-over.")
            else:
                roll_type = st.radio("Tipo de posición a hacer roll", ["CSP", "CC"], horizontal=True, key="roll_type")
                trades_open = get_trades_by_account(account_id, status="OPEN")
                roll_list = [t for t in trades_open if (t.get("strategy_type") or "").upper() == roll_type]
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
                        for k in ["roll_new_strike", "roll_new_exp", "roll_new_premium", "roll_comment"]:
                            if k in st.session_state:
                                del st.session_state[k]
                        st.success("Roll-over ejecutado: posición anterior cerrada y nueva registrada. Bitácora actualizada.")
                        st.rerun()

        # Add Position / Operación
        if not account_id:
            st.caption("Crea una cuenta en **Mi cuenta** para registrar posiciones.")
        with st.expander("➕ Añadir posición", expanded=False):
            if not account_id:
                st.info("Crea una cuenta en la pestaña **Mi cuenta** para registrar movimientos.")
            else:
                st.caption("**CSP** = vender put (colateral strike×100×contratos; no requiere acciones). **CC** = poseer las acciones y vender call (registra antes compra directa o asignación).")
                reg_type = st.radio("Tipo", ["CSP", "CC", "Compra directa", "Asignación CSP", "Asignación CC", "Dividendo", "Ajuste"], horizontal=False, key="add_reg_type")
                trade_date = st.date_input("Fecha", value=date.today(), key="add_trade_date").isoformat()

                if reg_type == "CSP":
                    ticker = st.text_input("Ticker", value="", key="add_csp_ticker", placeholder="Ej. AAPL", help="CSP: vendes un put; el colateral es strike × 100 × contratos.").strip().upper()
                    qty = st.number_input("Contratos", min_value=1, value=1, key="add_csp_qty")
                    strike = st.number_input("Strike", min_value=0.0, value=0.0, step=0.5, key="add_csp_strike", help="Obligatorio: precio de ejercicio del put.")
                    premium = st.number_input("Prima por contrato", min_value=0.0, value=0.0, step=0.01, key="add_csp_premium")
                    exp_default = date.today() + timedelta(days=30)
                    exp_date = st.date_input("Expiración", value=exp_default, key="add_csp_exp")
                    exp = exp_date.isoformat()
                    comment = st.text_area("Comentario (bitácora)", value="", key="add_csp_comment")
                    if st.button("Registrar CSP"):
                        if not ticker:
                            st.error("Indica el **ticker** (ej. AAPL).")
                        elif not strike or strike <= 0:
                            st.error("Indica el **strike** (debe ser mayor que 0).")
                        else:
                            try:
                                register_csp_opening(account_id, user_id, ticker, qty, strike, premium, exp, trade_date, comment or None)
                                for k in ["add_trade_date", "add_csp_ticker", "add_csp_qty", "add_csp_strike", "add_csp_premium", "add_csp_exp", "add_csp_comment"]:
                                    if k in st.session_state:
                                        del st.session_state[k]
                                st.success("CSP registrado. Formulario borrado.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"No se pudo registrar: {e}")

                elif reg_type == "CC":
                    ticker = st.text_input("Ticker", value="", key="add_cc_ticker", placeholder="Ej. AAPL", help="Covered Call: vendes una call teniendo las acciones. Necesitas al menos contratos × 100 acciones.").strip().upper()
                    qty = st.number_input("Contratos", min_value=1, value=1, key="add_cc_qty")
                    shares_needed = qty * 100
                    if ticker:
                        shares_now = get_stock_quantity(account_id, ticker)
                        if shares_now < shares_needed:
                            st.warning(f"**Covered Call requiere tener las acciones.** Tienes **{shares_now}** acciones de {ticker}; necesitas al menos **{shares_needed}** (contratos × 100). Registra primero una **compra directa** o una **asignación** de put.")
                        else:
                            st.caption(f"Acciones de {ticker}: **{shares_now}** (necesitas {shares_needed} para {qty} contrato(s)).")
                    strike = st.number_input("Strike", min_value=0.0, value=0.0, step=0.5, key="add_cc_strike", help="Obligatorio: precio de ejercicio de la call.")
                    premium = st.number_input("Prima por contrato", min_value=0.0, value=0.0, step=0.01, key="add_cc_premium")
                    exp_default_cc = date.today() + timedelta(days=30)
                    exp_date_cc = st.date_input("Expiración", value=exp_default_cc, key="add_cc_exp")
                    exp = exp_date_cc.isoformat()
                    comment = st.text_area("Comentario", value="", key="add_cc_comment")
                    if st.button("Registrar CC"):
                        if not ticker:
                            st.error("Indica el **ticker** (ej. AAPL).")
                        elif not strike or strike <= 0:
                            st.error("Indica el **strike** (debe ser mayor que 0).")
                        elif get_stock_quantity(account_id, ticker) < qty * 100:
                            st.error(f"No tienes suficientes acciones para este Covered Call. Necesitas **{qty * 100}** acciones de **{ticker}**. Registra primero una **compra directa** o una **asignación** de put.")
                        else:
                            try:
                                register_cc_opening(account_id, user_id, ticker, qty, strike, premium, exp, trade_date, comment or None)
                                for k in ["add_trade_date", "add_cc_ticker", "add_cc_qty", "add_cc_strike", "add_cc_premium", "add_cc_exp", "add_cc_comment"]:
                                    if k in st.session_state:
                                        del st.session_state[k]
                                st.success("CC registrado. Formulario borrado.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"No se pudo registrar: {e}")

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
                            try:
                                register_direct_purchase(account_id, user_id, ticker, qty, price, trade_date, comment or None)
                                for k in ["add_trade_date", "add_buy_ticker", "add_buy_qty", "add_buy_price", "add_buy_comment"]:
                                    if k in st.session_state:
                                        del st.session_state[k]
                                st.success("Compra registrada. Formulario borrado.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"No se pudo registrar: {e}")

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
                            try:
                                register_assignment(account_id, user_id, parent_trade_id, tr["ticker"], (tr.get("quantity") or 0) * 100, assign_price, trade_date, comment_assign or None)
                                for k in ["add_assign_csp_sel", "add_assign_price", "add_assign_comment"]:
                                    if k in st.session_state:
                                        del st.session_state[k]
                                st.success("Asignación registrada: CSP cerrado y acciones recibidas en la cuenta.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"No se pudo registrar: {e}")
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
                            try:
                                close_trade(cc_trade_id, account_id, trade_date)
                                for k in ["add_exercise_cc_sel", "add_exercise_cc_comment"]:
                                    if k in st.session_state:
                                        del st.session_state[k]
                                st.success("Asignación de CC registrada: posición cerrada. Las acciones fueron vendidas al strike.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"No se pudo registrar: {e}")

                elif reg_type == "Dividendo":
                    tickers_owned = [s["ticker"] for s in get_position_summary(account_id)] if account_id else []
                    if not tickers_owned:
                        st.caption("Solo puedes registrar dividendos de tickers que posees. No tienes posiciones en la cuenta; registra antes una compra directa o CSP/CC.")
                        ticker = ""
                        amount = 0.0
                    else:
                        ticker_sel = st.selectbox("Ticker (solo posiciones que posees)", options=[""] + sorted(tickers_owned), key="add_div_ticker_sel", format_func=lambda x: x if x else "— Elige un ticker —")
                        ticker = (ticker_sel or "").strip().upper()
                        amount = st.number_input("Monto total", min_value=0.0, value=0.0, step=0.01, key="add_div_amount")
                        ex_date_w = st.date_input("Ex-date", value=date.today(), key="add_div_ex_date")
                        ex_date = ex_date_w.isoformat()
                        pay_date_w = st.date_input("Pay-date (opcional)", value=None, key="add_div_pay_date")
                        pay_date = pay_date_w.isoformat() if pay_date_w else None
                        note = st.text_area("Nota", value="", key="add_div_note")
                        if st.button("Registrar dividendo"):
                            if not ticker:
                                st.error("Elige un **ticker** de la lista (posiciones que posees).")
                            else:
                                try:
                                    register_dividend(account_id, ticker, amount, ex_date, pay_date, note or None)
                                    for k in ["add_trade_date", "add_div_ticker", "add_div_ticker_sel", "add_div_amount", "add_div_ex_date", "add_div_pay_date", "add_div_note"]:
                                        if k in st.session_state:
                                            del st.session_state[k]
                                    st.success("Dividendo registrado. Formulario borrado.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"No se pudo registrar: {e}")

                elif reg_type == "Ajuste":
                    st.caption("**Ajuste**: para splits de acciones, corrección de cost basis u otros ajustes de posición en un ticker.")
                    ticker = st.text_input("Ticker", value="", key="add_adj_ticker", placeholder="Ej. AAPL").strip().upper()
                    adj_type = st.selectbox("Tipo", ["SPLIT", "COST_BASIS_CORRECTION", "OTHER"], key="add_adj_type")
                    old_val = st.number_input("Valor anterior", value=0.0, step=0.01, key="add_adj_old")
                    new_val = st.number_input("Valor nuevo", value=0.0, step=0.01, key="add_adj_new")
                    note = st.text_area("Nota", value="", key="add_adj_note")
                    if st.button("Registrar ajuste"):
                        if not ticker:
                            st.error("Indica el **ticker**.")
                        else:
                            try:
                                register_adjustment(account_id, ticker, adj_type, old_val, new_val, note or None)
                                for k in ["add_trade_date", "add_adj_ticker", "add_adj_type", "add_adj_old", "add_adj_new", "add_adj_note"]:
                                    if k in st.session_state:
                                        del st.session_state[k]
                                st.success("Ajuste registrado. Formulario borrado.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"No se pudo registrar: {e}")

# --- Vista Screener (por usuario) o tabs de cuenta ---
if show_screener_page:
    render_screener_page(user_id, run_scan)
    st.stop()

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

        # Colateral y utilización
        colateral = 0.0
        for s in summaries:
            if s.get("strategy_type") == "CSP" and s.get("strike"):
                colateral += safe_float(s["strike"]) * 100 * s.get("option_contracts", 0)
            elif s.get("stock_quantity", 0) > 0:
                colateral += safe_float(s.get("stock_cost_total") or 0)
        colateral = round2(colateral)
        cash_libre = round2(max(0, cap_total - colateral))
        max_per_ticker_pct = safe_float(acc_data.get("max_per_ticker"))

        # Encabezado y Resumen de cuenta (marco verde como Rendimiento)
        st.markdown(f'<div style="margin-bottom:1rem;"><span style="font-size:1.5rem;font-weight:600;color:#58a6ff;">AlphaWheel Pro</span> <span style="color:#8b949e;font-size:0.9rem;">— {acc_data.get("name", "Cuenta")}</span></div>', unsafe_allow_html=True)
        # Resumen de cuenta: summary-strip + 7 perf-cards (las 4 de rendimiento se añaden cuando hay posiciones)
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
            # Precios en tiempo real (Tradier)
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

            total_primas = sum((s.get("premiums_received") or 0) for s in summaries)
            total_primas = round2(total_primas)
            # Anualizado global: (RoC% / días promedio posición) * 365; usamos DTE como proxy si no tenemos días posición
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
                prem_per_contract = (prems / (contracts * 100)) if contracts else 0
                net_prem = prems
                open_date = s.get("trade_date") or ""
                exp_date = s.get("expiration_date") or ""
                try:
                    open_short = datetime.strptime(str(open_date)[:10], "%Y-%m-%d").strftime("%b %d") if open_date else "—"
                except Exception:
                    open_short = str(open_date)[:10] if open_date else "—"
                try:
                    exp_short = datetime.strptime(str(exp_date)[:10], "%Y-%m-%d").strftime("%b %d") if exp_date else "—"
                except Exception:
                    exp_short = str(exp_date)[:10] if exp_date else "—"
                fecha_inicio = str(open_date)[:10] if open_date else "—"
                fecha_exp = str(exp_date)[:10] if exp_date else "—"
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
                if zone == "—" or not strike:
                    pop_label = "N/A"
                else:
                    dist_pct = abs((mkt or 0) - strike) / strike * 100
                    pop_label = f"~{min(99, max(1, round2(50 + dist_pct * 0.5)))}%"
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
                    "Fecha inicio": fecha_inicio,
                    "Fecha exp.": fecha_exp,
                    "Días posición": dias_posicion,
                    "Precio MKT": round2(mkt),
                    "Strike": round2(strike) if strike else "—",
                    "Prima recibida": round2(net_prem),
                    "Breakeven": round2(be),
                    "Diagnostico": diagnostico,
                    "Retorno": round2(roc),
                    "Anualizado": round2(ann_ret),
                    "POP": pop_label,
                    "SYMBOL": ticker,
                    "QTY": contracts,
                    "NET PREM": round2(net_prem),
                    "COLLAT": round2(collat),
                    "ALLOC %": round2(alloc_pct),
                    "OPEN": open_short,
                    "EXP": exp_short,
                    "DUR": f"{dte}d",
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
            # Orden: en riesgo primero; resaltar con fondo rojo suave
            df_dash["_sort_diag"] = df_dash["Diagnostico"].apply(lambda x: (0 if x == "Riesgo" else (1 if x == "Perdiendo" else 2)))
            df_dash = df_dash.sort_values("_sort_diag").drop(columns=["_sort_diag"])

            used_pct = (colateral / cap_total * 100) if cap_total else 0
            max_per_ticker_pct = safe_float(acc_data.get("max_per_ticker"))
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
                    fig_pie = go.Figure(data=[go.Pie(labels=pie_labels, values=pie_values, hole=0.5, marker_colors=pie_colors, pull=pull, textinfo="label+percent", textposition="outside", outsidetextfont=dict(color="#e6edf3", size=12))])
                    fig_pie.update_layout(template="plotly_dark", height=shared_chart_height, margin=dict(l=10, r=10, t=30, b=50), showlegend=True, legend=dict(orientation="h", yanchor="top", y=-0.02), paper_bgcolor="rgba(22,27,34,0.98)", plot_bgcolor="rgba(22,27,34,0.98)", font=dict(color="#e6edf3"))
                    fig_pie.update_traces(textfont_color="#e6edf3")
                    center_text = f"Disponible<br>${fmt2(cash_libre)}<br>({fmt2(w_avail_pct)}%)"
                    fig_pie.add_annotation(text=center_text, x=0.5, y=0.5, font=dict(size=13, color="#8b949e"), showarrow=False)
                else:
                    fig_pie = go.Figure()
                    fig_pie.add_annotation(text=f"Sin posiciones.<br>Disponible: ${fmt2(cash_libre)} (100%)", x=0.5, y=0.5, font=dict(size=14, color="#8b949e"), showarrow=False)
                    fig_pie.update_layout(template="plotly_dark", height=shared_chart_height, paper_bgcolor="rgba(22,27,34,0.98)", plot_bgcolor="rgba(22,27,34,0.98)")
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
            alert_dte = config.ALERT_DTE_THRESHOLD
            for s in summaries:
                dte = calculate_dte(s.get("expiration_date"))
                if dte > 0 and dte < alert_dte:
                    st.markdown(f'<div class="alert-danger">⚠️ Expiración cercana: {s["ticker"]} — {dte} DTE</div>', unsafe_allow_html=True)

            # --- Línea de vencimientos (60 días: 0-3, 4-7, 8-14, 15+d); solo opciones (CSP/CC), no Propias ---
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
            # Posiciones % del ancho de la barra para centrar la rueda en cada segmento (0-3d, 4-7d, 8-14d, 15+d)
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
            # Tabla: Fecha inicio, Fecha exp., Contratos + Activo, Estrategia, Precio MKT, Strike, Prima, BE, Diagnostico, Retorno (%), Anualizado, POP
            st.caption("➕ Añade posiciones desde el panel **Añadir posición** (arriba). Para ver **Gráfica de riesgo y editar**: elige la posición en el desplegable de abajo y pulsa **Ver Gráfica de riesgo y editar**. Orden: en riesgo primero.")
            table_cols = ["Activo", "Estrategia", "Contratos", "Acciones libres", "Fecha inicio", "Fecha exp.", "Días posición", "Precio MKT", "Strike", "Prima recibida", "Breakeven", "Diagnostico", "Retorno", "Anualizado", "POP"]
            df_show = df_dash[[c for c in table_cols if c in df_dash.columns]].copy()
            # Asegurar columnas numéricas para PyArrow (evitar ArrowInvalid al convertir '-' a int64)
            if "Días posición" in df_show.columns:
                df_show["Días posición"] = pd.to_numeric(df_show["Días posición"], errors="coerce").fillna(0).astype(int)
            if "Contratos" in df_show.columns:
                df_show["Contratos"] = pd.to_numeric(df_show["Contratos"], errors="coerce").fillna(0).astype(int)
            if "Acciones libres" in df_show.columns:
                df_show["Acciones libres"] = pd.to_numeric(df_show["Acciones libres"], errors="coerce").fillna(0).astype(int)
            def to_2dec(x):
                if x is None: return "—"
                if isinstance(x, (int, float)): return fmt2(x)
                return str(x)
            def to_pct(x):
                if x is None: return "—"
                if isinstance(x, (int, float)): return f"{fmt2(x)}%"
                return str(x)
            for col in ["Precio MKT", "Strike", "Prima recibida", "Breakeven"]:
                if col in df_show.columns:
                    df_show[col] = df_show[col].apply(to_2dec)
            for col in ["Retorno", "Anualizado"]:
                if col in df_show.columns:
                    df_show[col] = df_show[col].apply(to_pct)
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
            dash_rows = None
            row_options = list(range(len(df_dash)))
            prev_sel = st.session_state.get("main_dashboard_selected_row_index")
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
                    key="main_dashboard_position_selector",
                )
            with col_btn:
                st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)
                ver_detalle = st.button("Ver Gráfica de riesgo y editar", type="primary", key="main_dashboard_ver_detalle")

            if ver_detalle and chosen_row >= 0:
                st.session_state["main_dashboard_selected_row_index"] = chosen_row
                st.rerun()
            sel_idx = st.session_state.get("main_dashboard_selected_row_index")
            if sel_idx is None or sel_idx < 0 or sel_idx >= len(df_dash):
                sel_idx = None

            if sel_idx is not None and 0 <= sel_idx < len(df_dash):
                if st.button("← Cerrar detalle", key="main_dashboard_cerrar_detalle"):
                    st.session_state["main_dashboard_selected_row_index"] = None
                    st.rerun()
                sel_data = df_dash.iloc[sel_idx]
                ticker = sel_data["Activo"]
                estrategia = str(sel_data.get("Estrategia") or "CSP")
                trades_ticker = [t for t in trades_open if t["ticker"] == ticker]
                be = safe_float(sel_data.get("BE"))
                strike = safe_float(sel_data.get("Strike") or sel_data.get("STRIKE"))
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
                roi_actual = safe_float(sel_data.get("Retorno"))
                diagnostico = str(sel_data.get("Diagnostico") or "OK")
                is_put = "CSP" in estrategia or "PUT" in estrategia.upper()

                st.markdown("---")
                st.markdown("### Herramientas de detalle")

                # ========== DIVIDENDOS DEL TICKER ==========
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
                # ========== GESTIONAR POSICIÓN (historial de la campaña: apertura + rolls) ==========
                st.markdown('<div class="section-title">Gestionar posición (historial de la campaña)</div>', unsafe_allow_html=True)
                st.caption(f"Todos los pasos de **{ticker}** (apertura + rolls). Cada roll conserva el registro anterior.")
                all_trades_historial = sorted(get_trades_by_account(account_id, ticker=ticker), key=lambda x: (x.get("trade_date") or "", x.get("trade_id") or 0))
                if all_trades_historial:
                    trade_options = [(t["trade_id"], f"{str(t.get('trade_date', ''))[:10]} | {t.get('strategy_type', '')} | Strike ${fmt2(t.get('strike'))} | Exp {str(t.get('expiration_date') or '')[:10]} | {t.get('status', '')}") for t in all_trades_historial]
                    try:
                        prev_idx = int(st.session_state.get("sel_trade_gest", 0))
                    except (TypeError, ValueError):
                        prev_idx = 0
                    prev_idx = max(0, min(prev_idx, len(trade_options) - 1)) if trade_options else 0
                    selected_id_highlight = trade_options[prev_idx][0] if prev_idx < len(trade_options) else None
                    rows_html = []
                    for t in all_trades_historial:
                        fd = str(t.get("trade_date") or "")[:10]
                        ed = str(t.get("expiration_date") or "")[:10]
                        row_class = ' class="selected"' if t["trade_id"] == selected_id_highlight else ''
                        comm = (str(t.get("comment") or ""))[:40]
                        comm_esc = html_module.escape(comm)
                        strat_esc = html_module.escape(str(t.get("strategy_type") or "—"))
                        status_esc = html_module.escape(str(t.get("status") or "—"))
                        rows_html.append(
                            f'<tr{row_class}>'
                            f'<td class="date">{fd}</td>'
                            f'<td>{strat_esc}</td>'
                            f'<td class="num">${fmt2(t.get("strike"))}</td>'
                            f'<td class="num">${fmt2(t.get("price"))}</td>'
                            f'<td class="date">{ed}</td>'
                            f'<td>{status_esc}</td>'
                            f'<td>{comm_esc}</td>'
                            f'</tr>'
                        )
                    table_body = "".join(rows_html)
                    st.markdown(
                        f'<div class="gest-table-wrap">'
                        f'<table class="gest-table">'
                        f'<thead><tr><th>Fecha</th><th>Estrategia</th><th>Strike</th><th>Prima</th><th>Expiración</th><th>Estado</th><th>Comentario</th></tr></thead>'
                        f'<tbody>{table_body}</tbody>'
                        f'</table></div>',
                        unsafe_allow_html=True,
                    )
                    sel_trade_idx = st.selectbox("Seleccionar trade para editar o borrar", range(len(trade_options)), format_func=lambda i: trade_options[i][1], key="sel_trade_gest")
                    selected_trade_id = trade_options[sel_trade_idx][0]
                    tr = next(t for t in all_trades_historial if t["trade_id"] == selected_trade_id)
                    is_open_trade = (tr.get("status") or "").upper() == "OPEN"
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
                            if st.form_submit_button("Guardar cambios"):
                                if is_stock:
                                    if edit_quantity < 1:
                                        st.error("La cantidad debe ser al menos 1.")
                                    elif not edit_price or edit_price <= 0:
                                        st.error("El precio por acción debe ser mayor que 0.")
                                    else:
                                        db.update_trade(selected_trade_id, account_id, price=round2(edit_price), quantity=edit_quantity, trade_date=edit_trade_date.isoformat(), comment=edit_comment or None)
                                        st.success("Cambios guardados.")
                                        st.rerun()
                                else:
                                    db.update_trade(selected_trade_id, account_id, price=round2(edit_price), strike=round2(edit_strike), expiration_date=edit_exp.isoformat(), trade_date=edit_trade_date_opt.isoformat(), comment=edit_comment or None)
                                    st.success("Cambios guardados.")
                                    st.rerun()
                        with col_del:
                            if st.form_submit_button("Borrar este trade"):
                                conn = db.get_conn()
                                conn.execute("DELETE FROM Trade WHERE trade_id = ?", (selected_trade_id,))
                                conn.commit()
                                conn.close()
                                st.success("Trade borrado.")
                                st.rerun()
                        with col_close:
                            if is_open_trade and st.form_submit_button("Cerrar posición"):
                                close_trade(selected_trade_id, account_id, date.today().isoformat())
                                st.success("Posición cerrada. Para un roll-over, añade ahora la nueva CSP/CC en el panel lateral.")
                                st.rerun()
                            elif not is_open_trade:
                                st.caption("(Ya cerrado)")

                st.markdown("---")
                st.markdown("### Análisis del riesgo (medidor)")

                def pnl_at_price(price_val):
                    if is_put:
                        return prems - (max(0, (strike or 0) - price_val) * 100 * contracts)
                    return prems - (max(0, price_val - (strike or 0)) * 100 * contracts)
                pnl_actual = pnl_at_price(mkt)
                estado_texto = "Ganando" if pnl_actual >= 0 else "Perdiendo"
                max_ganancia = prems
                max_perdida_put = (prems - (strike or 0) * 100 * contracts) if is_put and strike else None
                max_perdida_label = f"${fmt2(max_perdida_put)}" if is_put and max_perdida_put is not None else "Ilimitado"

                hero_class = "win" if pnl_actual >= 0 else "loss"
                st.markdown(f'<div class="rad-hero {hero_class}">P&L actual: ${fmt2(pnl_actual)} — {estado_texto}</div>', unsafe_allow_html=True)

                st.markdown('<div class="rad-card">', unsafe_allow_html=True)
                st.markdown(f"**{ticker} ({estrategia}) · {contracts} contrato(s)**")

                from app.position_chart_utils import risk_analysis_score, build_gauge_price_axis, build_copyable_summary_position
                health_main = risk_analysis_score(pnl_actual, mkt, be, is_put, dte, 0, True)
                status_main = "Favorable" if health_main > 66 else ("Evaluar" if health_main > 33 else "Desfavorable")
                fig_gauge_main = build_gauge_price_axis(
                    strike or 0, be, mkt, dte, status_main,
                    title="Análisis del riesgo",
                    is_put=is_put,
                )
                st.plotly_chart(fig_gauge_main, use_container_width=True)

                st.markdown(f"""
                <div class="rad-metrics rad-metrics-grid">
                    <div class="rad-metric"><span class="k">Cumplimiento</span><span class="v">{health_main}%</span></div>
                    <div class="rad-metric"><span class="k">Precio (actual)</span><span class="v">${fmt2(mkt)}</span></div>
                    <div class="rad-metric"><span class="k">Strike (ejercicio)</span><span class="v">${fmt2(strike)}</span></div>
                    <div class="rad-metric"><span class="k">BE (breakeven)</span><span class="v">${fmt2(be)}</span></div>
                    <div class="rad-metric"><span class="k">DTE (días a venc.)</span><span class="v">{dte} días</span></div>
                    <div class="rad-metric"><span class="k">P&L actual ($)</span><span class="v">${fmt2(pnl_actual)}</span></div>
                    <div class="rad-metric"><span class="k">Max ganancia ($)</span><span class="v" style="color:#3fb950">${fmt2(max_ganancia)}</span></div>
                    <div class="rad-metric"><span class="k">Max pérdida ($)</span><span class="v" style="color:#f85149">{max_perdida_label}</span></div>
                    <div class="rad-metric {'ok' if diagnostico == 'OK' else 'risk'}"><span class="k">Estado</span><span class="v">{estado_texto} · {diagnostico}</span></div>
                </div>
                """, unsafe_allow_html=True)
                with st.expander("📋 Copiar / Compartir resumen de la posición", expanded=False):
                    copy_text_main = build_copyable_summary_position(ticker, estrategia, contracts, strike or 0, be, mkt, prems, dte, pnl_actual, max_ganancia, max_perdida_label, estado_texto, diagnostico)
                    st.text_area("Resumen (selecciona y copia)", value=copy_text_main, height=160, key="copy_main_pos", disabled=True, label_visibility="collapsed")
                    st.caption("Selecciona todo el texto y cópialo para compartir (móvil: mantén pulsado).")
                st.markdown('</div>', unsafe_allow_html=True)

with tab_report:
    st.markdown('<div class="report-hero"><span class="report-hero-icon">📋</span> Bitácora y reportes</div>', unsafe_allow_html=True)
    st.markdown('<div class="dashboard-card"><h3>Reportes</h3>', unsafe_allow_html=True)
    if not account_id:
        st.info("Selecciona o crea una cuenta para ver reportes.")
    else:
        st.caption("Elige un **rango de fechas** (por fecha de apertura del trade). Los reportes son flexibles para juntar con otras hojas y hacer operaciones.")
        r1, r2 = st.columns([1, 1])
        with r1:
            date_from = st.date_input("Desde", value=date.today().replace(month=1, day=1), key="report_date_from")
        with r2:
            date_to = st.date_input("Hasta", value=date.today(), key="report_date_to")
        date_from_s = date_from.isoformat()
        date_to_s = date_to.isoformat()
        account_name = acc_data.get("name", "")

        # Filtros adicionales para la bitácora
        all_trades_for_filters = get_trades_for_report(account_id, "1900-01-01", "2100-12-31")
        tickers_for_filter = sorted({t["ticker"] for t in all_trades_for_filters}) if all_trades_for_filters else []
        col_f1, col_f2, col_f3 = st.columns([1, 1, 1])
        with col_f1:
            ticker_filter = st.selectbox(
                "Ticker (opcional)",
                options=[""] + tickers_for_filter,
                format_func=lambda x: x if x else "— Todos —",
                key="report_ticker_filter",
            )
        with col_f2:
            strategy_filter = st.selectbox(
                "Estrategia (opcional)",
                options=["", "CSP", "CC", "STOCK", "ASSIGNMENT"],
                format_func=lambda x: x if x else "— Todas —",
                key="report_strategy_filter",
            )
        with col_f3:
            status_filter = st.selectbox(
                "Estado (opcional)",
                options=["", "OPEN", "CLOSED"],
                format_func=lambda x: x if x else "— Ambos —",
                key="report_status_filter",
            )

        # Vista previa de trades en el rango con filtros
        report_trades = get_trades_for_report(
            account_id,
            date_from_s,
            date_to_s,
            ticker=ticker_filter or None,
            strategy=strategy_filter or None,
            status=status_filter or None,
        )
        st.markdown("**Vista previa** — trades en el rango / filtros aplicados")
        if report_trades:
            prev_df = pd.DataFrame(report_trades)
            prev_df = prev_df.rename(columns={
                "trade_date": "Fecha", "ticker": "Ticker", "strategy_type": "Estrategia",
                "quantity": "Cant.", "price": "Prima", "strike": "Strike",
                "expiration_date": "Expiración", "status": "Estado", "closed_date": "Cierre", "comment": "Comentario",
                "campaign_root_id": "Campaña_id", "campaign_start_date": "Inicio_campaña",
            })
            cols_show = [c for c in ["Fecha", "Ticker", "Estrategia", "Cant.", "Prima", "Strike", "Expiración", "Estado"] if c in prev_df.columns]
            st.dataframe(prev_df[cols_show] if cols_show else prev_df, use_container_width=True, height=220)
            st.caption(f"{len(report_trades)} trade(s) en el rango.")
        else:
            st.info("No hay trades en este rango. Ajusta las fechas o añade posiciones.")
            st.caption("0 trades")

        st.markdown("---")
        st.markdown("**Tax Efficiency & rendimiento del capital** (trades cerrados en el rango)")
        tax = tax_efficiency_summary(account_id, date_from_s, date_to_s)
        col_tx1, col_tx2, col_tx3 = st.columns(3)
        with col_tx1:
            st.metric("Total realizado", f"${fmt2(tax['total_realized_gain_loss'])}")
        with col_tx2:
            st.metric("Rendimiento sobre capital", f"{fmt2(tax['realized_pct_of_capital'])}%", help="Ganancia/pérdida realizada / capital de la cuenta en %")
        with col_tx3:
            st.metric("Rendimiento anualizado", f"{fmt2(tax['realized_ann_pct'])}%", help="Aproximación anualizada en base al rango de fechas elegido")

        # Desglose por ticker y por estrategia para la bitácora
        col_tx4, col_tx5 = st.columns(2)
        with col_tx4:
            if tax.get("by_ticker"):
                df_tk = pd.DataFrame(
                    [{"Ticker": k, "Realizado": v} for k, v in tax["by_ticker"].items()]
                )
                df_tk["Realizado"] = df_tk["Realizado"].apply(fmt2)
                st.caption("Por ticker (USD realizados)")
                st.dataframe(df_tk, use_container_width=True, hide_index=True, height=180)
            else:
                st.caption("Sin trades cerrados por ticker en este rango.")
        with col_tx5:
            if tax.get("by_strategy"):
                df_st = pd.DataFrame(
                    [
                        {
                            "Estrategia": k,
                            "Realizado": v,
                            "Trades": tax.get("closed_trades_by_strategy", {}).get(k, 0),
                        }
                        for k, v in tax["by_strategy"].items()
                    ]
                )
                df_st["Realizado"] = df_st["Realizado"].apply(fmt2)
                st.caption("Por estrategia (USD realizados / nº trades)")
                st.dataframe(df_st, use_container_width=True, hide_index=True, height=180)
            else:
                st.caption("Sin trades cerrados por estrategia en este rango.")

        st.markdown("---")
        st.markdown("**Exportar bitácora** — hojas listas para combinar")
        col1, col2, col3 = st.columns(3)
        with col1:
            csv_data = export_trades_csv(account_id, date_from_s, date_to_s, account_name)
            if csv_data:
                st.download_button("📥 Descargar CSV", csv_data, file_name=f"alphawheel_trades_{date_from_s}_{date_to_s}.csv", mime="text/csv")
            else:
                st.caption("Sin datos para CSV")
        with col2:
            excel_bytes = export_trades_excel(account_id, date_from_s, date_to_s, account_name)
            if excel_bytes:
                st.download_button("📥 Descargar Excel", excel_bytes, file_name=f"alphawheel_bitacora_{date_from_s}_{date_to_s}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                st.caption("Hojas: Trades, Resumen_por_ticker, Resumen_por_estrategia")
            else:
                st.caption("Sin datos para Excel" if not csv_data else "Instala openpyxl: pip install openpyxl")
        with col3:
            pdf_bytes = export_trades_pdf(account_id, date_from_s, date_to_s, account_name)
            if pdf_bytes:
                st.download_button("📥 Descargar PDF", pdf_bytes, file_name=f"alphawheel_bitacora_{date_from_s}_{date_to_s}.pdf", mime="application/pdf")
            else:
                st.caption("Sin datos para PDF")
    st.markdown('</div>', unsafe_allow_html=True)  # dashboard-card Reportes

with tab_settings:
    st.markdown('<div class="dashboard-card"><h3>Mi cuenta</h3>', unsafe_allow_html=True)
    st.caption("Aquí configuras el **token de Tradier** (para precios en tiempo real) y los **datos de la cuenta** (capital, meta, asignación).")
    if account_id:
        acc = get_account_by_id(account_id, user_id)
    else:
        acc = None
        st.info("Crea una cuenta abajo para empezar; luego podrás poner tu token y parámetros aquí.")
    if acc:
        st.markdown("---")
        st.markdown("**🔑 Token Tradier (para tener la data)**")
        st.caption("Obtén tu token en tradier.com → API Access. Si el navegador pregunta si guardar contraseña, puedes decir que no; el token se guarda en la app.")
        with st.form("form_mi_cuenta_guardar"):
            new_token = st.text_input("Token de acceso (Tradier)", value=(acc.get("access_token") or ""), type="password", placeholder="Pega tu token aquí", key="new_token_mi_cuenta")
            env = st.selectbox("Entorno", ["sandbox (pruebas)", "prod (real)"], index=0 if (acc.get("environment") or "sandbox") == "sandbox" else 1, key="env_tradier")
            env_val = "sandbox" if "sandbox" in (env or "") else "prod"
            st.markdown("**📊 Datos de la cuenta (actualizar)**")
            st.caption("Capital total de la cuenta, meta anual de retorno y máximo % por ticker.")
            cap = st.number_input("Capital ($)", value=float(acc.get("cap_total") or 100000), step=1000.0, format="%.2f", key="cap_mi_cuenta")
            target = st.number_input("Meta anual (%)", value=float(acc.get("target_ann") or 20), step=0.5, format="%.2f", key="target_mi_cuenta")
            max_ticker = st.number_input("Máx. por ticker (%)", value=float(acc.get("max_per_ticker") or 10), step=0.5, format="%.2f", key="max_ticker_mi_cuenta")
            submitted = st.form_submit_button("Guardar token y datos")
        if submitted:
            try:
                db.update_account_token(account_id, user_id, new_token or "", env_val)
                db.update_account_config(account_id, user_id, cap, target, max_ticker)
                st.success("Guardado. Los datos de la cuenta y el token se han actualizado.")
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo guardar: {e}")
        # Borrar cuenta: solo si hay más de una
        accounts_mi = get_accounts_by_user(user_id)
        if len(accounts_mi) > 1:
            st.markdown("---")
            if st.button("🗑️ Borrar esta cuenta", type="secondary", key="delete_acc_btn"):
                if delete_account(account_id, user_id):
                    if st.session_state.get("current_account_id") == account_id:
                        remaining = [a for a in accounts_mi if a["account_id"] != account_id]
                        st.session_state["current_account_id"] = remaining[0]["account_id"] if remaining else None
                    st.success("Cuenta borrada.")
                    st.rerun()
    st.markdown("---")
    st.subheader("Nueva cuenta")
    new_name = st.text_input("Nombre cuenta (ej. Estrategia Rueda, IRA Principal)", key="new_acc_name")
    if st.button("Crear cuenta"):
        if new_name:
            acc_id = db.create_account(user_id, new_name.strip())
            if acc_id:
                if "new_acc_name" in st.session_state:
                    del st.session_state["new_acc_name"]
                st.success("Cuenta creada. Selecciónala arriba.")
                st.rerun()
            else:
                st.error("Ya existe una cuenta con ese nombre. Elige otro.")
        else:
            st.warning("Escribe un nombre para la cuenta.")
    st.markdown('</div>', unsafe_allow_html=True)  # dashboard-card Mi cuenta