-- AlphaWheel Pro - Esquema PostgreSQL (multi-usuario, persistente en la nube)
-- Uso: definir ALPHAWHEEL_DATABASE_URL=postgresql://user:pass@host:5432/dbname

CREATE TABLE IF NOT EXISTS "User" (
    user_id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    display_name TEXT,
    password_hash TEXT,
    av_api_key TEXT,
    screener_watchlist TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS Account (
    account_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "User"(user_id),
    name TEXT NOT NULL,
    provider TEXT DEFAULT 'tradier',
    access_token TEXT,
    environment TEXT DEFAULT 'sandbox',
    cap_total REAL DEFAULT 100000.0,
    target_ann REAL DEFAULT 20.0,
    max_per_ticker REAL DEFAULT 10.0,
    connection_status TEXT DEFAULT 'offline',
    connection_checked_at TIMESTAMPTZ,
    av_api_key TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, name)
);

CREATE TABLE IF NOT EXISTS Trade (
    trade_id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES Account(account_id),
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
    parent_trade_id INTEGER REFERENCES Trade(trade_id),
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS Dividend (
    dividend_id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES Account(account_id),
    ticker TEXT NOT NULL,
    amount REAL NOT NULL,
    ex_date TEXT NOT NULL,
    pay_date TEXT,
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS PositionAdjustment (
    adjustment_id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES Account(account_id),
    trade_id INTEGER REFERENCES Trade(trade_id),
    ticker TEXT NOT NULL,
    adjustment_type TEXT NOT NULL CHECK (adjustment_type IN ('SPLIT', 'COST_BASIS_CORRECTION', 'OTHER')),
    old_value REAL,
    new_value REAL,
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS TradeComment (
    comment_id SERIAL PRIMARY KEY,
    trade_id INTEGER NOT NULL REFERENCES Trade(trade_id),
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS UserBunker (
    bunker_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "User"(user_id),
    name TEXT NOT NULL,
    tickers_text TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, name)
);

CREATE INDEX IF NOT EXISTS idx_account_user ON Account(user_id);
CREATE INDEX IF NOT EXISTS idx_trade_account ON Trade(account_id);
CREATE INDEX IF NOT EXISTS idx_trade_status_account ON Trade(status, account_id);
CREATE INDEX IF NOT EXISTS idx_trade_ticker_account ON Trade(ticker, account_id);
CREATE INDEX IF NOT EXISTS idx_dividend_account ON Dividend(account_id);
CREATE INDEX IF NOT EXISTS idx_adjustment_account ON PositionAdjustment(account_id);
