import sys
import argparse
import datetime
import db
import scraper
import ai_analysis

def run_sync(dry_run=False, force_ai=False):
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting Multi-ETF Sync Task...")
    
    # 1. Initialize DB
    if not dry_run:
        db.init_db()
        
    # Active ETFs to sync
    ACTIVE_ETFS = ["00997A", "00981A", "00403A", "00988A"]
    
    for etf_code in ACTIVE_ETFS:
        print(f"\n--- Syncing ETF: {etf_code} ---")
        
        nav_date = ""
        nav_val = 0.0
        change_pct = "0.0%"
        assets = None
        units = None
        holdings = []
        portfolio_date = ""
        news_items = []
        basic_info = None
        
        if etf_code == "00997A":
            # Scrape Basic NAV Info for 00997A
            print("Scraping basic NAV statistics...")
            try:
                basic_info = scraper.scrape_basic_nav()
                print(f"  NAV: {basic_info['nav']} TWD (Date: {basic_info['date']}, Change: {basic_info['change_percent']})")
                nav_date = basic_info["date"]
                nav_val = basic_info["nav"]
                change_pct = basic_info["change_percent"]
            except Exception as e:
                print(f"  Error scraping basic NAV: {e}")
                
            # Scrape Portfolio Holdings for 00997A
            print("Scraping portfolio holdings (PCF)...")
            try:
                portfolio_info = scraper.scrape_portfolio_holdings()
                print(f"  Portfolio Date: {portfolio_info['date']}")
                print(f"  Total Assets: {portfolio_info['fund_assets']:,} TWD")
                print(f"  Units Outstanding: {portfolio_info['outstanding_units']:,}")
                print(f"  Holdings Count: {len(portfolio_info['holdings'])}")
                portfolio_date = portfolio_info["date"]
                assets = portfolio_info["fund_assets"]
                units = portfolio_info["outstanding_units"]
                holdings = portfolio_info["holdings"]
            except Exception as e:
                print(f"  Error scraping portfolio: {e}")
                
            # Scrape Announcements for 00997A
            print("Scraping announcements...")
            try:
                news_items = scraper.scrape_announcements()
                print(f"  Announcements parsed: {len(news_items)}")
            except Exception as e:
                print(f"  Error scraping announcements: {e}")
        else:
            # Scrape Uni-President ETF (NAV & Holdings in one call)
            print(f"Scraping NAV and holdings for Uni-President ETF {etf_code}...")
            try:
                uni_info = scraper.scrape_uni_nav(etf_code)
                print(f"  NAV: {uni_info['nav']} TWD (Date: {uni_info['date']}, Change: {uni_info['change_percent']})")
                print(f"  Assets: {uni_info['fund_assets']:,} TWD | Outstanding Units: {uni_info['outstanding_units']:,}")
                print(f"  Holdings Count: {len(uni_info['holdings'])}")
                
                nav_date = uni_info["date"]
                nav_val = uni_info["nav"]
                change_pct = uni_info["change_percent"]
                assets = uni_info["fund_assets"]
                units = uni_info["outstanding_units"]
                holdings = uni_info["holdings"]
                portfolio_date = uni_info["date"]
                basic_info = uni_info
            except Exception as e:
                print(f"  Error scraping Uni-President ETF: {e}")
                continue

        if dry_run:
            print(f"[Dry Run] Sync completed for {etf_code}. No database updates made.")
            continue

        # Save NAV to DB
        if nav_date and nav_val:
            db.save_nav(
                etf_code=etf_code,
                date=nav_date,
                nav=nav_val,
                change_percent=change_pct,
                fund_assets=assets,
                outstanding_units=units
            )
            print(f"  Saved NAV data for date: {nav_date}")
            
        # Save Holdings to DB
        if holdings:
            db.save_holdings(etf_code, portfolio_date, holdings)
            print(f"  Saved {len(holdings)} holdings for date: {portfolio_date}")
            
        # Save Announcements to DB
        if news_items:
            db.save_announcements(etf_code, news_items)
            print(f"  Saved {len(news_items)} announcements")

        # Run AI Analysis if holdings changed
        if holdings:
            prev_date = db.get_previous_holdings_date(etf_code, portfolio_date)
            
            run_ai = force_ai
            comparison = None
            has_changes = True
            
            if prev_date:
                print(f"  Comparing holdings of {portfolio_date} with previous date {prev_date}...")
                prev_holdings = db.get_holdings_for_date(etf_code, prev_date)
                comparison = ai_analysis.compare_holdings(prev_holdings, holdings)
                
                has_changes = (
                    len(comparison["added"]) > 0 or 
                    len(comparison["removed"]) > 0 or 
                    len(comparison["changed"]) > 0
                )
                
                if has_changes:
                    print(f"    Detected changes: {len(comparison['added'])} added, {len(comparison['removed'])} removed, {len(comparison['changed'])} weight shifts.")
                    # Note: We do not automatically trigger AI generation during daily sync to save API TPM usage.
                    # The user can click the "AI分析" button on the dashboard to generate it on the fly.
                else:
                    print("    No holdings weight changes detected.")
            else:
                print("    No previous holdings date found in DB for comparison.")
                
            existing_analysis = db.get_ai_analysis(etf_code, portfolio_date)
            if existing_analysis and not force_ai:
                print(f"    AI analysis report already exists for {portfolio_date}. Skipping API call.")
                run_ai = False

            if run_ai:
                print(f"  Generating AI recommendations report for {portfolio_date}...")
                if not comparison:
                    comparison = {"added": [], "removed": [], "changed": []}
                    
                report = ai_analysis.generate_ai_analysis(
                    etf_code,
                    portfolio_date, 
                    comparison, 
                    basic_info, 
                    range_days=1, 
                    top_holdings=holdings
                )
                db.save_ai_analysis(etf_code, portfolio_date, report, range_days=1)
                print("    AI report successfully generated and saved to DB.")
            elif not has_changes and not existing_analysis:
                placeholder = (
                    f"### 💡 AI 操盤分析與行動建議 ({portfolio_date})\n\n"
                    f"成分股持倉組合相較前一交易日無任何異動（無新增、刪除或顯著權重微調）。\n\n"
                    f"**操盤建議**：經理人目前無換股動作，代表維持既有配置策略。建議長線配置投資人「**定期定額維持既有扣款節奏**」或「**續抱觀望**」，無須進行頻繁的短線調節。"
                )
                db.save_ai_analysis(etf_code, portfolio_date, placeholder, range_days=1)
                print("    Saved 'no changes' AI report placeholder.")
                
    print(f"\n[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Multi-ETF Sync Task completed successfully!\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Taiwan ETF Data Sync Task CLI")
    parser.add_argument("--dry-run", action="store_true", help="Scrape data but do not write to SQLite database")
    parser.add_argument("--force-ai", action="store_true", help="Force run Gemini API call even if no holdings change")
    args = parser.parse_args()
    
    run_sync(dry_run=args.dry_run, force_ai=args.force_ai)
