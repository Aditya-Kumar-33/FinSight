# src/integrator.py

import math
from typing import List, Dict, Any, Optional
import pandas as pd

from analyzer import QueryPlan
from llm_client import call_ollama, check_ollama_status


def compute_daily_returns(price_df: pd.DataFrame) -> pd.DataFrame:
    """
    Expects columns: symbol, trade_date, close_price.
    Returns DataFrame with an added daily_return column per symbol.
    """
    required_cols = {"symbol", "trade_date", "close_price"}
    if price_df is None or price_df.empty or not required_cols.issubset(
        price_df.columns
    ):
        return pd.DataFrame(columns=list(required_cols) + ["daily_return"])

    df = price_df.copy()
    df = df.sort_values(["symbol", "trade_date"])
    # Using pct_change directly on the grouped series keeps the original index alignment
    df["daily_return"] = df.groupby("symbol")["close_price"].pct_change()
    return df


def compute_volatility_and_max_drawdown(
    price_df: pd.DataFrame,
) -> Dict[str, Dict[str, float]]:
    """
    Given per-day prices (symbol, trade_date, close_price),
    return a dict: { symbol: { "volatility": float, "max_drawdown": float } }.
    Volatility: std of daily_return. Max drawdown: largest drop from rolling peak.
    """
    metrics: Dict[str, Dict[str, float]] = {}
    required_cols = {"symbol", "trade_date", "close_price"}
    if price_df is None or price_df.empty or not required_cols.issubset(
        price_df.columns
    ):
        return metrics

    df_returns = compute_daily_returns(price_df)
    for symbol, grp in df_returns.groupby("symbol"):
        returns = grp["daily_return"].dropna()
        volatility = returns.std() if not returns.empty else 0.0

        prices = grp.sort_values("trade_date")["close_price"]
        if prices.empty:
            metrics[symbol] = {"volatility": float(volatility), "max_drawdown": 0.0}
            continue

        running_max = prices.cummax()
        drawdowns = (prices / running_max) - 1.0
        max_drawdown = abs(drawdowns.min()) if not drawdowns.empty else 0.0

        # Guard against NaNs/infs
        metrics[symbol] = {
            "volatility": float(volatility) if math.isfinite(volatility) else 0.0,
            "max_drawdown": float(max_drawdown) if math.isfinite(max_drawdown) else 0.0,
        }

    return metrics


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
        growth = (
            f"{(r['price_growth'] or 0) * 100:.1f}%"
            if r.get("price_growth") is not None
            else "n/a"
        )
        start_price = (
            f"{r['start_price']:.2f}" if r.get("start_price") is not None else "n/a"
        )
        end_price = (
            f"{r['end_price']:.2f}" if r.get("end_price") is not None else "n/a"
        )
        roe = f"{r['roe']:.1f}%" if r.get("roe") is not None else "n/a"
        de = (
            f"{r['debt_equity_ratio']:.2f}"
            if r.get("debt_equity_ratio") is not None
            else "n/a"
        )
        pe = f"{r['pe_ratio']:.1f}" if r.get("pe_ratio") is not None else "n/a"
        cr = (
            f"{r['current_ratio']:.2f}"
            if r.get("current_ratio") is not None
            else "n/a"
        )
        mc = f"{r['market_cap']:.0f}" if r.get("market_cap") is not None else "n/a"
        vol = (
            f"{r['volatility']:.4f}" if r.get("volatility") is not None else "n/a"
        )
        mdd = (
            f"{r['max_drawdown']:.4f}" if r.get("max_drawdown") is not None else "n/a"
        )

        data_summary.append(
            f"- {r['symbol']}: price {start_price} -> {end_price} ({growth}), "
            f"ROE={roe}, D/E={de}, P/E={pe}, CurrRatio={cr}, MktCap={mc}, "
            f"Volatility={vol}, MaxDrawdown={mdd}"
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
1. Write 2-3 sentences summarizing ONLY the data shown above.
2. Discuss both performance (growth/ROE/PE/debt) and risk metrics (volatility, max drawdown) for each stock.
3. You may only use the numbers shown in ACTUAL QUERY RESULTS; do NOT invent any numbers, years, or metrics.
4. Data is valid only for fiscal years 2012-2022 and the provided date range; do NOT mention years outside this range.
5. Be factual and specific - no generic statements. For each stock, explain in one line why it looks attractive or risky given growth, leverage, valuation, and risk metrics.

Write your response now:"""

    try:
        summary = call_ollama(prompt, temperature=0.1, max_tokens=200)

        # Quick sanity check - if LLM mentions wrong years, return empty
        summary_lower = summary.lower()
        if any(year in summary_lower for year in ["2010", "2011", "2023", "2024"]):
            print("Warning: LLM hallucinated incorrect years - suppressing summary")
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

    from analyzer import ALL_SYMBOLS
    df = df[df["symbol"].isin(ALL_SYMBOLS)]

    # Apply thresholds parsed from NL query
    if plan.min_price_growth is not None and "price_growth" in df.columns:
        df = df[df["price_growth"] >= plan.min_price_growth]

    if plan.max_debt_equity is not None and "debt_equity_ratio" in df.columns:
        df = df[df["debt_equity_ratio"] <= plan.max_debt_equity]

    if plan.min_roe is not None and "roe" in df.columns:
        df = df[df["roe"] >= plan.min_roe]

    if plan.max_pe is not None and "pe_ratio" in df.columns:
        df = df[df["pe_ratio"] <= plan.max_pe]

    # Gather daily prices for risk metrics
    price_for_risk = df_price
    required_cols = {"symbol", "trade_date", "close_price"}
    if price_for_risk is None or price_for_risk.empty or not required_cols.issubset(
        price_for_risk.columns
    ):
        try:
            from db_utils import query_price_db

            symbol_filter = ""
            if plan.symbols:
                in_list = ", ".join(f"'{s}'" for s in plan.symbols)
                symbol_filter = f"AND symbol IN ({in_list})"

            price_for_risk = query_price_db(
                f"""
                SELECT symbol, trade_date, close_price
                FROM prices
                WHERE trade_date BETWEEN '{plan.start_date}' AND '{plan.end_date}'
                {symbol_filter}
                ORDER BY symbol, trade_date
                """
            )
        except Exception as e:
            if hasattr(plan, "warnings"):
                plan.warnings.append(f"Could not fetch daily prices for risk metrics: {e}")
            price_for_risk = pd.DataFrame(columns=list(required_cols))

    # Ensure date filtering for risk metrics
    if not price_for_risk.empty and "trade_date" in price_for_risk.columns:
        try:
            price_for_risk["trade_date"] = pd.to_datetime(price_for_risk["trade_date"])
            price_for_risk = price_for_risk[
                (price_for_risk["trade_date"] >= pd.to_datetime(plan.start_date))
                & (price_for_risk["trade_date"] <= pd.to_datetime(plan.end_date))
            ]
        except Exception:
            pass

    vol_dd = compute_volatility_and_max_drawdown(price_for_risk)

    def _safe_number(value: Any) -> Optional[float]:
        """
        Convert a value to float if it's a real number; otherwise return None so JSON stays valid.
        """
        try:
            num = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(num):
            return None
        return num

    results = []

    for _, row in df.iterrows():
        symbol = row["symbol"]
        risk_metrics = vol_dd.get(symbol, {})

        results.append(
            {
                "symbol": symbol,
                "price_growth": _safe_number(row.get("price_growth")),
                "start_price": _safe_number(row.get("start_price")),
                "end_price": _safe_number(row.get("end_price")),
                "roe": _safe_number(row.get("roe")),
                "debt_equity_ratio": _safe_number(row.get("debt_equity_ratio")),
                "pe_ratio": _safe_number(row.get("pe_ratio")),
                "current_ratio": _safe_number(row.get("current_ratio")),
                "market_cap": _safe_number(row.get("market_cap")),
                "volatility": _safe_number(risk_metrics.get("volatility")),
                "max_drawdown": _safe_number(risk_metrics.get("max_drawdown")),
            }
        )

    # Generate LLM summary of results
    llm_summary = ""
    if nl_query:
        llm_summary = generate_result_summary(
            nl_query, plan, df_price, df_fund, results
        )

    return results, llm_summary
