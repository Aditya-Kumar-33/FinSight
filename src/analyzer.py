# analyzer.py
from dataclasses import dataclass
from datetime import date
from typing import Optional, List, Tuple
from dateutil.relativedelta import relativedelta
import re
import json

ALL_SYMBOLS = [
    "RELIANCE",
    "HDFCBANK",
    "BHARTIARTL",
    "TCS",
    "ICICIBANK",
    "SBIN",
    "BAJFINANCE",
    "INFY",
    "HINDUNILVR",
]


@dataclass
class QueryPlan:
    start_date: date
    end_date: date
    symbols: Optional[List[str]]
    min_price_growth: Optional[float]
    max_debt_equity: Optional[float]
    min_roe: Optional[float]
    max_pe: Optional[float]
    fy: Optional[int]

    # will be filled by build_sql()
    sql_price: Optional[str] = None
    sql_fund: Optional[str] = None


# ------------ LLM-based query analyzer ------------


def build_nl_to_sql_prompt(nl_query: str) -> str:
    """
    Build a comprehensive prompt for the LLM to convert natural language to query parameters.
    """
    prompt = f"""You are a financial data query analyzer. Convert the following natural language query into structured parameters for querying stock market databases.

DATABASE SCHEMA:
1. prices table: (symbol, trade_date, close_price)
2. fundamentals table: (symbol, fy, roe, debt_equity_ratio, current_ratio, pe_ratio, pb_ratio, market_cap)

AVAILABLE SYMBOLS: {', '.join(ALL_SYMBOLS)}

USER QUERY: "{nl_query}"

TASK: Extract the following parameters from the query. If a parameter is not mentioned, use null.

Return ONLY a valid JSON object with these exact fields:
{{
  "start_date": "YYYY-MM-DD format or null",
  "end_date": "YYYY-MM-DD format or null",
  "symbols": ["SYMBOL1", "SYMBOL2"] or null,
  "min_price_growth": 0.20 (as decimal, e.g., 20% = 0.20) or null,
  "max_debt_equity": 1.0 or null,
  "min_roe": 15.0 or null,
  "max_pe": 25.0 or null,
  "fy": 2016 or 2017 or null
}}

RULES:
- Dates: If year mentioned (e.g., "2017"), use "2017-01-01" to "2017-12-31"
- If "last year" or "past year", use 2017-01-01 to 2017-12-31
- Default date range if not specified: 2016-01-01 to 2017-12-31
- Price growth: Convert percentage to decimal (20% → 0.20)
- Symbols: Extract only from available symbols list, use uppercase
- Financial year (fy): Extract year if mentioned (2016 or 2017)
- Thresholds: Extract numeric values for debt-equity, ROE, PE ratios

Return ONLY the JSON object, no explanations or additional text."""

    return prompt


def parse_llm_response(llm_response: str) -> dict:
    """
    Parse the LLM's JSON response and extract query parameters.
    Falls back to regex parsing if JSON parsing fails.
    """
    try:
        # Try to find JSON in the response
        json_start = llm_response.find("{")
        json_end = llm_response.rfind("}") + 1

        if json_start != -1 and json_end > json_start:
            json_str = llm_response[json_start:json_end]
            parsed = json.loads(json_str)
            return parsed
        else:
            raise ValueError("No JSON found in response")

    except (json.JSONDecodeError, ValueError) as e:
        print(f"Warning: Could not parse LLM JSON response: {e}")
        print(f"LLM Response: {llm_response}")
        # Return empty dict to trigger fallback
        return {}


def analyze_query_with_llm(nl_query: str) -> QueryPlan:
    """
    Use LLM to analyze the natural language query and extract parameters.
    Falls back to regex-based parsing if LLM is unavailable.
    """
    from llm_client import call_ollama, check_ollama_status

    # Check if Ollama is available
    if not check_ollama_status():
        print("Warning: Ollama not available, using fallback regex parser")
        return analyze_query_fallback(nl_query)

    # Build prompt and call LLM
    prompt = build_nl_to_sql_prompt(nl_query)
    llm_response = call_ollama(prompt, temperature=0.1)

    # Parse LLM response
    parsed = parse_llm_response(llm_response)

    # If parsing failed, use fallback
    if not parsed:
        print("Warning: LLM parsing failed, using fallback regex parser")
        return analyze_query_fallback(nl_query)

    # Convert parsed data to QueryPlan
    try:
        start_date = (
            date.fromisoformat(parsed["start_date"])
            if parsed.get("start_date")
            else date(2016, 1, 1)
        )
        end_date = (
            date.fromisoformat(parsed["end_date"])
            if parsed.get("end_date")
            else date(2017, 12, 31)
        )

        return QueryPlan(
            start_date=start_date,
            end_date=end_date,
            symbols=parsed.get("symbols"),
            min_price_growth=parsed.get("min_price_growth"),
            max_debt_equity=parsed.get("max_debt_equity"),
            min_roe=parsed.get("min_roe"),
            max_pe=parsed.get("max_pe"),
            fy=parsed.get("fy"),
        )
    except (KeyError, ValueError, TypeError) as e:
        print(f"Warning: Error converting LLM output to QueryPlan: {e}")
        return analyze_query_fallback(nl_query)


# ------------ fallback regex-based helpers ------------


def _parse_time_window(text: str) -> Tuple[date, date, Optional[int]]:
    t = text.lower()

    if "2016" in t:
        return date(2016, 1, 1), date(2016, 12, 31), 2016
    if "2017" in t:
        return date(2017, 1, 1), date(2017, 12, 31), 2017

    if "last year" in t or "past year" in t:
        end = date(2017, 12, 31)
        start = end - relativedelta(years=1)
        return start, end, 2017

    # default to full window of our data
    return date(2016, 1, 1), date(2017, 12, 31), None


def _parse_thresholds(text: str):
    t = text.lower()

    # price growth %
    # match "20% price growth" or "price growth 20%" loosely
    mg = re.search(r"(\d+)\s*%[^%]*price|\bprice growth\s*(\d+)\s*%", t)
    min_growth = None
    if mg:
        num = mg.group(1) or mg.group(2)
        min_growth = float(num) / 100.0

    # debt-equity
    md = re.search(r"debt[- ]equity\s*[<≤=]+\s*([0-9.]+)", t)
    max_de = float(md.group(1)) if md else None

    # ROE
    mr = re.search(r"roe\s*[>≥=]+\s*([0-9.]+)", t)
    min_roe = float(mr.group(1)) if mr else None

    # PE
    mp = re.search(r"(?:p\/?e|pe)\s*[<≤=]+\s*([0-9.]+)", t)
    max_pe = float(mp.group(1)) if mp else None

    return min_growth, max_de, min_roe, max_pe


def _detect_symbols(text: str) -> Optional[List[str]]:
    upper = text.upper()
    syms = [s for s in ALL_SYMBOLS if s in upper]
    return syms or None


def analyze_query_fallback(nl_query: str) -> QueryPlan:
    """
    Fallback regex-based query analyzer (original implementation).
    """
    start, end, fy = _parse_time_window(nl_query)
    min_growth, max_de, min_roe, max_pe = _parse_thresholds(nl_query)
    syms = _detect_symbols(nl_query)

    return QueryPlan(
        start_date=start,
        end_date=end,
        symbols=syms,
        min_price_growth=min_growth,
        max_debt_equity=max_de,
        min_roe=min_roe,
        max_pe=max_pe,
        fy=fy,
    )


# ------------ main analyzer entry points ------------


def analyze_query(nl_query: str) -> QueryPlan:
    """
    Main entry point - tries LLM first, falls back to regex if needed.
    """
    return analyze_query_with_llm(nl_query)


def build_sql(plan: QueryPlan) -> QueryPlan:
    # price query
    where_symbols = ""
    if plan.symbols:
        in_list = ", ".join(f"'{s}'" for s in plan.symbols)
        where_symbols = f"AND symbol IN ({in_list})"

    sql_price = f"""
        SELECT
            symbol,
            MIN(close_price) AS start_price,
            MAX(close_price) AS end_price,
            (MAX(close_price) - MIN(close_price)) / MIN(close_price) AS price_growth
        FROM prices
        WHERE trade_date BETWEEN '{plan.start_date}' AND '{plan.end_date}'
        {where_symbols}
        GROUP BY symbol
    """

    # fundamentals query – use fy if specified, else both
    if plan.fy is not None:
        fy_filter = f"AND fy = {plan.fy}"
    else:
        fy_filter = "AND fy IN (2016, 2017)"

    sql_fund = f"""
        SELECT
            symbol,
            fy,
            roe,
            debt_equity_ratio,
            current_ratio,
            pe_ratio,
            pb_ratio,
            market_cap
        FROM fundamentals
        WHERE 1 = 1
        {fy_filter}
    """

    plan.sql_price = sql_price
    plan.sql_fund = sql_fund
    return plan


def analyze_and_decompose(nl_query: str) -> QueryPlan:
    """
    High-level entry point used by federator:
      1) analyze NL query
      2) build concrete SQL sub-queries
    """
    plan = analyze_query(nl_query)
    plan = build_sql(plan)
    return plan


if __name__ == "__main__":
    q = "show companies with price growth 20% in 2017 and debt equity < 1 and ROE > 15 and PE < 25"
    plan = analyze_and_decompose(q)
    print(plan)
    print("\nSQL price:\n", plan.sql_price)
    print("\nSQL fund:\n", plan.sql_fund)
