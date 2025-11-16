# src/integrator.py

from typing import List, Dict, Any, Optional
import pandas as pd

from analyzer import QueryPlan
from llm_client import call_ollama, check_ollama_status


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
    if not check_ollama_status() or not results:
        return ""

    # Build a concise data summary
    data_summary = []
    for r in results[:5]:  # Limit to first 5 results
        data_summary.append(
            f"- {r['symbol']}: Price growth {r['price_growth']*100:.1f}%, "
            f"ROE {r['roe']:.1f}%, D/E {r['debt_equity_ratio']:.2f}, "
            f"P/E {r['pe_ratio']:.1f}"
        )

    prompt = f"""You are a financial analyst assistant. The user asked: "{nl_query}"

Based on the available data (2016-2017), here are the results:
{chr(10).join(data_summary)}

TASK: Provide a brief, relevant 2-3 sentence summary that:
1. Acknowledges if the query asks for data outside the available range (we only have 2016-2017)
2. Highlights key findings from the actual results
3. Keeps it concise and directly answers what the user asked

Do NOT provide generic information or boilerplate. Be specific to this query and these results."""

    try:
        summary = call_ollama(prompt, temperature=0.3, max_tokens=300)
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
                "price_growth": float(row.get("price_growth", 0.0)),
                "start_price": float(row.get("start_price", 0.0)),
                "end_price": float(row.get("end_price", 0.0)),
                "roe": float(row.get("roe", 0.0)),
                "debt_equity_ratio": float(row.get("debt_equity_ratio", 0.0)),
                "pe_ratio": float(row.get("pe_ratio", 0.0)),
                "current_ratio": float(row.get("current_ratio", 0.0)),
                "market_cap": float(row.get("market_cap", 0.0)),
            }
        )

    # Generate LLM summary of results
    llm_summary = ""
    if nl_query:
        llm_summary = generate_result_summary(
            nl_query, plan, df_price, df_fund, results
        )

    return results, llm_summary
