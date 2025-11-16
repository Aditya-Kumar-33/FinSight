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


# ------------ LLM-based SQL query generator ------------


def build_nl_to_sql_prompt(nl_query: str) -> str:
    """
    Build a comprehensive prompt for the LLM to convert natural language directly to SQL queries.
    """
    prompt = f"""You are a SQL query generator for financial databases. Convert the following natural language query into TWO SEPARATE SQL queries.
IMPORTANT: DO NOT INVENT numeric metric values. If the user requests a metric that doesn't exist in the schema (for example 'ROI' when only 'roe' exists), do NOT fabricate an answer — return SQL and parameter fields only, and set data_unavailable where appropriate.

DATABASE SCHEMA:
1. prices table (ONLY price data):
   - symbol VARCHAR (stock ticker symbol)
   - trade_date DATE
   - close_price DECIMAL
   NOTE: NO fundamental metrics here (no ROE, debt_equity_ratio, PE, etc.)

2. fundamentals table (ONLY fundamental metrics):
   - symbol VARCHAR (stock ticker symbol)
   - fy INT (fiscal year: 2012 to 2022 ONLY)
   - roe DECIMAL (Return on Equity)
   - debt_equity_ratio DECIMAL
   - current_ratio DECIMAL
   - pe_ratio DECIMAL (Price to Earnings)
   - pb_ratio DECIMAL (Price to Book)
   - market_cap BIGINT
   NOTE: NO price data here

AVAILABLE SYMBOLS: {', '.join(ALL_SYMBOLS)}
AVAILABLE DATA RANGE: 2012-01-01 to 2022-12-31 ONLY

USER QUERY: "{nl_query}"

CRITICAL RULES - READ CAREFULLY:
- If the user requests data outside 2012-01-01 to 2022-12-31, do NOT hallucinate — set data_unavailable = true in your JSON and provide a clear unavailable message.
- If the user requests a metric not present in the schema (e.g., \"ROI\"), do NOT invent numeric values. Indicate the requested metric in the JSON (requested_metric) so the caller can decide how to proceed (map, approximate, or refuse).
- Return ONLY a single valid JSON object (no extra text). The JSON must contain the two SQL strings and the extracted parameters as described below.

**sql_price query:**
- Query ONLY the prices table
- NEVER filter by fundamental metrics (ROE, debt_equity, PE, etc.) - those are in a different table!
- Calculate: (MAX(close_price) - MIN(close_price)) / MIN(close_price) AS price_growth
- Filter by: date range (BETWEEN), symbols (IN clause if specified)
- GROUP BY symbol
- SELECT: symbol, MIN(close_price) AS start_price, MAX(close_price) AS end_price, price_growth
- DO NOT use HAVING clause for fundamentals - they don't exist in prices table!

**sql_fund query:**
- Query ONLY the fundamentals table
- Filter by: fiscal year (fy), optionally by symbol
- If no fy specified, use: WHERE fy IN (2012, 2022)
- SELECT all columns: symbol, fy, roe, debt_equity_ratio, current_ratio, pe_ratio, pb_ratio, market_cap
- DO NOT try to filter by price_growth - that's in a different table!

**Parameter extraction:**
- Extract thresholds but DON'T put them in SQL - the Python code will apply them after joining tables
- min_price_growth: from "X% growth", "growth > X%", etc. (as decimal: 20% = 0.20)
- max_debt_equity: from "debt-equity < X", "DE < X", etc.
- min_roe: from "ROE > X", "ROE ≥ X%", etc.
- max_pe: from "PE < X", "P/E < X", etc.
- fy: from "2012", "2022", "last year" (→2022), "FY 2012", etc.
- symbols: extract from AVAILABLE SYMBOLS list only

Return ONLY a valid JSON object:
{{
  "sql_price": "SELECT symbol, MIN(close_price) AS start_price, MAX(close_price) AS end_price, (MAX(close_price) - MIN(close_price)) / MIN(close_price) AS price_growth FROM prices WHERE trade_date BETWEEN '...' AND '...' [AND symbol IN (...)] GROUP BY symbol",
  "sql_fund": "SELECT symbol, fy, roe, debt_equity_ratio, current_ratio, pe_ratio, pb_ratio, market_cap FROM fundamentals WHERE fy IN (...) [AND symbol IN (...)]",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "symbols": ["SYMBOL1"] or null,
  "min_price_growth": 0.20 or null,
  "max_debt_equity": 1.0 or null,
  "min_roe": 15.0 or null,
  "max_pe": 25.0 or null,
  "fy": 2012 or 2022 or null,
  "data_unavailable": false,
  "unavailable_message": "..." or null
}}

EXAMPLES:
Query: "stocks with 20% growth in 2022 and debt-equity < 1"
- sql_price: WHERE trade_date BETWEEN '2022-01-01' AND '2022-12-31' (NO debt-equity filter here!)
- sql_fund: WHERE fy = 2022 (NO growth filter here!)
- min_price_growth: 0.20 (Python will filter)
- max_debt_equity: 1.0 (Python will filter)

Query: "Show TCS and INFY growth in 2012"
- sql_price: WHERE trade_date BETWEEN '2012-01-01' AND '2012-12-31' AND symbol IN ('TCS', 'INFY')
- sql_fund: WHERE fy = 2012 AND symbol IN ('TCS', 'INFY')
- symbols: ["TCS", "INFY"]

Return ONLY the JSON, no extra text."""

    return prompt


def parse_llm_sql_response(llm_response: str) -> dict:
    """
    Parse the LLM's JSON response containing SQL queries and parameters.
    Returns parsed dictionary or empty dict on failure.
    """
    try:
        # Try to find JSON in the response
        json_start = llm_response.find("{")
        json_end = llm_response.rfind("}") + 1

        if json_start != -1 and json_end > json_start:
            json_str = llm_response[json_start:json_end]
            parsed = json.loads(json_str)

            # Validate that required SQL fields exist
            if "sql_price" not in parsed or "sql_fund" not in parsed:
                raise ValueError("Missing required SQL fields in response")

            return parsed
        else:
            raise ValueError("No JSON found in response")

    except (json.JSONDecodeError, ValueError) as e:
        print(f"Warning: Could not parse LLM SQL response: {e}")
        print(f"LLM Response: {llm_response}")
        # Return empty dict to trigger fallback
        return {}


def validate_sql_query(sql: str, query_type: str = "price") -> bool:
    """
    Basic SQL validation to ensure the query is safe and well-formed.
    Also checks that fundamental fields aren't in price queries and vice versa.
    """
    if not sql or not isinstance(sql, str):
        return False

    sql_lower = sql.lower().strip()

    # Must contain SELECT and FROM
    if "select" not in sql_lower or "from" not in sql_lower:
        return False

    # Shouldn't contain dangerous operations
    dangerous = ["drop", "delete", "insert", "update", "truncate", "alter", "create"]
    if any(keyword in sql_lower for keyword in dangerous):
        return False

    # Check table separation
    if query_type == "price":
        # Price queries should query 'prices' table
        if "from prices" not in sql_lower:
            print(f"Warning: Price query should use 'FROM prices' table")
            return False

        # Price queries should NOT filter by fundamental fields
        fundamental_fields = [
            "roe",
            "debt_equity",
            "pe_ratio",
            "pb_ratio",
            "current_ratio",
            "market_cap",
        ]
        for field in fundamental_fields:
            if field in sql_lower:
                print(
                    f"Warning: Price query contains fundamental field '{field}' - these belong in fundamentals table!"
                )
                return False

    elif query_type == "fund":
        # Fundamentals queries should query 'fundamentals' table
        if "from fundamentals" not in sql_lower:
            print(f"Warning: Fundamentals query should use 'FROM fundamentals' table")
            return False

        # Fundamentals queries should NOT filter by price fields
        price_fields = [
            "close_price",
            "trade_date",
            "price_growth",
            "start_price",
            "end_price",
        ]
        for field in price_fields:
            if field in sql_lower and field not in [
                "start_date",
                "end_date",
            ]:  # Allow date params
                print(
                    f"Warning: Fundamentals query contains price field '{field}' - these belong in prices table!"
                )
                return False

    return True


def analyze_query_with_llm(nl_query: str) -> QueryPlan:
    """
    Use LLM to analyze the natural language query and generate SQL queries directly.
    Falls back to manual SQL generation if LLM is unavailable or fails.
    """
    from llm_client import call_ollama, check_ollama_status

    # Check if Ollama is available
    if not check_ollama_status():
        print("Warning: Ollama not available, using fallback manual SQL generation")
        return analyze_query_fallback(nl_query)

    # Build prompt and call LLM
    prompt = build_nl_to_sql_prompt(nl_query)
    llm_response = call_ollama(prompt, temperature=0.1)

    # Parse LLM response
    parsed = parse_llm_sql_response(llm_response)

    # If parsing failed, use fallback
    if not parsed:
        print("Warning: LLM SQL generation failed, using fallback manual method")
        return analyze_query_fallback(nl_query)

    # Check if data is unavailable
    if parsed.get("data_unavailable", False):
        msg = parsed.get(
            "unavailable_message", "Requested data is not available in the database."
        )
        print(f"\n⚠️  {msg}")
        print("ℹ️  Available data: 2012-2022, stocks: RELIANCE, HDFCBANK, TCS, etc.")
        print("ℹ️  Available fields: close_price (no volume data)")
        # Still try to show what we can with fallback
        return analyze_query_fallback(nl_query)

    # Validate generated SQL queries
    sql_price = parsed.get("sql_price", "")
    sql_fund = parsed.get("sql_fund", "")

    if not validate_sql_query(sql_price, "price") or not validate_sql_query(
        sql_fund, "fund"
    ):
        print(
            "Warning: Generated SQL queries are invalid, using fallback manual method"
        )
        return analyze_query_fallback(nl_query)

    # Convert parsed data to QueryPlan
    try:
        start_date = (
            date.fromisoformat(parsed["start_date"])
            if parsed.get("start_date")
            else date(2012, 1, 1)
        )
        end_date = (
            date.fromisoformat(parsed["end_date"])
            if parsed.get("end_date")
            else date(2022, 12, 31)
        )

        plan = QueryPlan(
            start_date=start_date,
            end_date=end_date,
            symbols=parsed.get("symbols"),
            min_price_growth=parsed.get("min_price_growth"),
            max_debt_equity=parsed.get("max_debt_equity"),
            min_roe=parsed.get("min_roe"),
            max_pe=parsed.get("max_pe"),
            fy=parsed.get("fy"),
        )

        # Directly assign the LLM-generated SQL queries
        plan.sql_price = sql_price
        plan.sql_fund = sql_fund

        print("✓ Successfully generated SQL queries using LLM")
        return plan

    except (KeyError, ValueError, TypeError) as e:
        print(f"Warning: Error converting LLM output to QueryPlan: {e}")
        return analyze_query_fallback(nl_query)


# ------------ fallback regex-based helpers ------------


def _parse_time_window(text: str) -> Tuple[date, date, Optional[int]]:
    t = text.lower()

    if "2012" in t:
        return date(2012, 1, 1), date(2012, 12, 31), 2012
    if "2022" in t:
        return date(2022, 1, 1), date(2022, 12, 31), 2022

    if "last year" in t or "past year" in t:
        end = date(2022, 12, 31)
        start = end - relativedelta(years=1)
        return start, end, 2022

    # default to full window of our data
    return date(2012, 1, 1), date(2022, 12, 31), None


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
    """
    Build SQL queries for the QueryPlan.
    If SQL queries are already set (from LLM), skip generation.
    Otherwise, use the manual method to generate SQL.
    """
    # Check if SQL queries are already generated by LLM
    if plan.sql_price and plan.sql_fund:
        print("Using LLM-generated SQL queries")
        return plan

    print("Using manual SQL generation method")

    # Manual SQL generation (fallback method)
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
        fy_filter = "AND fy IN (2012, 2022)"

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
      1) Try to use LLM to analyze NL query and generate SQL directly
      2) If LLM fails or is unavailable, use fallback regex parser
      3) If SQL not generated by LLM, build SQL manually using build_sql()

    The flow is:
      - analyze_query_with_llm() tries LLM first (generates SQL + parameters)
      - If LLM succeeds, plan.sql_price and plan.sql_fund are already set
      - If LLM fails, analyze_query_fallback() extracts parameters only
      - build_sql() checks if SQL already exists, generates manually if not
    """
    plan = analyze_query(nl_query)
    plan = build_sql(plan)
    return plan


if __name__ == "__main__":
    q = "show companies with price growth 20% in 2022 and debt equity < 1 and ROE > 15 and PE < 25"
    plan = analyze_and_decompose(q)
    print(plan)
    print("\nSQL price:\n", plan.sql_price)
    print("\nSQL fund:\n", plan.sql_fund)
