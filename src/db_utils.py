# src/db_utils.py

import pandas as pd
import mysql.connector
from config import PRICE_DB, FUND_DB


def query_price_db(sql: str, params=None) -> pd.DataFrame:
    conn = mysql.connector.connect(**PRICE_DB)
    try:
        df = pd.read_sql(sql, conn, params=params)
    finally:
        conn.close()
    return df


def query_fund_db(sql: str, params=None) -> pd.DataFrame:
    conn = mysql.connector.connect(**FUND_DB)
    try:
        df = pd.read_sql(sql, conn, params=params)
    finally:
        conn.close()
    return df


if __name__ == "__main__":
    # quick smoke test
    print("Testing price_db...")
    df_p = query_price_db("SELECT symbol, COUNT(*) AS n FROM prices GROUP BY symbol")
    print(df_p)

    print("\nTesting fundamentals_db...")
    df_f = query_fund_db("SELECT symbol, COUNT(*) AS n FROM fundamentals GROUP BY symbol")
    print(df_f)
