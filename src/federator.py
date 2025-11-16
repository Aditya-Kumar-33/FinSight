# federator.py

import pandas as pd
from analyzer import analyze_and_decompose, QueryPlan
from db_utils import query_price_db, query_fund_db


def run_federated_query(nl_query: str) -> tuple[QueryPlan, pd.DataFrame, pd.DataFrame]:
    plan = analyze_and_decompose(nl_query)

    # safety + type checker happiness
    assert plan.sql_price is not None, "sql_price was not generated"
    assert plan.sql_fund is not None, "sql_fund was not generated"

    try:
        df_price = query_price_db(plan.sql_price)
    except Exception as e:
        print(f"\n❌ Error executing price query: {e}")
        print(f"SQL was: {plan.sql_price}")
        raise

    try:
        df_fund = query_fund_db(plan.sql_fund)
    except Exception as e:
        print(f"\n❌ Error executing fundamentals query: {e}")
        print(f"SQL was: {plan.sql_fund}")
        raise

    return plan, df_price, df_fund


if __name__ == "__main__":
    q = "show companies with price growth 20% in 2017 and debt equity < 1"
    plan, df_price, df_fund = run_federated_query(q)
    print("PRICE RESULT:\n", df_price.head())
    print("\nFUND RESULT:\n", df_fund.head())
