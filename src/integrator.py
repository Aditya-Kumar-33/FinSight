# src/integrator.py

from typing import List, Dict, Any
import pandas as pd

from analyzer import QueryPlan
from llm_client import build_llm_prompt, call_llm, load_report_text


def integrate(plan: QueryPlan, df_price: pd.DataFrame, df_fund: pd.DataFrame) -> List[Dict[str, Any]]:
    # focus on latest FY if multiple per symbol
    if "fy" in df_fund.columns:
        df_fund = df_fund.sort_values(["symbol", "fy"]).drop_duplicates("symbol", keep="last")

    df = pd.merge(df_price, df_fund, on="symbol", how="left")

    # Apply thresholds parsed from NL query
    if plan.min_price_growth is not None:
        df = df[df["price_growth"] >= plan.min_price_growth]

    if plan.max_debt_equity is not None and "debt_equity_ratio" in df.columns:
        df = df[df["debt_equity_ratio"] <= plan.max_debt_equity]

    if plan.min_roe is not None and "roe" in df.columns:
        df = df[df["roe"] >= plan.min_roe]

    if plan.max_pe is not None and "pe_ratio" in df.columns:
        df = df[df["pe_ratio"] <= plan.max_pe]

    results = []

    for _, row in df.iterrows():
        symbol = row["symbol"]

        # optional LLM part: read pre-saved annual report text
        report_text = load_report_text(symbol, plan.fy or 2017)
        prompt = build_llm_prompt(symbol, report_text)
        llm_summary = call_llm(prompt)

        results.append({
            "symbol": symbol,
            "price_growth": float(row["price_growth"]),
            "start_price": float(row["start_price"]),
            "end_price": float(row["end_price"]),
            "roe": float(row.get("roe") or 0.0),
            "debt_equity_ratio": float(row.get("debt_equity_ratio") or 0.0),
            "pe_ratio": float(row.get("pe_ratio") or 0.0),
            "current_ratio": float(row.get("current_ratio") or 0.0),
            "market_cap": float(row.get("market_cap") or 0.0),
            "llm_commentary": llm_summary,
        })

    return results
