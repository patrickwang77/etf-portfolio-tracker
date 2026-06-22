import os
import sys
import subprocess
from flask import Flask, jsonify, request, send_from_directory
from dotenv import load_dotenv

# Ensure backend directory is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import db
import scraper
import ai_analysis
import daily_scrape

# Load environment variables
load_dotenv()

# We serve static files directly from the sibling "frontend" directory
app = Flask(__name__, static_folder="../frontend", static_url_path="")

@app.route("/")
def index():
    return app.send_static_file("index.html")

@app.route("/api/summary")
def get_summary():
    try:
        etf_code = request.args.get("etf", default="00997A")
        latest_nav = db.get_latest_nav(etf_code)
        latest_units = db.get_latest_personal_units(etf_code)
        
        if not latest_nav:
            # Fallback empty structure if no data crawled
            latest_nav = {
                "date": "N/A", "nav": 0.0, "change_percent": "0.0%",
                "fund_assets": 0, "outstanding_units": 0
            }
            
        nav = latest_nav.get("nav", 0.0)
        portfolio_value = nav * latest_units
        
        # Calculate daily change in portfolio value
        # Find previous NAV
        nav_history = db.get_nav_history(etf_code, limit=2)
        prev_nav = 0.0
        if len(nav_history) >= 2:
            prev_nav = nav_history[0]["nav"]
            
        prev_portfolio_value = prev_nav * latest_units
        portfolio_change_amt = portfolio_value - prev_portfolio_value
        portfolio_change_pct = f"{(portfolio_change_amt / prev_portfolio_value * 100):.2f}%" if prev_portfolio_value > 0 else "0.00%"
        
        return jsonify({
            "success": True,
            "nav_date": latest_nav.get("date"),
            "nav": nav,
            "change_percent": latest_nav.get("change_percent"),
            "fund_assets": latest_nav.get("fund_assets"),
            "outstanding_units": latest_nav.get("outstanding_units"),
            "personal_units": latest_units,
            "portfolio_value": portfolio_value,
            "portfolio_change_amount": portfolio_change_amt,
            "portfolio_change_percent": portfolio_change_pct
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/holdings")
def get_holdings():
    try:
        etf_code = request.args.get("etf", default="00997A")
        latest_date = db.get_latest_holdings_date(etf_code)
        if not latest_date:
            return jsonify({"success": True, "date": "N/A", "holdings": [], "changes": {}})
            
        holdings = db.get_holdings_for_date(etf_code, latest_date)
        
        # Compute changes compared to previous recorded holdings date
        prev_date = db.get_previous_holdings_date(etf_code, latest_date)
        changes = {"added": [], "removed": [], "changed": []}
        
        if prev_date:
            prev_holdings = db.get_holdings_for_date(etf_code, prev_date)
            changes = ai_analysis.compare_holdings(prev_holdings, holdings)
            
        return jsonify({
            "success": True,
            "date": latest_date,
            "previous_date": prev_date,
            "holdings": holdings,
            "changes": changes
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/history")
def get_history():
    try:
        etf_code = request.args.get("etf", default="00997A")
        limit = request.args.get("limit", default=45, type=int)
        history = db.get_nav_history(etf_code, limit=limit)
        latest_units = db.get_latest_personal_units(etf_code)
        
        # Format response for frontend charts
        formatted_history = []
        for h in history:
            nav = h.get("nav", 0.0)
            formatted_history.append({
                "date": h.get("date"),
                "nav": nav,
                "portfolio_value": nav * latest_units,
                "fund_assets": h.get("fund_assets"),
                "outstanding_units": h.get("outstanding_units")
            })
            
        return jsonify({
            "success": True,
            "history": formatted_history
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/announcements")
def get_announcements():
    try:
        etf_code = request.args.get("etf", default="00997A")
        limit = request.args.get("limit", default=20, type=int)
        items = db.get_announcements(etf_code, limit=limit)
        return jsonify({
            "success": True,
            "announcements": items
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/ai-analysis")
def get_ai_report():
    try:
        etf_code = request.args.get("etf", default="00997A")
        latest_date = db.get_latest_holdings_date(etf_code)
        if not latest_date:
            return jsonify({"success": True, "date": "N/A", "report": "暫無持股數據，無法生成 AI 分析。"})
            
        range_days = request.args.get("range", default=1, type=int)
        force = request.args.get("force", default=0, type=int)
        
        report = None if force else db.get_ai_analysis(etf_code, latest_date, range_days)
        if not report:
            if not force:
                return jsonify({
                    "success": True,
                    "date": latest_date,
                    "range_days": range_days,
                    "report": None
                })
            # Generate one on the fly if missing
            holdings = db.get_holdings_for_date(etf_code, latest_date)
            comp_date = db.get_holdings_date_at_offset(etf_code, latest_date, range_days)
            comparison = {"added": [], "removed": [], "changed": []}
            if comp_date and comp_date != latest_date:
                comp_holdings = db.get_holdings_for_date(etf_code, comp_date)
                comparison = ai_analysis.compare_holdings(comp_holdings, holdings)
            
            basic_info = db.get_latest_nav(etf_code)
            report = ai_analysis.generate_ai_analysis(etf_code, latest_date, comparison, basic_info, range_days, holdings)
            db.save_ai_analysis(etf_code, latest_date, report, range_days)
            
        return jsonify({
            "success": True,
            "date": latest_date,
            "range_days": range_days,
            "report": report
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/sync", methods=["POST"])
def trigger_sync():
    try:
        # Run daily_scrape.py orchestrator sync
        force_ai = request.json.get("force_ai", False) if request.is_json else False
        daily_scrape.run_sync(force_ai=force_ai)
        return jsonify({"success": True, "message": "數據同步完成！"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/settings", methods=["POST"])
def save_settings():
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "Missing payload"}), 400
            
        # We determine which ETF settings are being saved (default to 00997A)
        etf_code = data.get("etf", "00997A")
        
        # 1. Update personal holdings units
        if "personal_units" in data:
            try:
                units = float(data["personal_units"])
                db.save_personal_units(etf_code, units)
            except ValueError:
                return jsonify({"success": False, "error": "單位數格式錯誤"}), 400
                
        # 2. Update Gemini API Key
        if "gemini_key" in data:
            key_val = data["gemini_key"].strip()
            env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
            
            # Read existing .env lines
            lines = []
            key_replaced = False
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip().startswith("GEMINI_API_KEY="):
                            lines.append(f"GEMINI_API_KEY={key_val}\n")
                            key_replaced = True
                        else:
                            lines.append(line)
                            
            if not key_replaced:
                lines.append(f"GEMINI_API_KEY={key_val}\n")
                
            # Write back
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
                
            # Reload environment variable in current process
            os.environ["GEMINI_API_KEY"] = key_val
            
        return jsonify({"success": True, "message": "設定已成功儲存！"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    db.init_db()
    # Run server locally on port 5000
    print("Starting Web Application Dashboard on http://localhost:5000")
    app.run(host="127.0.0.1", port=5000, debug=True)
