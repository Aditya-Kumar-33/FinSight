# analyzer.py
from dataclasses import dataclass
from datetime import date
from typing import Optional, List, Tuple
from dateutil.relativedelta import relativedelta
import re

ALL_SYMBOLS = [
    "RELIANCE", "HDFCBANK", "BHARTIARTL", "TCS", "ICICIBANK",
    "SBIN", "BAJFINANCE", "INFY", "HINDUNILVR"
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


# ------------ internal helpers ------------

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


# ------------ main analyzer entry points ------------

def analyze_query(nl_query: str) -> QueryPlan:
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
