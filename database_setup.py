import sqlite3
import os

def create_database():
    if os.path.exists('trading_app.db'):
        os.remove('trading_app.db') # Borramos para empezar de cero sin errores
        
    conn = sqlite3.connect('trading_app.db')
    cursor = conn.cursor()
    
    # Tabla de Usuarios: Solo lo esencial
    cursor.execute('''CREATE TABLE Users (
        user_id INTEGER PRIMARY KEY, 
        access_token TEXT,
        cap_total REAL,
        target_ann REAL)''')
    
    # Tabla de Trades: Estructura contable limpia
    cursor.execute('''CREATE TABLE Trades (
        trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_name TEXT,
        ticker TEXT,
        asset_type TEXT,
        quantity INTEGER,
        price REAL,
        strike REAL,
        expiration_date TEXT,
        status TEXT,
        strategy_type TEXT,
        parent_id INTEGER)''')
    
    cursor.execute("INSERT INTO Users (user_id, cap_total, target_ann) VALUES (1, 100000.0, 15.0)")
    conn.commit()
    conn.close()
    print("✅ Base de datos reseteada y limpia.")

if __name__ == "__main__":
    create_database()