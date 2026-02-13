# AlphaWheel Pro - Estilos globales (diseño profesional, listo para GitHub)

PROFESSIONAL_CSS = """
<style>
    /* Base: tema oscuro profesional */
    .stApp {
        background: linear-gradient(180deg, #0d1117 0%, #161b22 50%, #0d1117 100%);
        color: #e6edf3;
        min-height: 100vh;
    }
    /* Métricas */
    [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', 'Consolas', 'SF Mono', monospace !important;
        color: #58a6ff !important;
        font-size: 1.35rem;
        font-weight: 600;
        letter-spacing: 0.02em;
    }
    [data-testid="stMetricLabel"] {
        color: #c9d1d9 !important;
        font-size: 0.8rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    /* Contenedores */
    .status-container {
        background: #161b22;
        padding: 1.25rem 1.5rem;
        border-radius: 12px;
        border: 1px solid #21262d;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 14px rgba(0,0,0,0.25);
    }
    .capital-ring {
        background: #161b22;
        border: 1px solid #21262d;
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 14px rgba(0,0,0,0.25);
    }
    .card-panel, .rad-card {
        background: #161b22;
        border: 1px solid #21262d;
        border-radius: 12px;
        padding: 1.25rem;
        margin: 1rem 0;
        box-shadow: 0 4px 14px rgba(0,0,0,0.25);
        transition: box-shadow 0.2s ease;
    }
    .card-panel:hover, .rad-card:hover {
        box-shadow: 0 6px 20px rgba(88,166,255,0.08);
    }
    .card-panel h3, .rad-card h3 {
        color: #58a6ff;
        font-size: 1rem;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid #21262d;
    }
    /* Barras de progreso */
    [data-testid="stProgressBar"] { background: #21262d !important; border-radius: 8px; }
    [data-testid="stProgressBar"] > div {
        background: linear-gradient(90deg, #238636, #58a6ff) !important;
        min-width: 2% !important;
        border-radius: 8px;
    }
    .prog-annual-wrap { margin-bottom: 10px; }
    .prog-annual-bar { height: 10px; background: #21262d; border-radius: 8px; overflow: hidden; }
    .prog-annual-fill { height: 100%; background: linear-gradient(90deg, #238636, #58a6ff); border-radius: 8px; }
    .prog-exp-bar { height: 12px; border-radius: 8px; display: flex; overflow: hidden; }
    .prog-exp-seg { height: 100%; min-width: 2px; }
    .prog-exp-seg.red { background: #c85a54; }
    .prog-exp-seg.yellow { background: #c9b84a; }
    .prog-exp-seg.green { background: #4ab85a; }
    .prog-exp-seg.orange { background: #d29922; }
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
    .timeline-bar-wrap { height: 28px; border-radius: 14px; overflow: hidden; background: #21262d; margin: 0.5rem 0 1rem 0; }
    .timeline-bar-fill { height: 100%; border-radius: 14px; background: linear-gradient(90deg, #238636, #58a6ff); transition: width 0.2s ease; }
    .expiration-timeline { background: #161b22; border: 1px solid #21262d; border-radius: 14px; padding: 1.25rem 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 4px 14px rgba(0,0,0,0.25); }
    .expiration-timeline h3 { color: #e6edf3; font-size: 1.1rem; margin: 0 0 0.5rem 0; font-weight: 600; }
    .expiration-timeline .next-days { color: #8b949e; font-size: 0.85rem; }
    .timeline-60-bar { height: 28px; border-radius: 14px; display: flex; overflow: hidden; margin: 0.75rem 0 0.25rem 0; background: #0d1117; }
    .timeline-60-seg { height: 100%; min-width: 4px; }
    .timeline-60-seg.s0 { background: #c85a54; width: 5%; }
    .timeline-60-seg.s1 { background: #d29922; width: 6.67%; }
    .timeline-60-seg.s2 { background: #c9b84a; width: 11.67%; }
    .timeline-60-seg.s3 { background: #4ab85a; width: 76.66%; }
    .timeline-60-marker { margin-top: -36px; margin-bottom: 8px; display: flex; justify-content: center; }
    .timeline-60-marker .bubble { background: #161b22; border: 2px solid #e3b341; border-radius: 50%; width: 48px; height: 48px; display: flex; flex-direction: column; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 700; color: #e6edf3; box-shadow: 0 2px 8px rgba(0,0,0,0.4); margin-left: var(--marker-pct, 50%); transform: translateX(-50%); }
    .timeline-60-marker .bubble .n { font-size: 1rem; }
    .timeline-60-labels { display: flex; justify-content: space-between; font-size: 0.7rem; color: #8b949e; margin-bottom: 0.5rem; }
    .timeline-legend { display: flex; gap: 1rem; flex-wrap: wrap; margin-top: 0.75rem; font-size: 0.8rem; color: #8b949e; }
    .timeline-legend span { display: flex; align-items: center; gap: 0.35rem; }
    .timeline-legend .dot { width: 8px; height: 8px; border-radius: 50%; }
    .timeline-legend .dot.red { background: #c85a54; }
    .timeline-legend .dot.orange { background: #d29922; }
    .timeline-legend .dot.yellow { background: #c9b84a; }
    .timeline-legend .dot.green { background: #4ab85a; }
    /* Dashboard cards unificadas (mismo estilo que Position Performance / Expiration Timeline) */
    .dashboard-card { background: #161b22; border: 1px solid #21262d; border-radius: 14px; padding: 1.25rem 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 4px 14px rgba(0,0,0,0.25); }
    .dashboard-card.resumen-cuenta-card { border: 2px solid rgba(63,185,80,0.5); }
    /* Tarjetas de métricas del screener: marco verde como en el dashboard */
    .metric-card {
        background: #161b22;
        border: 2px solid rgba(63,185,80,0.5);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.5rem;
        color: #e6edf3;
        font-size: 0.95rem;
    }
    .metric-card h3 { color: #58a6ff; font-size: 1.25rem; margin: 0.35rem 0; font-weight: 600; }
    .metric-card b { color: #c9d1d9; font-weight: 600; }
    .dashboard-card h3 { color: #e6edf3; font-size: 1.1rem; margin: 0 0 0.75rem 0; font-weight: 600; }
    .dashboard-card .card-sub { color: #8b949e; font-size: 0.85rem; margin-bottom: 0.75rem; }
    .capital-allocation-bar { height: 28px; border-radius: 14px; display: flex; overflow: hidden; margin: 0.75rem 0 0.5rem 0; background: #0d1117; }
    .capital-allocation-bar .capital-segments { display: flex; width: 100%; height: 100%; }
    .capital-allocation-bar .capital-seg { display: block; height: 100%; min-width: 2px; font-size: 0.7rem; color: #0d1117; text-align: center; line-height: 28px; white-space: nowrap; overflow: hidden; }
    .capital-allocation-bar .seg { height: 100%; min-width: 2px; transition: opacity 0.2s; }
    .capital-allocation-bar .seg:hover { opacity: 0.9; }
    .capital-legend { display: flex; gap: 1rem; flex-wrap: wrap; margin-top: 0.5rem; font-size: 0.8rem; color: #8b949e; }
    .capital-legend span, .capital-legend .capital-legend-item { display: flex; align-items: center; gap: 0.35rem; margin-right: 0.5rem; }
    .capital-legend .sq, .capital-legend .swatch { width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0; }
    .summary-strip { background: #0d1117; border-radius: 10px; padding: 0.75rem 1rem; margin-bottom: 1rem; font-size: 0.95rem; color: #e6edf3; font-family: 'JetBrains Mono', monospace; }
    .summary-strip strong { color: #58a6ff; }
    /* Tablas */
    .gest-table-wrap {
        background: #161b22;
        border: 1px solid #21262d;
        border-radius: 14px;
        overflow: hidden;
        margin: 1.5rem 0 2rem 0;
        box-shadow: 0 6px 20px rgba(0,0,0,0.3);
    }
    .gest-table { width: 100%; border-collapse: collapse; font-size: 0.95rem; }
    .gest-table thead {
        background: linear-gradient(180deg, #21262d 0%, #30363d 100%);
        color: #e6edf3;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-size: 0.8rem;
    }
    .gest-table th { padding: 16px 20px; text-align: left; border-bottom: 2px solid #58a6ff; }
    .gest-table td { padding: 14px 20px; border-bottom: 1px solid #21262d; color: #c9d1d9; }
    .gest-table tbody tr:hover { background: rgba(88,166,255,0.06); }
    .gest-table .num { font-family: 'JetBrains Mono', monospace; color: #58a6ff; font-weight: 500; }
    .gest-table .date { font-family: 'JetBrains Mono', monospace; color: #8b949e; }
    .gest-table tbody tr.selected { background: rgba(88,166,255,0.18) !important; border-left: 4px solid #58a6ff; }
    .section-title { font-size: 1.1rem; font-weight: 600; color: #58a6ff; margin-bottom: 0.5rem; padding-bottom: 0.5rem; border-bottom: 1px solid #21262d; }
    /* Radiografía */
    .rad-hero {
        padding: 1.25rem 1.5rem;
        border-radius: 12px;
        margin-bottom: 1.25rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.15rem;
        font-weight: 600;
        text-align: center;
    }
    .rad-hero.win {
        background: linear-gradient(135deg, rgba(63,185,80,0.25) 0%, rgba(63,185,80,0.08) 100%);
        border: 1px solid rgba(63,185,80,0.5);
        color: #3fb950;
    }
    .rad-hero.loss {
        background: linear-gradient(135deg, rgba(248,81,73,0.25) 0%, rgba(248,81,73,0.08) 100%);
        border: 1px solid rgba(248,81,73,0.5);
        color: #f85149;
    }
    .rad-metrics { display: flex; flex-wrap: wrap; gap: 1.5rem; padding: 1rem 1.25rem; background: #0d1117; border-radius: 10px; margin-top: 1rem; font-family: 'JetBrains Mono', monospace; }
    .rad-metric { min-width: 0; }
    .rad-metric .k { font-size: 0.75rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.05em; }
    .rad-metric .v { font-size: 1.1rem; font-weight: 600; color: #e6edf3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 4ch; }
    .rad-metric.ok .v { color: #3fb950; }
    .rad-metric.risk .v { color: #f85149; }
    .rad-metrics-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 1rem; }
    /* Reportes */
    .report-hero {
        background: linear-gradient(135deg, #1a2332 0%, #0d1117 50%);
        border: 1px solid #30363d;
        border-radius: 14px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1.5rem;
        font-size: 1.25rem;
        font-weight: 600;
        color: #e6edf3;
        display: flex;
        align-items: center;
        gap: 0.75rem;
        box-shadow: 0 4px 16px rgba(0,0,0,0.3);
    }
    .report-hero-icon { font-size: 1.5rem; filter: drop-shadow(0 0 8px rgba(88,166,255,0.4)); }
    /* Alertas */
    .alert-danger {
        background: rgba(248,81,73,0.12);
        border: 1px solid #f85149;
        border-radius: 8px;
        padding: 10px;
        margin: 8px 0;
        color: #ff7b72;
    }
    /* Sidebar: fondo un poco más claro y texto muy legible */
    [data-testid="stSidebar"] > div:first-child {
        background: linear-gradient(180deg, #1c2128 0%, #22272e 50%, #1c2128 100%);
        border-right: 1px solid #373e47;
    }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] [data-testid="stMarkdown"] {
        color: #f0f6fc !important;
        font-weight: 600;
        font-size: 0.95rem;
    }
    [data-testid="stSidebar"] label span {
        color: #f0f6fc !important;
        font-weight: 600;
    }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
        color: #e6edf3 !important;
        font-weight: 500;
        font-size: 0.9rem;
    }
    [data-testid="stSidebar"] [data-testid="stMarkdown"] h2, [data-testid="stSidebar"] .stMarkdown h2 {
        color: #f0f6fc !important;
        font-weight: 700;
    }
    [data-testid="stSidebar"] input, [data-testid="stSidebar"] [data-testid="stNumberInput"] input {
        color: #e6edf3 !important;
        background: #0d1117 !important;
        font-weight: 500;
    }
    [data-testid="stSidebar"] [data-testid="stMarkdown"] h1:first-of-type {
        background: linear-gradient(90deg, #58a6ff, #79c0ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-weight: 700;
        letter-spacing: 0.02em;
    }
    /* Contraste general: texto y etiquetas en toda la app */
    [data-testid="stSlider"] label, [data-testid="stNumberInput"] label, [data-testid="stTextInput"] label,
    [data-testid="stCheckbox"] label, [data-testid="stSelectbox"] label, [data-testid="stMultiSelect"] label {
        color: #e6edf3 !important;
        font-weight: 500;
    }
    [data-testid="stSlider"] label span, [data-testid="stNumberInput"] label span, [data-testid="stTextInput"] label span,
    [data-testid="stCheckbox"] label span, [data-testid="stSelectbox"] label span {
        color: #e6edf3 !important;
    }
    [data-testid="stCaptionContainer"] {
        color: #c9d1d9 !important;
    }
    .stMarkdown p {
        color: #c9d1d9 !important;
    }
    .stApp > header { background: linear-gradient(90deg, #0d1117 0%, #161b22 100%); border-bottom: 1px solid #21262d; }
    /* Ocultar solo pie de Streamlit; el header debe quedar visible para el menú */
    footer { visibility: hidden !important; }
    div[data-testid="stDataFrame"] { border-radius: 8px; overflow: hidden; border: 1px solid #21262d; }
    /* Login: tarjeta centrada */
    .login-card {
        max-width: 420px;
        margin: 2rem auto;
        padding: 2rem;
        background: #161b22;
        border: 1px solid #21262d;
        border-radius: 16px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.4);
    }
    .login-title { font-size: 1.5rem; font-weight: 700; color: #58a6ff; margin-bottom: 0.5rem; text-align: center; }
    .login-subtitle { color: #8b949e; font-size: 0.9rem; text-align: center; margin-bottom: 1.5rem; }
    .user-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.35rem 0.75rem;
        background: rgba(88,166,255,0.15);
        border: 1px solid rgba(88,166,255,0.3);
        border-radius: 8px;
        font-size: 0.9rem;
        color: #79c0ff;
    }
    /* Pestañas y opciones (Ir a Screener / Mi Cuenta): tono más claro sobre fondo oscuro */
    [data-testid="stTabs"] [data-baseweb="tab-list"] button,
    [data-testid="stTabs"] [role="tab"] {
        color: #e6edf3 !important;
        font-weight: 500;
    }
    [data-testid="stTabs"] [data-baseweb="tab-list"] button:hover,
    [data-testid="stTabs"] [role="tab"]:hover {
        color: #79c0ff !important;
    }
    [data-testid="stRadio"] label,
    [data-testid="stRadio"] label span {
        color: #e6edf3 !important;
    }
    [data-testid="stRadio"] label:hover,
    [data-testid="stRadio"] label:hover span {
        color: #b1d4e0 !important;
    }
</style>
"""
