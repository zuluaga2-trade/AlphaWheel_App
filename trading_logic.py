import sqlite3
from datetime import datetime

def init_db():
    conn = sqlite3.connect('trading_app.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS Trades (
            trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date TEXT, account_name TEXT, ticker TEXT,
            asset_type TEXT, quantity INTEGER, price REAL,
            strike REAL, expiration_date TEXT, strategy_type TEXT,
            status TEXT DEFAULT 'OPEN')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS Accounts (
            account_id INTEGER PRIMARY KEY AUTOINCREMENT, 
            name TEXT UNIQUE, access_token TEXT,
            cap_total REAL DEFAULT 100000.0,
            target_ann REAL DEFAULT 20.0,
            max_per_ticker REAL DEFAULT 10.0)''')
    conn.commit()
    conn.close()

def update_account_config(acc_name, token, cap, target, max_ticker):
    conn = sqlite3.connect('trading_app.db')
    conn.execute('''UPDATE Accounts SET access_token=?, cap_total=?, target_ann=?, max_per_ticker=? WHERE name=?''', 
                 (token, cap, target, max_ticker, acc_name))
    conn.commit()
    conn.close()

def calculate_dte(exp_date):
    if not exp_date or str(exp_date).strip() in ['None', '', 'N/A']: return 0
    try:
        exp = datetime.strptime(str(exp_date).strip(), '%Y-%m-%d')
        return max(0, (exp - datetime.now()).days)
    except: return 0

init_db()