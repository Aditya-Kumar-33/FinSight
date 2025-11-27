# src/integrator.py

from typing import List, Dict, Any, Optional
import pandas as pd
import math

from analyzer import QueryPlan
from llm_client import call_ollama, check_ollama_status


def safe_float(value: Any) -> Optional[float]:
    """
    Convert a value to float, returning None for NaN values.
    This ensures proper JSON serialization.
    """
    try:
        f = float(value)
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None


def generate_result_summary(
    nl_query: str,
    plan: QueryPlan,
    df_price: pd.DataFrame,
    df_fund: pd.DataFrame,
    results: List[Dict[str, Any]],
) -> str:
    """
    Use LLM to generate a concise, relevant summary of the query results.
    """
    if not check_ollama_status():
        return ""

    if not results:
        return "No companies matched the specified criteria."

    # Build a concise data summary with actual values
    data_summary = []
    for r in results[:5]:  # Limit to first 5 results
        data_summary.append(
            f"- {r['symbol']}: Price grew {r['price_growth']*100:.1f}% "
            f"(from ₹{r['start_price']:.2f} to ₹{r['end_price']:.2f}), "
            f"ROE={r['roe']:.1f}%, D/E={r['debt_equity_ratio']:.2f}, P/E={r['pe_ratio']:.1f}"
        )

    prompt = f"""You are a financial data assistant. Answer ONLY based on the data provided below.

USER QUERY: "{nl_query}"

IMPORTANT FACTS:
- Database contains data ONLY for years 2012-2022
- Database contains ONLY close_price (NO volume/trading volume data)
- Available stocks: RELIANCE, HDFCBANK, TCS, INFY, etc.

ACTUAL QUERY RESULTS ({len(results)} {'company' if len(results) == 1 else 'companies'}):
{chr(10).join(data_summary)}

Date range queried: {plan.start_date} to {plan.end_date}

INSTRUCTIONS:
1. Write 2-3 sentences summarizing ONLY the data shown above
2. If user asked for data outside 2012-2022 or asked for volume, acknowledge this limitation
3. Use EXACT numbers from the results above - DO NOT make up or approximate values
4. We have data from 2012-2022 only - do NOT mention any other date range
5. Be factual and specific - no generic statements

CORRECT example: "For the query about RELIANCE in 2017, the stock showed 114.2% price growth from ₹196.43 to ₹420.77, with ROE of 0.12% and debt-equity ratio of 0.75."

WRONG example: "I'm sorry but data only covers 2012-2022..." (NEVER say this!)

Write your response now:"""

    try:
        summary = call_ollama(prompt, temperature=0.1, max_tokens=200)

        # Quick sanity check - if LLM mentions wrong years, return empty
        summary_lower = summary.lower()
        if any(year in summary_lower for year in ["2010", "2011", "2023", "2024"]):
            print("⚠️  LLM hallucinated incorrect years - suppressing summary")
            return ""

        return summary.strip()
    except Exception as e:
        print(f"Warning: Could not generate LLM summary: {e}")
        return ""


def integrate(
    plan: QueryPlan,
    df_price: pd.DataFrame,
    df_fund: pd.DataFrame,
    nl_query: Optional[str] = None,
) -> tuple[List[Dict[str, Any]], str]:
    """
    Integrate price and fundamentals data, apply filters, and generate summary.
    Returns: (results_list, llm_summary)
    """
    # focus on latest FY if multiple per symbol
    if "fy" in df_fund.columns and not df_fund.empty:
        df_fund = df_fund.sort_values(["symbol", "fy"]).drop_duplicates(
            "symbol", keep="last"
        )

    # Handle empty dataframes
    if df_price.empty:
        return [], "No price data found for the specified criteria."

    df = (
        pd.merge(df_price, df_fund, on="symbol", how="left")
        if not df_fund.empty
        else df_price
    )

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

        results.append(
            {
                "symbol": symbol,
                "price_growth": safe_float(row.get("price_growth", 0.0)),
                "start_price": safe_float(row.get("start_price", 0.0)),
                "end_price": safe_float(row.get("end_price", 0.0)),
                "roe": safe_float(row.get("roe", 0.0)),
                "debt_equity_ratio": safe_float(row.get("debt_equity_ratio", 0.0)),
                "pe_ratio": safe_float(row.get("pe_ratio", 0.0)),
                "current_ratio": safe_float(row.get("current_ratio", 0.0)),
                "market_cap": safe_float(row.get("market_cap", 0.0)),
            }
        )

    # Generate LLM summary of results
    llm_summary = ""
    if nl_query:
        llm_summary = generate_result_summary(
            nl_query, plan, df_price, df_fund, results
        )

    return results, llm_summary
