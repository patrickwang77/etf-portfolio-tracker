import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# We use direct HTTP requests to call Gemini API, avoiding complex SDKs
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent"

def get_api_key():
    # Attempt to load from environment variable
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        # Fallback: check if we can read from .env file directly in parent workspace folder
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("GEMINI_API_KEY="):
                        return line.strip().split("=", 1)[1].strip().strip('"\'')
    return key

def compare_holdings(prev_holdings, curr_holdings):
    """
    Compares two holdings lists and returns differences.
    Each holdings list is a list of dicts: [{'code': '...', 'name': '...', 'weight': 6.78, 'shares': 1234}]
    """
    prev_map = {h['code']: h for h in prev_holdings}
    curr_map = {h['code']: h for h in curr_holdings}
    
    added = []
    removed = []
    changed = []
    
    # 1. Check for additions and changes
    for code, curr in curr_map.items():
        if code not in prev_map:
            added.append({
                "code": code,
                "name": curr["name"],
                "weight": curr["weight"],
                "shares": curr["shares"]
            })
        else:
            prev = prev_map[code]
            weight_diff = curr["weight"] - prev["weight"]
            # We record a change if the absolute weight difference is greater than 0.01%
            if abs(weight_diff) >= 0.01:
                changed.append({
                    "code": code,
                    "name": curr["name"],
                    "prev_weight": prev["weight"],
                    "curr_weight": curr["weight"],
                    "weight_change": weight_diff,
                    "prev_shares": prev["shares"],
                    "curr_shares": curr["shares"],
                    "shares_change": curr["shares"] - prev["shares"]
                })
                
    # 2. Check for removals
    for code, prev in prev_map.items():
        if code not in curr_map:
            removed.append({
                "code": code,
                "name": prev["name"],
                "weight": prev["weight"],
                "shares": prev["shares"]
            })
            
    # Sort changes by absolute magnitude
    changed.sort(key=lambda x: abs(x["weight_change"]), reverse=True)
    
    return {
        "added": added,
        "removed": removed,
        "changed": changed
    }

def generate_ai_analysis(etf_code, date, comparison, nav_info=None, range_days=1, top_holdings=None):
    """
    Generates AI analysis and recommendations for ETF holding shifts over 1D, 5D, or 10D ranges
    """
    api_key = get_api_key()
    if not api_key:
        return (
            f"### 💡 AI {range_days}日操盤分析與行動建議\n\n"
            "尚未設定 Gemini API Key。\n\n"
            "請前往系統「系統設定 (Settings)」分頁，輸入您的 **Gemini API Key**，即可啟用自動成分股持倉分析與行動建議系統。"
        )
        
    etf_names = {
        "00997A": "群益美國增長主動式ETF",
        "00981A": "統一台股增長主動式ETF",
        "00403A": "統一升級50主動式ETF",
        "00988A": "統一全球創新主動式ETF"
    }
    etf_name = etf_names.get(etf_code, "主動式 ETF")
    
    # Constructing prompt detailing holding changes
    prompt = (
        f"您是一位頂尖的量化基金與主動式 ETF (Active ETF) 投資分析專家。 {etf_code} 是一款台灣發行的「{etf_name}」。\n"
        f"我們監測到了該 ETF 在 {date} 的持股成分與權重在過去 {range_days} 個交易日中產生了調整，以下是變動與當前持倉細節：\n\n"
    )
    
    # Add NAV stats if available
    if nav_info:
        prompt += (
            f"【最新淨值資訊】\n"
            f"- 淨值日期: {nav_info.get('date')}\n"
            f"- 當日淨值: {nav_info.get('nav')} TWD\n"
            f"- 當日漲跌: {nav_info.get('change_percent')}\n"
            f"- 溢價/折價率: {nav_info.get('premium_discount', 'N/A')}\n\n"
        )
        
    # Add Top Holdings details if provided
    if top_holdings:
        prompt += "【目前前十大核心持倉 (Top 10 Core Holdings)】\n"
        for i, h in enumerate(top_holdings[:10]):
            prompt += f"  {i+1}. {h['code']} ({h['name']}): 權重 {h['weight']:.4f}% (股數: {h['shares']:,})\n"
        prompt += "\n"
        
    prompt += f"【過去 {range_days} 個交易日內持股變動細節】\n"
    
    # 1. Additions
    if comparison["added"]:
        prompt += "■ 新增持股：\n"
        for item in comparison["added"]:
            prompt += f"  - {item['code']} ({item['name']}): 權重 {item['weight']}% (股數: {item['shares']:,})\n"
    else:
        prompt += "■ 新增持股：無\n"
        
    # 2. Removals
    if comparison["removed"]:
        prompt += "\n■ 刪除持股：\n"
        for item in comparison["removed"]:
            prompt += f"  - {item['code']} ({item['name']}): 權重 {item['weight']}% (股數: {item['shares']:,})\n"
    else:
        prompt += "\n■ 刪除持股：無\n"
        
    # 3. Changes
    if comparison["changed"]:
        prompt += "\n■ 權重顯著調整（由大至小排序）：\n"
        # List top 15 changes to keep prompt size reasonable
        for item in comparison["changed"][:15]:
            sign = "+" if item["weight_change"] > 0 else ""
            prompt += (
                f"  - {item['code']} ({item['name']}): 權重由 {item['prev_weight']}% 調整至 {item['curr_weight']}% "
                f"(變動: {sign}{item['weight_change']:.4f}%) "
                f"[股數變動: {item['shares_change']:+,} 股]\n"
            )
            
    prompt += (
        f"\n請根據以上過去 {range_days} 個交易日的持股異動，以及前十大核心持倉結構，為投資人撰寫一份專業的【主動式 ETF {range_days}日操盤動向與個人行動建議分析】。\n"
        "報告必須使用繁體中文撰寫，包含以下三個核心章節：\n"
        "1. **操盤經理人核心動向與換股戰術解讀**：分析經理人在過去這段時間內加減倉、換股背後的宏觀經濟、產業發展邏輯與戰術意圖。\n"
        "2. **前十大主要持股剖析（優點與注意風險）**：針對前十大主要持股，深入點出此 ETF 集中配置這些主要股票的**核心優點**，以及**後續需特別注意的風險與看法**。\n"
        "3. **個人投資行動建議**：針對「已持有該 ETF 單位數進行長期資產配置的散戶投資人」，給出具體且客觀的應對建議（例如：增持、減持、定期定額維持、或觀望等行動指南與觀察要點）。"
    )

    try:
        url = f"{GEMINI_URL}?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.95,
                "maxOutputTokens": 8192
            }
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        resp_json = response.json()
        recommendation = resp_json["candidates"][0]["content"]["parts"][0]["text"]
        return recommendation
        
    except Exception as e:
        return (
            f"### ❌ AI {range_days}日操盤分析與行動建議\n\n"
            f"呼叫 Gemini API 時發生錯誤：\n"
            f"```text\n{str(e)}\n```\n\n"
            f"請確認您的 API Key 是否正確且具有 Gemini 3.5 Flash 存取權限。"
        )

if __name__ == "__main__":
    # Test compare function
    prev = [{"code": "MU US", "name": "美光", "weight": 6.78, "shares": 27000}]
    curr = [{"code": "MU US", "name": "美光", "weight": 7.10, "shares": 29000}, {"code": "NVDA US", "name": "輝達", "weight": 1.20, "shares": 5000}]
    comp = compare_holdings(prev, curr)
    print("Test Comparison:", comp)
