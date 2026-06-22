import requests
import datetime
import time
import re
import db

def parse_roc_date(date_str):
    # Converts '115/06/01' to '2026-06-01'
    match = re.search(r'(\d+)/(\d{2})/(\d{2})', date_str)
    if match:
        year = int(match.group(1)) + 1911
        month = int(match.group(2))
        day = int(match.group(3))
        return f"{year}-{month:02d}-{day:02d}"
    return date_str

def seed_history():
    print("Initializing Database...")
    db.init_db()
    
    # 00997A listed on 2026-04-14. We want to fetch April, May, and June 2026 data.
    # TWSE API format: date=YYYYMMDD (queries the entire month of that date)
    months = ["20260401", "20260501", "20260601"]
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    total_seeded = 0
    
    for m in months:
        url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&stockNo=00997A&date={m}"
        print(f"Fetching historical prices for month: {m[:6]} from TWSE...")
        try:
            response = requests.get(url, headers=headers, timeout=12)
            if response.status_code == 200:
                resp_data = response.json()
                data_rows = resp_data.get("data", [])
                
                print(f"  Found {len(data_rows)} trading days.")
                for row in data_rows:
                    # Row columns: Date, Volume, Turnover, Open, High, Low, Close, Change, Transactions, etc.
                    date_raw = row[0]
                    close_val = row[6]
                    change_val = row[7]
                    
                    date_clean = parse_roc_date(date_raw)
                    try:
                        price = float(close_val.replace(",", ""))
                    except ValueError:
                        continue
                        
                    # Save into nav_history
                    # We use the closing price as the NAV for historical entries
                    db.save_nav(
                        date=date_clean,
                        nav=price,
                        change_percent=change_val.strip(),
                        fund_assets=None,
                        outstanding_units=None
                    )
                    total_seeded += 1
            else:
                print(f"  TWSE API returned status: {response.status_code}")
        except Exception as e:
            print(f"  Error fetching: {e}")
            
        # Sleep to be polite to TWSE servers
        time.sleep(2)
        
    print(f"Seeding completed. Total historical entries added: {total_seeded}")

if __name__ == "__main__":
    seed_history()
