# AlphaWheel Pro - Configuración central
import os
from pathlib import Path

# Base de datos: por defecto en la raíz del proyecto para que persista entre reinicios y actualizaciones.
# Para no perder usuarios ni datos en despliegues (Streamlit Cloud, etc.), usar PostgreSQL:
#   ALPHAWHEEL_DATABASE_URL = "postgresql://user:pass@host:5432/dbname"
# Si DATABASE_URL está definido, se usa PostgreSQL; si no, se usa SQLite en DB_PATH.
_root = Path(__file__).resolve().parent
DB_PATH = os.environ.get("ALPHAWHEEL_DB_PATH", str(_root / "trading_app.db"))


def _get_database_url():
    url = os.environ.get("ALPHAWHEEL_DATABASE_URL", "").strip() or os.environ.get("DATABASE_URL", "").strip()
    if url:
        return url
    try:
        import streamlit as st
        return (st.secrets.get("ALPHAWHEEL_DATABASE_URL") or st.secrets.get("DATABASE_URL") or "").strip()
    except Exception:
        return ""


DATABASE_URL = _get_database_url()

# Restricción por email: solo estos usuarios pueden acceder (login y registro).
# Variable de entorno o Secrets (Streamlit Cloud): ALPHAWHEEL_ALLOWED_EMAILS = emails separados por coma.
# Si está vacía o no definida, se permiten todos los emails (uso local / desarrollo).
def _get_allowed_emails_raw():
    raw = os.environ.get("ALPHAWHEEL_ALLOWED_EMAILS", "").strip()
    if raw:
        return raw
    try:
        import streamlit as st
        val = st.secrets.get("ALPHAWHEEL_ALLOWED_EMAILS")
        return (val if isinstance(val, str) else "").strip()
    except Exception:
        return ""


ALLOWED_EMAILS_RAW = _get_allowed_emails_raw()
ALLOWED_EMAILS = frozenset(e.strip().lower() for e in ALLOWED_EMAILS_RAW.split(",") if e.strip()) if ALLOWED_EMAILS_RAW else None

# Regla de precisión: máximo 2 decimales en todos los valores mostrados
PRECISION_DECIMALS = 2

# Alertas: DTE por debajo de este valor se considera "expiración cercana"
ALERT_DTE_THRESHOLD = 5
