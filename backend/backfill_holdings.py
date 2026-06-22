import datetime
import time
import db
import scraper

def backfill():
    print("Initializing Database...")
    db.init_db()
    
    # 1. Query the 12 most recent dates in nav_history to backfill holdings for
    # We query 12 to make sure we cover at least 10 valid trading days
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT date FROM nav_history ORDER BY date DESC LIMIT 12")
    rows = cursor.fetchall()
    conn.close()
    
    dates = [r[0] for r in rows]
    print("Found recent historical dates in database:", dates)
    
    # Add today/latest portfolio date if not already in dates
    latest_holdings_date = scraper.scrape_portfolio_holdings().get("date")
    if latest_holdings_date and latest_holdings_date not in dates:
        dates.insert(0, latest_holdings_date)
        
    # We want to backfill the latest 10 unique trading days
    target_dates = dates[:11] # take up to 11 to ensure we have a solid 10-day history
    print(f"Targeting backfill for {len(target_dates)} dates: {target_dates}")
    
    success_count = 0
    for d in target_dates:
        print(f"Backfilling holdings for date: {d} ...")
        try:
            # Query Capital Fund PCF API with specific date
            pcf_data = scraper.scrape_portfolio_holdings()
            # If the date differs from current, we fetch for that specific date
            # We must call scraper.scrape_portfolio_holdings with date parameter!
            # Wait, let's look at how scrape_portfolio_holdings is implemented.
            # In scraper.py, we only supported scraping latest. We need to modify scraper.py 
            # to support an optional date parameter in scrape_portfolio_holdings(date=None)!
            # Let's double check if we can pass the date to the API.
            # Yes! The API POST payload takes {"fundId": "502", "date": "2026-06-08"}.
            # Let's write the query payload inside this script or modify scraper.py.
            # We can write the fetch logic directly here, or modify scraper.py.
            # Direct fetch logic is very clean and self-contained! Let's do it here.
            
            payload = {"fundId": "502", "date": d.replace("-", "/")}
            url = "https://www.capitalfund.com.tw/CFWeb/api/etf/buyback"
            response = requests.post(url, headers=scraper.HEADERS, json=payload, timeout=12)
            
            if response.status_code == 200:
                resp_json = response.json()
                if resp_json.get("code") == 200:
                    data = resp_json.get("data", {})
                    pcf_summary = data.get("pcf", {})
                    stocks = data.get("stocks", [])
                    
                    # Convert stocks to scraper structure
                    holdings_list = []
                    for s in stocks:
                        code = s.get("stocNo", "").strip()
                        name = s.get("stocName", "").strip()
                        if not name or "" in name:
                            name = s.get("stocEname", "").strip()
                        weight = float(s.get("weight") or s.get("weightRound") or 0.0)
                        shares = int(s.get("share") or 0)
                        if code:
                            holdings_list.append({
                                "code": code,
                                "name": name,
                                "weight": weight,
                                "shares": shares
                            })
                            
                    # Save holdings
                    db.save_holdings(d, holdings_list)
                    
                    # Save fund scale/units to nav_history
                    fund_assets = int(pcf_summary.get("nav") or 0)
                    units = int(pcf_summary.get("totUnit") or 0)
                    
                    # Retrieve existing NAV entry or use the PCF unit NAV
                    existing_nav = 0.0
                    existing_change = "0.0%"
                    
                    conn_d = db.get_db_connection()
                    cursor_d = conn_d.cursor()
                    cursor_d.execute("SELECT nav, change_percent FROM nav_history WHERE date = ?", (d,))
                    row_d = cursor_d.fetchone()
                    conn_d.close()
                    
                    if row_d:
                        existing_nav = row_d[0]
                        existing_change = row_d[1]
                    else:
                        existing_nav = float(pcf_summary.get("pUnit") or 0.0)
                        
                    db.save_nav(
                        date=d,
                        nav=existing_nav,
                        change_percent=existing_change,
                        fund_assets=fund_assets,
                        outstanding_units=units
                    )
                    
                    print(f"  Successfully saved {len(holdings_list)} holdings. Assets: {fund_assets:,} TWD, Units: {units:,}")
                    success_count += 1
                else:
                    print(f"  API returned error code: {resp_json.get('code')}")
            else:
                print(f"  HTTP error: {response.status_code}")
                
        except Exception as e:
            print(f"  Error backfilling date {d}: {e}")
            
        # Sleep to avoid WAF rate-limiting
        time.sleep(2)
        
    print(f"\nBackfill complete. Successfully backfilled holdings for {success_count} dates.")

if __name__ == "__main__":
    import requests # import here as it is needed
    backfill()
