# AlphaWheel Pro - Configuración central
import os

# Base de datos (SQLite por defecto; cambiar a PostgreSQL en producción)
DB_PATH = os.environ.get("ALPHAWHEEL_DB_PATH", "trading_app.db")

# Restricción por email: solo estos usuarios pueden acceder (login y registro).
# Variable de entorno ALPHAWHEEL_ALLOWED_EMAILS = emails separados por coma (ej. user1@mail.com,user2@mail.com).
# Si está vacía o no definida, se permiten todos los emails (uso local / desarrollo).
ALLOWED_EMAILS_RAW = os.environ.get("ALPHAWHEEL_ALLOWED_EMAILS", "").strip()
ALLOWED_EMAILS = frozenset(e.strip().lower() for e in ALLOWED_EMAILS_RAW.split(",") if e.strip()) if ALLOWED_EMAILS_RAW else None

# Regla de precisión: máximo 2 decimales en todos los valores mostrados
PRECISION_DECIMALS = 2

# Alertas: DTE por debajo de este valor se considera "expiración cercana"
ALERT_DTE_THRESHOLD = 5
