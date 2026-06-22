import os
import sqlite3

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "tracker.db")

def get_db_connection():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if migration is needed for nav_history
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='nav_history'")
    table_exists = cursor.fetchone()
    
    need_migration = False
    if table_exists:
        cursor.execute("PRAGMA table_info(nav_history)")
        cols = [r['name'] for r in cursor.fetchall()]
        if 'etf_code' not in cols:
            need_migration = True
            
    if need_migration:
        print("Migrating SQLite database schema to support multi-ETF (adding etf_code)...")
        try:
            # 1. Migrate nav_history
            cursor.execute("""
            CREATE TABLE nav_history_new (
                etf_code TEXT NOT NULL,
                date TEXT NOT NULL,
                nav REAL NOT NULL,
                change_percent TEXT,
                fund_assets REAL,
                outstanding_units REAL,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (etf_code, date)
            )
            """)
            cursor.execute("SELECT COUNT(*) FROM nav_history")
            if cursor.fetchone()[0] > 0:
                cursor.execute("""
                INSERT INTO nav_history_new (etf_code, date, nav, change_percent, fund_assets, outstanding_units, scraped_at)
                SELECT '00997A', date, nav, change_percent, fund_assets, outstanding_units, scraped_at FROM nav_history
                """)
            
            # 2. Migrate holdings_history
            cursor.execute("""
            CREATE TABLE holdings_history_new (
                etf_code TEXT NOT NULL,
                date TEXT NOT NULL,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                weight REAL NOT NULL,
                shares INTEGER,
                PRIMARY KEY (etf_code, date, code)
            )
            """)
            cursor.execute("SELECT COUNT(*) FROM holdings_history")
            if cursor.fetchone()[0] > 0:
                cursor.execute("""
                INSERT INTO holdings_history_new (etf_code, date, code, name, weight, shares)
                SELECT '00997A', date, code, name, weight, shares FROM holdings_history
                """)
                
            # 3. Migrate ai_analysis
            cursor.execute("""
            CREATE TABLE ai_analysis_new (
                etf_code TEXT NOT NULL,
                date TEXT NOT NULL,
                range_days INTEGER DEFAULT 1,
                recommendation TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (etf_code, date, range_days)
            )
            """)
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_analysis'")
            if cursor.fetchone():
                cursor.execute("SELECT COUNT(*) FROM ai_analysis")
                if cursor.fetchone()[0] > 0:
                    cursor.execute("""
                    INSERT INTO ai_analysis_new (etf_code, date, range_days, recommendation, created_at)
                    SELECT '00997A', date, range_days, recommendation, created_at FROM ai_analysis
                    """)
                
            # 4. Migrate personal_holdings
            cursor.execute("""
            CREATE TABLE personal_holdings_new (
                etf_code TEXT NOT NULL,
                date TEXT NOT NULL,
                units REAL NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (etf_code, date)
            )
            """)
            cursor.execute("SELECT COUNT(*) FROM personal_holdings")
            if cursor.fetchone()[0] > 0:
                cursor.execute("""
                INSERT INTO personal_holdings_new (etf_code, date, units, updated_at)
                SELECT '00997A', date, units, updated_at FROM personal_holdings
                """)
                
            # 5. Migrate announcements
            cursor.execute("""
            CREATE TABLE announcements_new (
                id TEXT PRIMARY KEY,
                etf_code TEXT NOT NULL,
                title TEXT NOT NULL,
                date TEXT NOT NULL,
                url TEXT NOT NULL,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            cursor.execute("SELECT COUNT(*) FROM announcements")
            if cursor.fetchone()[0] > 0:
                cursor.execute("""
                INSERT INTO announcements_new (id, etf_code, title, date, url, scraped_at)
                SELECT id, '00997A', title, date, url, scraped_at FROM announcements
                """)
                
            # Drop old tables
            cursor.execute("DROP TABLE nav_history")
            cursor.execute("DROP TABLE holdings_history")
            cursor.execute("DROP TABLE IF EXISTS ai_analysis")
            cursor.execute("DROP TABLE personal_holdings")
            cursor.execute("DROP TABLE announcements")
            
            # Rename new tables
            cursor.execute("ALTER TABLE nav_history_new RENAME TO nav_history")
            cursor.execute("ALTER TABLE holdings_history_new RENAME TO holdings_history")
            cursor.execute("ALTER TABLE ai_analysis_new RENAME TO ai_analysis")
            cursor.execute("ALTER TABLE personal_holdings_new RENAME TO personal_holdings")
            cursor.execute("ALTER TABLE announcements_new RENAME TO announcements")
            
            conn.commit()
            print("Database migration completed successfully!")
        except Exception as e:
            conn.rollback()
            print(f"Error migrating database: {e}")
            raise e
    else:
        # Create tables from scratch if they don't exist
        # 1. NAV History Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS nav_history (
            etf_code TEXT NOT NULL,
            date TEXT NOT NULL,
            nav REAL NOT NULL,
            change_percent TEXT,
            fund_assets REAL,
            outstanding_units REAL,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (etf_code, date)
        )
        """)
        
        # 2. Holdings Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS holdings_history (
            etf_code TEXT NOT NULL,
            date TEXT NOT NULL,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            weight REAL NOT NULL,
            shares INTEGER,
            PRIMARY KEY (etf_code, date, code)
        )
        """)
        
        # 3. Announcements Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            id TEXT PRIMARY KEY,
            etf_code TEXT NOT NULL,
            title TEXT NOT NULL,
            date TEXT NOT NULL,
            url TEXT NOT NULL,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # 4. Personal Holdings Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS personal_holdings (
            etf_code TEXT NOT NULL,
            date TEXT NOT NULL,
            units REAL NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (etf_code, date)
        )
        """)
        
        # 5. AI Recommendations Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_analysis (
            etf_code TEXT NOT NULL,
            date TEXT NOT NULL,
            range_days INTEGER DEFAULT 1,
            recommendation TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (etf_code, date, range_days)
        )
        """)
        
        # Seed default personal holdings if empty
        cursor.execute("SELECT COUNT(*) FROM personal_holdings")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT OR IGNORE INTO personal_holdings (etf_code, date, units) VALUES ('00997A', '2026-06-20', 0)")
            cursor.execute("INSERT OR IGNORE INTO personal_holdings (etf_code, date, units) VALUES ('00981A', '2026-06-20', 0)")
            cursor.execute("INSERT OR IGNORE INTO personal_holdings (etf_code, date, units) VALUES ('00403A', '2026-06-20', 0)")
            cursor.execute("INSERT OR IGNORE INTO personal_holdings (etf_code, date, units) VALUES ('00988A', '2026-06-20', 0)")
            
        conn.commit()
    conn.close()

# --- Helper Functions for Data Operations ---

def save_nav(etf_code, date, nav, change_percent=None, fund_assets=None, outstanding_units=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO nav_history (etf_code, date, nav, change_percent, fund_assets, outstanding_units)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (etf_code, date, nav, change_percent, fund_assets, outstanding_units))
    conn.commit()
    conn.close()

def save_holdings(etf_code, date, holdings_list):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM holdings_history WHERE etf_code = ? AND date = ?", (etf_code, date))
    
    for h in holdings_list:
        cursor.execute("""
        INSERT OR REPLACE INTO holdings_history (etf_code, date, code, name, weight, shares)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (etf_code, date, h['code'], h['name'], h['weight'], h.get('shares', 0)))
    conn.commit()
    conn.close()

def save_announcements(etf_code, announcements_list):
    conn = get_db_connection()
    cursor = conn.cursor()
    for item in announcements_list:
        import hashlib
        unique_str = f"{etf_code}_{item['date']}_{item['title']}"
        ann_id = hashlib.md5(unique_str.encode('utf-8')).hexdigest()
        
        cursor.execute("""
        INSERT OR IGNORE INTO announcements (id, etf_code, title, date, url)
        VALUES (?, ?, ?, ?, ?)
        """, (ann_id, etf_code, item['title'], item['date'], item['url']))
    conn.commit()
    conn.close()

def get_latest_nav(etf_code):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM nav_history WHERE etf_code = ? ORDER BY date DESC LIMIT 1", (etf_code,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_nav_history(etf_code, limit=30):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM nav_history WHERE etf_code = ? ORDER BY date DESC LIMIT ?", (etf_code, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]

def get_holdings_for_date(etf_code, date):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM holdings_history WHERE etf_code = ? AND date = ? ORDER BY weight DESC", (etf_code, date))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_latest_holdings_date(etf_code):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT date FROM holdings_history WHERE etf_code = ? ORDER BY date DESC LIMIT 1", (etf_code,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def get_previous_holdings_date(etf_code, current_date):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT date FROM holdings_history WHERE etf_code = ? AND date < ? ORDER BY date DESC LIMIT 1", (etf_code, current_date))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def get_holdings_date_at_offset(etf_code, current_date, offset):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT DISTINCT date FROM holdings_history 
    WHERE etf_code = ? AND date <= ? 
    ORDER BY date DESC
    """, (etf_code, current_date))
    rows = cursor.fetchall()
    conn.close()
    dates = [r[0] for r in rows]
    if not dates:
        return None
    if offset < len(dates):
        return dates[offset]
    return dates[-1]

def get_announcements(etf_code, limit=20):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM announcements WHERE etf_code = ? ORDER BY date DESC, scraped_at DESC LIMIT ?", (etf_code, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_personal_units(etf_code, units, date=None):
    import datetime
    if not date:
        date = datetime.date.today().strftime('%Y-%m-%d')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO personal_holdings (etf_code, date, units, updated_at)
    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
    """, (etf_code, date, units))
    conn.commit()
    conn.close()

def get_latest_personal_units(etf_code):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT units FROM personal_holdings WHERE etf_code = ? ORDER BY date DESC, updated_at DESC LIMIT 1", (etf_code,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0.0

def save_ai_analysis(etf_code, date, recommendation, range_days=1):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO ai_analysis (etf_code, date, range_days, recommendation, created_at)
    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (etf_code, date, range_days, recommendation))
    conn.commit()
    conn.close()

def get_ai_analysis(etf_code, date, range_days=1):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT recommendation FROM ai_analysis WHERE etf_code = ? AND date = ? AND range_days = ?", (etf_code, date, range_days))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
