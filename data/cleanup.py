from pathlib import Path
import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "fundamentals.csv"
OUTPUT_FILE = BASE_DIR / "fundamentals_clean.csv"

# Columns that MUST remain string
NON_NUMERIC = ["symbol"]

def clean_numeric(series):
    """Strip invalid characters and convert to float."""
    return (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("–", "", regex=False)
        .str.replace("-", "", regex=False)  # remove placeholder dashes
        .str.strip()
        .replace(["", "nan", "NaN", "None", "--", " "], np.nan)
        .astype(float)
    )

def clean_fundamentals():
    print(f"📥 Loading: {INPUT_FILE}")
    df = pd.read_csv(INPUT_FILE)
    print("Raw shape:", df.shape)

    # Clean symbol
    if "symbol" in df.columns:
        df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()

    # Convert fy to int
    if "fy" in df.columns:
        df["fy"] = pd.to_numeric(df["fy"], errors="coerce").astype("Int64")

    # Detect numeric columns
    numeric_cols = [c for c in df.columns if c not in NON_NUMERIC + ["fy"]]

    # Clean all numeric columns
    for col in numeric_cols:
        df[col] = clean_numeric(df[col])

    # cash_conversion_cycle MUST NOT be blank for FLOAT
    if "cash_conversion_cycle" in df.columns:
        df["cash_conversion_cycle"] = df["cash_conversion_cycle"].fillna(0.0)

    # Sort for consistency
    df = df.sort_values(["symbol", "fy"])

    print("Cleaned shape:", df.shape)

    # Save
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"✅ Saved cleaned CSV → {OUTPUT_FILE}")
    print("Ready for MySQL import (0 truncation errors expected).")

if __name__ == "__main__":
    clean_fundamentals()
