# AlphaWheel Pro - Acceso a BD con aislamiento por user_id / account_id
# Soporta SQLite (local) y PostgreSQL (nube, para no perder datos en redeploys)
# Paridad web/local: las rutas críticas (login, cuentas, trades, guardar CSP) usan conexión
# directa psycopg2 cuando _is_postgres() para evitar fallos del wrapper en la versión web.
import sqlite3
import os
from pathlib import Path

import config

try:
    import psycopg2
    from psycopg2 import extras as pg_extras
    from psycopg2 import IntegrityError as pg_IntegrityError
except ImportError:
    psycopg2 = None
    pg_extras = None
    pg_IntegrityError = None


def _is_postgres():
    """True si está configurada una URL de PostgreSQL."""
    url = getattr(config, "DATABASE_URL", "") or ""
    return bool(url.startswith("postgresql://") and psycopg2 is not None)


def _schema_path(name="schema.sql"):
    """Ruta al archivo de esquema; prueba varias ubicaciones para Cloud (mount path)."""
    candidates = [
        Path(__file__).resolve().parent / name,
        Path(__file__).resolve().parent.parent / "database" / name,
        Path.cwd() / "database" / name,
        Path.cwd() / name,
    ]
    for p in candidates:
        if p.exists():
            return p
    return Path(__file__).resolve().parent / name


# --- Wrapper para PostgreSQL (misma API que SQLite: ? -> %s, lastrowid vía lastval()) ---
class _PgCursorWrapper:
    def __init__(self, cursor):
        self._cur = cursor
        self._lastrowid = None
        try:
            self._cur.execute("SELECT lastval()")
            row = self._cur.fetchone()
            self._lastrowid = row[0] if row and row[0] else None
        except Exception:
            pass

    @property
    def lastrowid(self):
        return self._lastrowid

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def description(self):
        return getattr(self._cur, "description", None)

    def fetchone(self):
        # Evitar ProgrammingError "no results to fetch": solo fetch si el cursor tiene result set
        if getattr(self._cur, "description", None) is None:
            return None
        row = self._cur.fetchone()
        return dict(row) if row else None

    def fetchall(self):
        if getattr(self._cur, "description", None) is None:
            return []
        return [dict(r) for r in self._cur.fetchall()]


def _pg_quote_user_table(sql: str) -> str:
    """En PostgreSQL la tabla User debe ir entre comillas."""
    for a, b in [
        (" FROM User ", ' FROM "User" '),
        (" INTO User ", ' INTO "User" '),
        (" UPDATE User ", ' UPDATE "User" '),
        ("UPDATE User ", 'UPDATE "User" '),  # inicio de sentencia (sin espacio delante)
        (" DELETE FROM User ", ' DELETE FROM "User" '),
    ]:
        sql = sql.replace(a, b)
    return sql


class _PgConnWrapper:
    def __init__(self, conn):
        self._conn = conn

    @property
    def raw_conn(self):
        """Conexión psycopg2 subyacente (para autocommit en esquema)."""
        return self._conn

    def execute(self, sql, params=None):
        sql = sql.replace("?", "%s")
        sql = _pg_quote_user_table(sql)
        cur = self._conn.cursor(cursor_factory=pg_extras.RealDictCursor)
        try:
            cur.execute(sql, params or ())
            return _PgCursorWrapper(cur)
        except Exception:
            self._conn.rollback()
            raise

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

    def executescript(self, sql):
        for stmt in sql.split(";"):
            stmt = stmt.strip()
            if stmt and not stmt.startswith("--"):
                self.execute(stmt)


def get_conn():
    """Conexión a SQLite o PostgreSQL según config. Misma API: conn.execute(sql, params), cur.lastrowid, cur.fetchone() (dict)."""
    if _is_postgres():
        conn = psycopg2.connect(config.DATABASE_URL)
        conn.autocommit = True  # Evita InFailedSqlTransaction: cada sentencia es su propia transacción
        return _PgConnWrapper(conn)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _run_pg_schema(conn):
    path = _schema_path("schema_pg.sql")
    if not path.exists():
        raise FileNotFoundError(
            f"Esquema PostgreSQL no encontrado: schema_pg.sql. Probadas: {[str(p) for p in [Path(__file__).resolve().parent, Path.cwd() / 'database']]}"
        )
    sql = path.read_text(encoding="utf-8")
    # Quitar líneas que son solo comentarios o vacías, para que el split por ";" no deje el primer CREATE en un bloque que empiece con "--"
    lines = [ln for ln in sql.splitlines() if ln.strip() and not ln.strip().startswith("--")]
    sql_clean = "\n".join(lines)
    # Cada sentencia en su propia transacción para evitar InFailedSqlTransaction si una falla
    raw = getattr(conn, "raw_conn", conn)
    if hasattr(raw, "autocommit"):
        raw.autocommit = True
    try:
        for stmt in sql_clean.split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(stmt)
    finally:
        if hasattr(raw, "autocommit"):
            raw.autocommit = False
    conn.commit()


def init_db():
    """Crea o actualiza el esquema. SQLite: schema.sql + migraciones. PostgreSQL: schema_pg.sql (usuarios y datos persistentes)."""
    if _is_postgres():
        conn = get_conn()
        try:
            _run_pg_schema(conn)
            # Migrar lista antigua a búnker Principal si existe columna screener_watchlist
            try:
                cur = conn.execute(
                    'SELECT user_id, screener_watchlist FROM "User" WHERE screener_watchlist IS NOT NULL AND trim(screener_watchlist) != \'\''
                )
                for row in cur.fetchall():
                    uid = row.get("user_id")
                    wl = (row.get("screener_watchlist") or "") if row else ""
                    if uid is None:
                        continue
                    try:
                        conn.execute(
                            "INSERT INTO UserBunker (user_id, name, tickers_text) VALUES (%s, %s, %s) ON CONFLICT (user_id, name) DO NOTHING",
                            (uid, "Principal", wl),
                        )
                    except Exception:
                        pass
                conn.commit()
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE Trade ADD COLUMN IF NOT EXISTS close_type TEXT")
                conn.execute("ALTER TABLE Trade ADD COLUMN IF NOT EXISTS buyback_debit REAL")
                conn.commit()
            except Exception:
                pass
        finally:
            conn.close()
        return

    schema_path = _schema_path("schema.sql")
    if not schema_path.exists():
        schema_path = Path(__file__).parent / "schema.sql"
    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()
    conn = get_conn()
    try:
        conn.executescript(sql)
        conn.commit()
        try:
            conn.execute("ALTER TABLE User ADD COLUMN password_hash TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE Account ADD COLUMN av_api_key TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE User ADD COLUMN av_api_key TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE User ADD COLUMN screener_watchlist TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE Trade ADD COLUMN close_type TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE Trade ADD COLUMN buyback_debit REAL")
            conn.commit()
        except sqlite3.OperationalError:
            pass
        conn.execute("""
            CREATE TABLE IF NOT EXISTS UserBunker (
                bunker_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                tickers_text TEXT,
                created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                UNIQUE(user_id, name),
                FOREIGN KEY (user_id) REFERENCES User(user_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS CampaignAdjustment (
                account_id INTEGER NOT NULL,
                campaign_root_id INTEGER NOT NULL,
                commissions REAL DEFAULT 0,
                fees REAL DEFAULT 0,
                PRIMARY KEY (account_id, campaign_root_id),
                FOREIGN KEY (account_id) REFERENCES Account(account_id),
                FOREIGN KEY (campaign_root_id) REFERENCES Trade(trade_id)
            )
        """)
        conn.commit()
        try:
            cur = conn.execute(
                "SELECT user_id, screener_watchlist FROM User WHERE screener_watchlist IS NOT NULL AND trim(screener_watchlist) != ''"
            )
            for row in cur.fetchall():
                uid, wl = row[0], (row[1] or "")
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO UserBunker (user_id, name, tickers_text) VALUES (?, 'Principal', ?)",
                        (uid, wl),
                    )
                except Exception:
                    pass
            conn.commit()
        except Exception:
            pass
    finally:
        conn.close()

# --- Usuarios (aislamiento raíz) ---
def ensure_user(email: str, display_name: str = None):
    """Crea usuario si no existe; devuelve user_id."""
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT user_id FROM User WHERE email = ?", (email.strip(),)
        )
        row = cur.fetchone()
        if row:
            return row["user_id"]
        cur = conn.execute(
            "INSERT INTO User (email, display_name) VALUES (?, ?)",
            (email.strip(), display_name or email),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def get_user_by_email(email: str):
    """Obtiene usuario por email (para login)."""
    if _is_postgres():
        # Ruta directa con psycopg2 para evitar ProgrammingError en fetchone con el wrapper
        conn = psycopg2.connect(config.DATABASE_URL)
        try:
            cur = conn.cursor(cursor_factory=pg_extras.RealDictCursor)
            cur.execute(
                'SELECT user_id, email, display_name, password_hash FROM "User" WHERE email = %s',
                (email.strip().lower(),),
            )
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT user_id, email, display_name, password_hash FROM User WHERE email = ?",
            (email.strip().lower(),),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_users():
    """Lista todos los usuarios (para selector en UI)."""
    conn = get_conn()
    try:
        cur = conn.execute("SELECT user_id, email, display_name FROM User ORDER BY email")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def create_user_with_password(email: str, display_name: str, password_hash: str):
    """Crea usuario con contraseña hasheada. Devuelve user_id."""
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO User (email, display_name, password_hash) VALUES (?, ?, ?)",
            (email.strip().lower(), (display_name or email).strip(), password_hash),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_user_password(user_id: int, password_hash: str):
    """Actualiza contraseña del usuario."""
    conn = get_conn()
    try:
        conn.execute("UPDATE User SET password_hash = ? WHERE user_id = ?", (password_hash, user_id))
        conn.commit()
    finally:
        conn.close()


def get_user_screener_settings(user_id: int) -> dict:
    """Devuelve av_api_key y screener_watchlist del usuario (screener es por usuario, no por cuenta)."""
    if not user_id:
        return {"av_api_key": "", "screener_watchlist": ""}
    if _is_postgres():
        conn = psycopg2.connect(config.DATABASE_URL)
        conn.autocommit = True
        try:
            cur = conn.cursor(cursor_factory=pg_extras.RealDictCursor)
            cur.execute('SELECT av_api_key, screener_watchlist FROM "User" WHERE user_id = %s', (user_id,))
            row = cur.fetchone()
            if not row:
                return {"av_api_key": "", "screener_watchlist": ""}
            return {"av_api_key": (row.get("av_api_key") or "").strip(), "screener_watchlist": (row.get("screener_watchlist") or "").strip()}
        except Exception:
            return {"av_api_key": "", "screener_watchlist": ""}
        finally:
            conn.close()
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT av_api_key, screener_watchlist FROM User WHERE user_id = ?",
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            return {"av_api_key": "", "screener_watchlist": ""}
        try:
            av = row["av_api_key"] or ""
            wl = row["screener_watchlist"] or ""
        except (TypeError, KeyError, IndexError):
            av = (row[0] or "") if len(row) > 0 else ""
            wl = (row[1] or "") if len(row) > 1 else ""
        return {"av_api_key": av, "screener_watchlist": wl}
    except Exception:
        return {"av_api_key": "", "screener_watchlist": ""}
    finally:
        conn.close()


def update_user_av_key(user_id: int, av_api_key: str) -> None:
    """Guarda la clave Alpha Vantage del usuario (screener)."""
    if _is_postgres():
        conn = psycopg2.connect(config.DATABASE_URL)
        conn.autocommit = True
        try:
            cur = conn.cursor()
            cur.execute('UPDATE "User" SET av_api_key = %s WHERE user_id = %s', (av_api_key or "", user_id))
        finally:
            conn.close()
        return
    conn = get_conn()
    try:
        conn.execute("UPDATE User SET av_api_key = ? WHERE user_id = ?", (av_api_key or "", user_id))
        conn.commit()
    finally:
        conn.close()


def update_user_screener_watchlist(user_id: int, watchlist: str) -> None:
    """Guarda la lista del búnker del usuario (screener). Obsoleto: usar UserBunker."""
    conn = get_conn()
    try:
        conn.execute("UPDATE User SET screener_watchlist = ? WHERE user_id = ?", (watchlist or "", user_id))
        conn.commit()
    finally:
        conn.close()


# --- Búnkeres por usuario (varios por usuario para búsquedas selectivas) ---
def get_user_bunkers(user_id: int) -> list:
    """Lista de búnkeres del usuario: [{"bunker_id", "name", "tickers_text", "created_at"}, ...]."""
    if not user_id:
        return []
    if _is_postgres():
        conn = psycopg2.connect(config.DATABASE_URL)
        conn.autocommit = True
        try:
            cur = conn.cursor(cursor_factory=pg_extras.RealDictCursor)
            cur.execute(
                "SELECT bunker_id, user_id, name, tickers_text, created_at FROM UserBunker WHERE user_id = %s ORDER BY name",
                (user_id,),
            )
            rows = cur.fetchall()
            return [dict(r) for r in rows] if rows else []
        finally:
            conn.close()
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT bunker_id, user_id, name, tickers_text, created_at FROM UserBunker WHERE user_id = ? ORDER BY name",
            (user_id,),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_bunker_by_id(bunker_id: int, user_id: int) -> dict | None:
    """Un búnker por ID (solo si pertenece al usuario)."""
    if not bunker_id or not user_id:
        return None
    if _is_postgres():
        conn = psycopg2.connect(config.DATABASE_URL)
        conn.autocommit = True
        try:
            cur = conn.cursor(cursor_factory=pg_extras.RealDictCursor)
            cur.execute(
                "SELECT bunker_id, user_id, name, tickers_text, created_at FROM UserBunker WHERE bunker_id = %s AND user_id = %s",
                (bunker_id, user_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT bunker_id, user_id, name, tickers_text, created_at FROM UserBunker WHERE bunker_id = ? AND user_id = ?",
            (bunker_id, user_id),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_bunker(user_id: int, name: str, tickers_text: str = "") -> int | None:
    """Crea un búnker. Devuelve bunker_id o None si falla (ej. nombre duplicado)."""
    if not user_id or not (name or "").strip():
        return None
    if _is_postgres():
        conn = psycopg2.connect(config.DATABASE_URL)
        conn.autocommit = True
        try:
            cur = conn.cursor(cursor_factory=pg_extras.RealDictCursor)
            cur.execute(
                """INSERT INTO UserBunker (user_id, name, tickers_text) VALUES (%s, %s, %s)
                 RETURNING bunker_id""",
                (user_id, (name or "").strip(), (tickers_text or "").strip()),
            )
            row = cur.fetchone()
            return row["bunker_id"] if row else None
        except Exception as e:
            if pg_IntegrityError and isinstance(e, pg_IntegrityError):
                return None
            raise
        finally:
            conn.close()
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO UserBunker (user_id, name, tickers_text) VALUES (?, ?, ?)",
            (user_id, (name or "").strip(), (tickers_text or "").strip()),
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None
    except Exception as e:
        if pg_IntegrityError and isinstance(e, pg_IntegrityError):
            return None
        raise
    finally:
        conn.close()


def update_bunker(bunker_id: int, user_id: int, name: str | None = None, tickers_text: str | None = None) -> bool:
    """Actualiza nombre y/o tickers de un búnker. Solo si pertenece al user_id."""
    if not bunker_id or not user_id:
        return False
    if _is_postgres():
        conn = psycopg2.connect(config.DATABASE_URL)
        conn.autocommit = True
        try:
            cur = conn.cursor()
            if name is not None and tickers_text is not None:
                cur.execute(
                    "UPDATE UserBunker SET name = %s, tickers_text = %s WHERE bunker_id = %s AND user_id = %s",
                    (name.strip(), (tickers_text or "").strip(), bunker_id, user_id),
                )
            elif name is not None:
                cur.execute(
                    "UPDATE UserBunker SET name = %s WHERE bunker_id = %s AND user_id = %s",
                    (name.strip(), bunker_id, user_id),
                )
            elif tickers_text is not None:
                cur.execute(
                    "UPDATE UserBunker SET tickers_text = %s WHERE bunker_id = %s AND user_id = %s",
                    ((tickers_text or "").strip(), bunker_id, user_id),
                )
            else:
                return False
            return cur.rowcount > 0
        finally:
            conn.close()
    conn = get_conn()
    try:
        if name is not None and tickers_text is not None:
            conn.execute(
                "UPDATE UserBunker SET name = ?, tickers_text = ? WHERE bunker_id = ? AND user_id = ?",
                (name.strip(), (tickers_text or "").strip(), bunker_id, user_id),
            )
        elif name is not None:
            conn.execute(
                "UPDATE UserBunker SET name = ? WHERE bunker_id = ? AND user_id = ?",
                (name.strip(), bunker_id, user_id),
            )
        elif tickers_text is not None:
            conn.execute(
                "UPDATE UserBunker SET tickers_text = ? WHERE bunker_id = ? AND user_id = ?",
                ((tickers_text or "").strip(), bunker_id, user_id),
            )
        else:
            return False
        conn.commit()
        return True
    finally:
        conn.close()


def delete_bunker(bunker_id: int, user_id: int) -> bool:
    """Elimina un búnker. Solo si pertenece al user_id."""
    if not bunker_id or not user_id:
        return False
    if _is_postgres():
        conn = psycopg2.connect(config.DATABASE_URL)
        conn.autocommit = True
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM UserBunker WHERE bunker_id = %s AND user_id = %s", (bunker_id, user_id))
            return cur.rowcount > 0
        finally:
            conn.close()
    conn = get_conn()
    try:
        cur = conn.execute("DELETE FROM UserBunker WHERE bunker_id = ? AND user_id = ?", (bunker_id, user_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# --- Cuentas (siempre filtradas por user_id) ---
def get_accounts_by_user(user_id: int):
    """Cuentas del usuario. Los datos de otro usuario nunca se exponen."""
    if _is_postgres():
        conn = psycopg2.connect(config.DATABASE_URL)
        try:
            cur = conn.cursor(cursor_factory=pg_extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM Account WHERE user_id = %s ORDER BY name",
                (user_id,),
            )
            rows = cur.fetchall()
            return [dict(r) for r in rows] if rows else []
        finally:
            conn.close()
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT * FROM Account WHERE user_id = ? ORDER BY name",
            (user_id,),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

def get_account_by_id(account_id: int, user_id: int):
    """Una cuenta por ID, solo si pertenece al user_id."""
    if _is_postgres():
        conn = psycopg2.connect(config.DATABASE_URL)
        conn.autocommit = True
        try:
            cur = conn.cursor(cursor_factory=pg_extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM Account WHERE account_id = %s AND user_id = %s",
                (account_id, user_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT * FROM Account WHERE account_id = ? AND user_id = ?",
            (account_id, user_id),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def update_account_token(account_id: int, user_id: int, access_token: str, environment: str = "sandbox"):
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE Account SET access_token = ?, environment = ?, connection_status = 'offline', connection_checked_at = NULL WHERE account_id = ? AND user_id = ?",
            (access_token, environment, account_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()

def set_account_connection_status(account_id: int, status: str):
    """status: 'online' | 'offline'."""
    conn = get_conn()
    try:
        if _is_postgres():
            conn.execute(
                "UPDATE Account SET connection_status = %s, connection_checked_at = now() WHERE account_id = %s",
                (status, account_id),
            )
        else:
            conn.execute(
                "UPDATE Account SET connection_status = ?, connection_checked_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE account_id = ?",
                (status, account_id),
            )
        conn.commit()
    finally:
        conn.close()

def create_account(user_id: int, name: str, cap_total: float = 100000.0, target_ann: float = 20.0, max_per_ticker: float = 10.0):
    """Crea una cuenta. Devuelve account_id o None si ya existe una cuenta con ese nombre (UniqueViolation)."""
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO Account (user_id, name, cap_total, target_ann, max_per_ticker) VALUES (?, ?, ?, ?, ?)",
            (user_id, name, cap_total, target_ann, max_per_ticker),
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None
    except Exception as e:
        if pg_IntegrityError and isinstance(e, pg_IntegrityError):
            return None
        raise
    finally:
        conn.close()

def update_account_config(account_id: int, user_id: int, cap_total: float, target_ann: float, max_per_ticker: float):
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE Account SET cap_total = ?, target_ann = ?, max_per_ticker = ? WHERE account_id = ? AND user_id = ?",
            (cap_total, target_ann, max_per_ticker, account_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_account_av_key(account_id: int, user_id: int, av_api_key: str) -> None:
    """Guarda la clave de Alpha Vantage para la cuenta (screener)."""
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE Account SET av_api_key = ? WHERE account_id = ? AND user_id = ?",
            (av_api_key or "", account_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def delete_account(account_id: int, user_id: int) -> bool:
    """Borra la cuenta y todos sus datos (trades, dividendos, ajustes). Solo si la cuenta pertenece al user_id. Devuelve True si se borró."""
    conn = get_conn()
    try:
        cur = conn.execute("SELECT account_id FROM Account WHERE account_id = ? AND user_id = ?", (account_id, user_id))
        if not cur.fetchone():
            return False
        trade_ids = [r[0] for r in conn.execute("SELECT trade_id FROM Trade WHERE account_id = ?", (account_id,)).fetchall()]
        if trade_ids:
            placeholders = ",".join("?" * len(trade_ids))
            conn.execute(f"DELETE FROM TradeComment WHERE trade_id IN ({placeholders})", trade_ids)
        conn.execute("DELETE FROM Trade WHERE account_id = ?", (account_id,))
        conn.execute("DELETE FROM Dividend WHERE account_id = ?", (account_id,))
        conn.execute("DELETE FROM PositionAdjustment WHERE account_id = ?", (account_id,))
        conn.execute("DELETE FROM Account WHERE account_id = ? AND user_id = ?", (account_id, user_id))
        conn.commit()
        return True
    finally:
        conn.close()


# --- Trades (siempre por account_id; la cuenta ya está ligada al user) ---
def get_trade_by_id(account_id: int, trade_id: int):
    """Un trade por ID, solo si pertenece a la cuenta."""
    if _is_postgres():
        conn = psycopg2.connect(config.DATABASE_URL)
        conn.autocommit = True
        try:
            cur = conn.cursor(cursor_factory=pg_extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM Trade WHERE account_id = %s AND trade_id = %s",
                (account_id, trade_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT * FROM Trade WHERE account_id = ? AND trade_id = ?",
            (account_id, trade_id),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_trades_by_account(account_id: int, status: str = None, ticker: str = None):
    """Trades de la cuenta. Opcional: filtrar por status y/o ticker."""
    if _is_postgres():
        conn = psycopg2.connect(config.DATABASE_URL)
        conn.autocommit = True
        try:
            cur = conn.cursor(cursor_factory=pg_extras.RealDictCursor)
            q = "SELECT * FROM Trade WHERE account_id = %s"
            params = [account_id]
            if status:
                q += " AND status = %s"
                params.append(status)
            if ticker:
                q += " AND ticker = %s"
                params.append(ticker)
            q += " ORDER BY trade_date DESC, trade_id DESC"
            cur.execute(q, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows] if rows else []
        finally:
            conn.close()
    conn = get_conn()
    try:
        q = "SELECT * FROM Trade WHERE account_id = ?"
        params = [account_id]
        if status:
            q += " AND status = ?"
            params.append(status)
        if ticker:
            q += " AND ticker = ?"
            params.append(ticker)
        q += " ORDER BY trade_date DESC, trade_id DESC"
        cur = conn.execute(q, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

def insert_trade(account_id: int, ticker: str, asset_type: str, quantity: int, price: float,
                strategy_type: str, status: str, entry_type: str, trade_date: str,
                strike: float = None, expiration_date: str = None, closed_date: str = None,
                parent_trade_id: int = None, comment: str = None):
    if _is_postgres():
        conn = psycopg2.connect(config.DATABASE_URL)
        conn.autocommit = True
        try:
            cur = conn.cursor(cursor_factory=pg_extras.RealDictCursor)
            cur.execute(
                """INSERT INTO Trade (account_id, ticker, asset_type, quantity, price, strike, expiration_date,
                 strategy_type, status, entry_type, trade_date, closed_date, parent_trade_id, comment)
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                 RETURNING trade_id""",
                (account_id, ticker, asset_type, quantity, price, strike, expiration_date,
                 strategy_type, status, entry_type, trade_date, closed_date, parent_trade_id, comment),
            )
            row = cur.fetchone()
            return row["trade_id"] if row else None
        finally:
            conn.close()
    conn = get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO Trade (account_id, ticker, asset_type, quantity, price, strike, expiration_date,
             strategy_type, status, entry_type, trade_date, closed_date, parent_trade_id, comment)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (account_id, ticker, asset_type, quantity, price, strike, expiration_date,
             strategy_type, status, entry_type, trade_date, closed_date, parent_trade_id, comment),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def close_trade(trade_id: int, account_id: int, closed_date: str, buyback_debit: float = None):
    """
    Cierra un trade (CSP/CC o otro). Si buyback_debit es distinto de None, se registra cierre por recompra:
    close_type='buyback' y buyback_debit=importe pagado. Resultado: CSP → cash; CC → acciones libres.
    """
    conn = get_conn()
    try:
        if buyback_debit is not None:
            conn.execute(
                "UPDATE Trade SET status = 'CLOSED', closed_date = ?, close_type = 'buyback', buyback_debit = ? WHERE trade_id = ? AND account_id = ?",
                (closed_date, round(float(buyback_debit), 2), trade_id, account_id),
            )
        else:
            conn.execute(
                "UPDATE Trade SET status = 'CLOSED', closed_date = ? WHERE trade_id = ? AND account_id = ?",
                (closed_date, trade_id, account_id),
            )
        conn.commit()
    finally:
        conn.close()


def update_trade(trade_id: int, account_id: int, price: float = None, strike: float = None, expiration_date: str = None,
                 comment: str = None, quantity: int = None, trade_date: str = None):
    """Actualiza campos editables de un trade. OPTION: price, strike, expiration_date, comment. STOCK: price, quantity, trade_date, comment."""
    conn = get_conn()
    try:
        updates, params = [], []
        if price is not None:
            updates.append("price = ?")
            params.append(price)
        if strike is not None:
            updates.append("strike = ?")
            params.append(strike)
        if expiration_date is not None:
            updates.append("expiration_date = ?")
            params.append(expiration_date)
        if comment is not None:
            updates.append("comment = ?")
            params.append(comment)
        if quantity is not None:
            updates.append("quantity = ?")
            params.append(quantity)
        if trade_date is not None:
            updates.append("trade_date = ?")
            params.append(trade_date)
        if not updates:
            return
        params.extend([trade_id, account_id])
        conn.execute(
            f"UPDATE Trade SET {', '.join(updates)} WHERE trade_id = ? AND account_id = ?",
            params,
        )
        conn.commit()
    finally:
        conn.close()


def set_trade_buyback(trade_id: int, account_id: int, buyback_debit: float) -> None:
    """Registra en un trade (p. ej. recompra) close_type='buyback' y el débito pagado. Evita perder precisión en débitos pequeños."""
    if _is_postgres():
        conn = psycopg2.connect(config.DATABASE_URL)
        conn.autocommit = True
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE Trade SET close_type = 'buyback', buyback_debit = %s WHERE trade_id = %s AND account_id = %s",
                (round(float(buyback_debit), 2), trade_id, account_id),
            )
        finally:
            conn.close()
        return
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE Trade SET close_type = 'buyback', buyback_debit = ? WHERE trade_id = ? AND account_id = ?",
            (round(float(buyback_debit), 2), trade_id, account_id),
        )
        conn.commit()
    finally:
        conn.close()


# --- Ajustes por campaña (comisiones y fees) ---
def _ensure_campaign_adjustment_table(conn):
    """Crea la tabla CampaignAdjustment si no existe (PostgreSQL puede no tenerla en schema inicial)."""
    if _is_postgres() and psycopg2:
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS CampaignAdjustment (
                    account_id INTEGER NOT NULL REFERENCES Account(account_id),
                    campaign_root_id INTEGER NOT NULL REFERENCES Trade(trade_id),
                    commissions REAL DEFAULT 0,
                    fees REAL DEFAULT 0,
                    PRIMARY KEY (account_id, campaign_root_id)
                )
            """)
        except Exception:
            pass


def get_campaign_adjustment(account_id: int, campaign_root_id: int):
    """Devuelve {commissions, fees} para la campaña, o {commissions: 0, fees: 0} si no hay registro."""
    if _is_postgres():
        conn = psycopg2.connect(config.DATABASE_URL)
        conn.autocommit = True
        try:
            _ensure_campaign_adjustment_table(conn)
            cur = conn.cursor(cursor_factory=pg_extras.RealDictCursor)
            cur.execute(
                "SELECT commissions, fees FROM CampaignAdjustment WHERE account_id = %s AND campaign_root_id = %s",
                (account_id, campaign_root_id),
            )
            row = cur.fetchone()
            if row:
                return {"commissions": float(row.get("commissions") or 0), "fees": float(row.get("fees") or 0)}
            return {"commissions": 0.0, "fees": 0.0}
        finally:
            conn.close()
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT commissions, fees FROM CampaignAdjustment WHERE account_id = ? AND campaign_root_id = ?",
            (account_id, campaign_root_id),
        )
        row = cur.fetchone()
        if row:
            try:
                return {"commissions": float(row.get("commissions") or 0), "fees": float(row.get("fees") or 0)}
            except (TypeError, KeyError):
                return {"commissions": float(row[0] or 0), "fees": float(row[1] or 0)}
        return {"commissions": 0.0, "fees": 0.0}
    finally:
        conn.close()


def upsert_campaign_adjustment(account_id: int, campaign_root_id: int, commissions: float = 0, fees: float = 0):
    """Crea o actualiza comisiones y fees de la campaña."""
    if _is_postgres():
        conn = psycopg2.connect(config.DATABASE_URL)
        conn.autocommit = True
        try:
            _ensure_campaign_adjustment_table(conn)
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO CampaignAdjustment (account_id, campaign_root_id, commissions, fees)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (account_id, campaign_root_id) DO UPDATE SET commissions = EXCLUDED.commissions, fees = EXCLUDED.fees""",
                (account_id, campaign_root_id, round(float(commissions), 2), round(float(fees), 2)),
            )
        finally:
            conn.close()
        return
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO CampaignAdjustment (account_id, campaign_root_id, commissions, fees)
               VALUES (?, ?, ?, ?)
               ON CONFLICT (account_id, campaign_root_id) DO UPDATE SET commissions = excluded.commissions, fees = excluded.fees""",
            (account_id, campaign_root_id, round(float(commissions), 2), round(float(fees), 2)),
        )
        conn.commit()
    finally:
        conn.close()


# --- Dividendos ---
def get_dividends_by_account(account_id: int, ticker: str = None):
    conn = get_conn()
    try:
        q = "SELECT * FROM Dividend WHERE account_id = ?"
        params = [account_id]
        if ticker:
            q += " AND ticker = ?"
            params.append(ticker)
        q += " ORDER BY ex_date DESC"
        cur = conn.execute(q, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

def insert_dividend(account_id: int, ticker: str, amount: float, ex_date: str, pay_date: str = None, note: str = None):
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO Dividend (account_id, ticker, amount, ex_date, pay_date, note) VALUES (?, ?, ?, ?, ?, ?)",
            (account_id, ticker, amount, ex_date, pay_date, note),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

# --- Ajustes de posición ---
def get_adjustments_by_account(account_id: int, ticker: str = None):
    conn = get_conn()
    try:
        q = "SELECT * FROM PositionAdjustment WHERE account_id = ?"
        params = [account_id]
        if ticker:
            q += " AND ticker = ?"
            params.append(ticker)
        q += " ORDER BY created_at DESC"
        cur = conn.execute(q, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

def insert_adjustment(account_id: int, ticker: str, adjustment_type: str, old_value: float = None, new_value: float = None, note: str = None, trade_id: int = None):
    conn = get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO PositionAdjustment (account_id, trade_id, ticker, adjustment_type, old_value, new_value, note)
             VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (account_id, trade_id, ticker, adjustment_type, old_value, new_value, note),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

# --- Bitácora (comentarios por trade) ---
def get_trade_comments(trade_id: int):
    conn = get_conn()
    try:
        cur = conn.execute("SELECT * FROM TradeComment WHERE trade_id = ? ORDER BY created_at", (trade_id,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

def add_trade_comment(trade_id: int, body: str):
    conn = get_conn()
    try:
        cur = conn.execute("INSERT INTO TradeComment (trade_id, body) VALUES (?, ?)", (trade_id, body))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()
