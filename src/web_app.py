import json
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory

from services import execute_query
from llm_client import check_ollama_status
from db_utils import query_price_db, query_fund_db

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR.parent / "web"

app = Flask(__name__, static_folder=str(WEB_DIR))


@app.route("/api/health", methods=["GET"])
def health():
    db_ok = True
    messages = []
    try:
        query_price_db("SELECT 1")
        query_fund_db("SELECT 1")
    except Exception as e:
        db_ok = False
        messages.append(f"DB check failed: {e}")
    ollama_ok = check_ollama_status()
    return (
        jsonify(
            {
                "status": "ok" if db_ok else "degraded",
                "db_ok": db_ok,
                "ollama_ok": ollama_ok,
                "messages": messages,
            }
        ),
        200 if db_ok else 503,
    )


@app.route("/api/query", methods=["POST"])
def api_query():
    try:
        payload = request.get_json(force=True, silent=False) or {}
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    nl_query = (payload.get("nl_query") or "").strip()
    if not nl_query:
        return jsonify({"error": "nl_query cannot be empty"}), 400

    try:
        plan, results, llm_summary = execute_query(nl_query)
    except Exception as e:
        return jsonify({"error": f"Query failed: {e}"}), 500

    plan_summary = {
        "start_date": str(plan.start_date),
        "end_date": str(plan.end_date),
        "symbols": plan.symbols,
        "fy": plan.fy,
        "min_price_growth": plan.min_price_growth,
        "max_debt_equity": plan.max_debt_equity,
        "min_roe": plan.min_roe,
        "max_pe": plan.max_pe,
    }

    return jsonify(
        {"results": results, "llm_summary": llm_summary, "plan": plan_summary}
    )


@app.route("/", methods=["GET"])
def index():
    return send_from_directory(str(WEB_DIR), "index.html")


if __name__ == "__main__":
    # How to run (dev):
    # 1) docker compose -f db/docker-compose.yml up -d
    # 2) pip install -r requirements.txt  (ensure Flask is installed)
    # 3) python src/web_app.py
    # 4) open http://localhost:5000
    app.run(host="0.0.0.0", port=5000, debug=True)
