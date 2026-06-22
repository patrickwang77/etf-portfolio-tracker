import re
import datetime
import requests

BASE_URL = "https://www.capitalfund.com.tw"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Content-Type': 'application/json;charset=UTF-8',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://www.capitalfund.com.tw/etf/product/detail/502/basic'
}

def clean_date_str(date_str):
    if not date_str:
        return ""
    # Converts '2026/06/18' or '2026-06-18' to '2026-06-18'
    match = re.search(r'(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})', date_str)
    if match:
        return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    return date_str

def scrape_basic_nav():
    url = f"{BASE_URL}/CFWeb/api/etf/nav"
    response = requests.post(url, headers=HEADERS, json={}, timeout=15)
    response.raise_for_status()
    
    data = response.json()
    if data.get("code") != 200:
        raise Exception(f"API Error fetching NAV: {data.get('code')}")
        
    items = data.get("data", [])
    for item in items:
        # 502 is the fund ID for 00997A
        if str(item.get("fundId")) == "502" or item.get("stocNo") == "00997A":
            nav_val = item.get("navRound") or item.get("nav")
            change_pct = item.get("navChangeRatioRound") or f"{item.get('navChangeRatioDec', 0.0):.2f}%"
            date_str = clean_date_str(item.get("date1"))
            
            # Premium/Discount info
            diff_ratio = item.get("diffRatioRound") or f"{item.get('diffRatioDec', 0.0):.2f}%"
            
            return {
                "nav": float(nav_val) if nav_val else 0.0,
                "date": date_str,
                "change_percent": change_pct,
                "market_price": float(item.get("priceRound") or item.get("price") or 0.0),
                "premium_discount": diff_ratio,
                "dividend_frequency": "季配"  # 00997A is quarterly payout
            }
            
    # Fallback to empty structure
    return {
        "nav": 0.0,
        "date": datetime.date.today().strftime('%Y-%m-%d'),
        "change_percent": "0.0%",
        "market_price": 0.0,
        "premium_discount": "0.0%",
        "dividend_frequency": "季配"
    }

def scrape_portfolio_holdings():
    url = f"{BASE_URL}/CFWeb/api/etf/buyback"
    # fundId: 502 is for 00997A
    payload = {"fundId": "502"}
    response = requests.post(url, headers=HEADERS, json=payload, timeout=15)
    response.raise_for_status()
    
    data = response.json()
    if data.get("code") != 200:
        raise Exception(f"API Error fetching buyback: {data.get('code')}")
        
    pcf_data = data.get("data", {})
    pcf_summary = pcf_data.get("pcf", {})
    
    portfolio_data = {
        "fund_assets": int(pcf_summary.get("nav") or 0),
        "outstanding_units": int(pcf_summary.get("totUnit") or 0),
        "holdings": [],
        "other_assets": [],
        "bond_repos": [],
        "date": clean_date_str(pcf_summary.get("date1"))
    }
    
    # If API date is missing, default to today
    if not portfolio_data["date"]:
        portfolio_data["date"] = datetime.date.today().strftime('%Y-%m-%d')
        
    # Parse Stocks
    stocks_list = pcf_data.get("stocks", [])
    for s in stocks_list:
        code = s.get("stocNo", "").strip()
        # Decode possible URL/Unicode naming errors or use Ename as fallback
        name = s.get("stocName", "").strip()
        if not name or "" in name:
            name = s.get("stocEname", "").strip()
            
        weight = float(s.get("weight") or s.get("weightRound") or 0.0)
        shares = int(s.get("share") or 0)
        
        if code:
            portfolio_data["holdings"].append({
                "code": code,
                "name": name,
                "weight": weight,
                "shares": shares
            })
            
    # Parse Bond Repos (RPS)
    rps_list = pcf_data.get("rps", [])
    for r in rps_list:
        name = r.get("bondsName", "").strip()
        if not name or "" in name:
            name = r.get("bondsEname", "").strip()
            
        # Parse currency & value from "TWD 20,016,216.00"
        val_text = r.get("bondsMoney", "").strip()
        currency = "TWD"
        val_num = 0.0
        val_match = re.search(r'([A-Z]{3})\s*([\d\-\,\.]+)', val_text)
        if val_match:
            currency = val_match.group(1)
            val_num = float(val_match.group(2).replace(",", ""))
            
        portfolio_data["bond_repos"].append({
            "name": name,
            "value": val_num,
            "currency": currency
        })
        
    # Parse Other Assets
    assets_list = pcf_data.get("assets", [])
    for a in assets_list:
        name = a.get("asDesc", "").strip()
        if not name or "" in name:
            name = a.get("asEname", "").strip()
            
        val_text = a.get("asMoney", "").strip()
        currency = "TWD"
        val_num = 0.0
        val_match = re.search(r'([A-Z]{3})\s*([\d\-\,\.]+)', val_text)
        if val_match:
            currency = val_match.group(1)
            val_num = float(val_match.group(2).replace(",", ""))
            
        portfolio_data["other_assets"].append({
            "name": name,
            "value": val_num,
            "currency": currency
        })
        
    return portfolio_data

def scrape_announcements():
    # Crawl announcements page to get recent updates
    # The news list URL is parsed from the HTML layout
    url = f"{BASE_URL}/etf/product/news/list/0"
    html_headers = HEADERS.copy()
    # Remove JSON specific headers for the HTML page
    html_headers.pop('Content-Type', None)
    
    response = requests.get(url, headers=html_headers, timeout=15)
    response.raise_for_status()
    
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(response.text, "html.parser")
    news_items = []
    
    # Find links pointing to details
    links = soup.find_all("a", href=re.compile(r"news/detail"))
    for link in links:
        title = link.get_text().strip()
        href = link.get("href")
        date_str = ""
        
        # Traverse up parent elements to find news date
        parent = link.parent
        for _ in range(4):
            if not parent:
                break
            date_match = re.search(r'\d{4}[/\-\.]\d{2}[/\-\.]\d{2}', parent.get_text())
            if date_match:
                date_str = date_match.group(0)
                break
                
        if title and href:
            news_items.append({
                "title": title,
                "url": BASE_URL + href if href.startswith("/") else href,
                "date": clean_date_str(date_str)
            })
            
    # Deduplicate and filter for relevant 00997A items
    seen_urls = set()
    deduped_news = []
    for item in news_items:
        if item["url"] not in seen_urls:
            title_upper = item["title"].upper()
            # If 00997A or "美國增長" is mentioned, prioritize it
            if "00997" in title_upper or "美國增長" in item["title"] or "主動" in item["title"]:
                deduped_news.append(item)
                seen_urls.add(item["url"])
            elif len(deduped_news) < 8: # Or keep generic announcements up to 8 items
                deduped_news.append(item)
                seen_urls.add(item["url"])
                    
    return deduped_news

UNI_FUND_MAPPING = {
    "00981A": "49YTW",
    "00403A": "63YTW",
    "00988A": "61YTW"
}

def scrape_uni_nav(etf_code):
    fund_code = UNI_FUND_MAPPING.get(etf_code)
    if not fund_code:
        raise Exception(f"Unsupported Uni-President ETF code: {etf_code}")
        
    url = f"https://www.ezmoney.com.tw/ETF/Fund/Info?fundCode={fund_code}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    
    # We want to make sure the response is decoded correctly
    response.encoding = response.apparent_encoding or 'utf-8'
    
    from bs4 import BeautifulSoup
    import json
    import html
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Extract asset data
    el_asset = soup.find(id="DataAsset")
    if not el_asset:
        raise Exception(f"Element with id='DataAsset' not found on page for {etf_code}")
        
    unescaped_asset = html.unescape(el_asset.get("data-content", ""))
    asset_data = json.loads(unescaped_asset)
    
    nav = 0.0
    edit_date = ""
    fund_assets = 0.0
    outstanding_units = 0.0
    holdings_list = []
    
    for item in asset_data:
        code = item.get("AssetCode")
        val = item.get("Value")
        if code == "P_UNIT":
            nav = float(val) if val else 0.0
            edit_date = item.get("EditDate", "")
        elif code == "NAV":
            fund_assets = float(val) if val else 0.0
        elif code == "OUT_UNIT":
            outstanding_units = float(val) if val else 0.0
        elif code == "ST":
            details = item.get("Details") or []
            for d in details:
                holdings_list.append({
                    "code": d.get("DetailCode", "").strip(),
                    "name": d.get("DetailName", "").strip(),
                    "weight": float(d.get("NavRate") or 0.0),
                    "shares": int(d.get("Share") or 0)
                })
                
    # Sort holdings by weight descending
    holdings_list.sort(key=lambda x: x["weight"], reverse=True)
            
    # Search table for change percentage and business date
    change_pct = "0.0%"
    table_date = ""
    
    for tr in soup.find_all("tr"):
        tds = [td.get_text().strip() for td in tr.find_all(["td", "th"])]
        if len(tds) >= 5 and etf_code in tds[1]:
            table_date = tds[0]
            change_pct = tds[4]
            break
            
    # Determine the business date
    business_date = ""
    if table_date and edit_date:
        match_year = re.match(r'(\d{4})', edit_date)
        if match_year:
            year = int(match_year.group(1))
            match_md = re.search(r'(\d{1,2})/(\d{1,2})', table_date)
            if match_md:
                month = int(match_md.group(1))
                day = int(match_md.group(2))
                
                # Rollback year if edit_date is Jan and table_date is Dec
                match_edit_m = re.search(r'^\d{4}[/\-\.](\d{1,2})', edit_date)
                if match_edit_m:
                    edit_month = int(match_edit_m.group(1))
                    if edit_month == 1 and month == 12:
                        year -= 1
                business_date = f"{year:04d}-{month:02d}-{day:02d}"
                
    if not business_date:
        if edit_date:
            business_date = clean_date_str(edit_date.split("T")[0])
        else:
            business_date = datetime.date.today().strftime('%Y-%m-%d')
            
    return {
        "nav": nav,
        "date": business_date,
        "change_percent": change_pct,
        "fund_assets": fund_assets,
        "outstanding_units": outstanding_units,
        "holdings": holdings_list
    }

if __name__ == "__main__":
    print("Testing Updated API-Based Scraper...")
    try:
        basic = scrape_basic_nav()
        print("Basic NAV Data:")
        for k, v in basic.items():
            print(f"  {k}: {v}")
            
        portfolio = scrape_portfolio_holdings()
        print("\nPortfolio Summary:")
        print(f"  Date: {portfolio['date']}")
        print(f"  Fund Assets: {portfolio['fund_assets']:,} TWD")
        print(f"  Outstanding Units: {portfolio['outstanding_units']:,}")
        print(f"  Holdings Count: {len(portfolio['holdings'])}")
        if portfolio['holdings']:
            print("  Top 3 Holdings:")
            for i, h in enumerate(portfolio['holdings'][:3]):
                print(f"    {i+1}. {h['code']} - {h['name']}: {h['weight']}% ({h['shares']:,} shares)")
                
        print("\nBond Repos Count:", len(portfolio["bond_repos"]))
        print("Other Assets Count:", len(portfolio["other_assets"]))
        
        news = scrape_announcements()
        print(f"\nAnnouncements Count: {len(news)}")
        if news:
            print("  Latest Announcement:", news[0])
            
        print("\nTesting Uni-President Scrapers:")
        for uni_code in ["00981A", "00403A", "00988A"]:
            print(f"\nScraping {uni_code}...")
            uni_data = scrape_uni_nav(uni_code)
            for k, v in uni_data.items():
                if k == "holdings":
                    print(f"  {k} Count: {len(v)}")
                    if v:
                        print(f"    Top Holding: {v[0]}")
                else:
                    print(f"  {k}: {v}")
            
        print("\nAll Scraper operations completed successfully!")
    except Exception as e:
        print("\nScraper operations failed:", e)
