-- AlphaWheel Pro - Esquema multi-usuario (SQLite)
-- Aislamiento: todas las consultas por user_id / account_id

-- Usuarios del sistema (multi-usuario con autenticación)
CREATE TABLE IF NOT EXISTS User (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    display_name TEXT,
    password_hash TEXT,
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Cuentas por usuario (ej. "Robinhood Taxable", "IRA Principal")
CREATE TABLE IF NOT EXISTS Account (
    account_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    provider TEXT DEFAULT 'tradier',
    access_token TEXT,
    environment TEXT DEFAULT 'sandbox',
    cap_total REAL DEFAULT 100000.0,
    target_ann REAL DEFAULT 20.0,
    max_per_ticker REAL DEFAULT 10.0,
    connection_status TEXT DEFAULT 'offline',
    connection_checked_at TEXT,
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(user_id, name),
    FOREIGN KEY (user_id) REFERENCES User(user_id)
);

-- Trades: cada pierna (CSP, CC, compra/venta stock, asignación)
CREATE TABLE IF NOT EXISTS Trade (
    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    asset_type TEXT NOT NULL CHECK (asset_type IN ('OPTION', 'STOCK')),
    quantity INTEGER NOT NULL,
    price REAL NOT NULL,
    strike REAL,
    expiration_date TEXT,
    strategy_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED')),
    entry_type TEXT NOT NULL CHECK (entry_type IN ('OPENING', 'ASSIGNMENT', 'DIRECT_PURCHASE', 'CLOSING')),
    trade_date TEXT NOT NULL,
    closed_date TEXT,
    close_type TEXT,
    buyback_debit REAL,
    parent_trade_id INTEGER,
    comment TEXT,
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (account_id) REFERENCES Account(account_id),
    FOREIGN KEY (parent_trade_id) REFERENCES Trade(trade_id)
);

-- Dividendos (reducen cost basis efectivo)
CREATE TABLE IF NOT EXISTS Dividend (
    dividend_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    amount REAL NOT NULL,
    ex_date TEXT NOT NULL,
    pay_date TEXT,
    note TEXT,
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (account_id) REFERENCES Account(account_id)
);

-- Ajustes manuales (splits, corrección cost basis)
CREATE TABLE IF NOT EXISTS PositionAdjustment (
    adjustment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    trade_id INTEGER,
    ticker TEXT NOT NULL,
    adjustment_type TEXT NOT NULL CHECK (adjustment_type IN ('SPLIT', 'COST_BASIS_CORRECTION', 'OTHER')),
    old_value REAL,
    new_value REAL,
    note TEXT,
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (account_id) REFERENCES Account(account_id),
    FOREIGN KEY (trade_id) REFERENCES Trade(trade_id)
);

-- Bitácora: comentarios por trade
CREATE TABLE IF NOT EXISTS TradeComment (
    comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (trade_id) REFERENCES Trade(trade_id)
);

-- Ajustes por campaña: comisiones broker y fees (restan del neto de la campaña)
CREATE TABLE IF NOT EXISTS CampaignAdjustment (
    account_id INTEGER NOT NULL,
    campaign_root_id INTEGER NOT NULL,
    commissions REAL DEFAULT 0,
    fees REAL DEFAULT 0,
    PRIMARY KEY (account_id, campaign_root_id),
    FOREIGN KEY (account_id) REFERENCES Account(account_id),
    FOREIGN KEY (campaign_root_id) REFERENCES Trade(trade_id)
);

-- Índices para filtrado por usuario/cuenta
CREATE INDEX IF NOT EXISTS idx_account_user ON Account(user_id);
CREATE INDEX IF NOT EXISTS idx_trade_account ON Trade(account_id);
CREATE INDEX IF NOT EXISTS idx_trade_status_account ON Trade(status, account_id);
CREATE INDEX IF NOT EXISTS idx_trade_ticker_account ON Trade(ticker, account_id);
CREATE INDEX IF NOT EXISTS idx_dividend_account ON Dividend(account_id);
CREATE INDEX IF NOT EXISTS idx_adjustment_account ON PositionAdjustment(account_id);
