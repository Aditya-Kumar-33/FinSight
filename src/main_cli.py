# main_cli.py

from federator import run_federated_query
from integrator import integrate


def main():
    print("Finsight CLI – type a query (or 'q' to quit).")
    while True:
        nl_query = input("\n> ").strip()
        if not nl_query:
            continue
        if nl_query.lower() in {"q", "quit", "exit"}:
            break

        print("\nAnalyzing and decomposing query...")
        plan, df_price, df_fund = run_federated_query(nl_query)

        print("\nExecuting and integrating results...")
        results = integrate(plan, df_price, df_fund)

        if not results:
            print("No companies matched your criteria.")
            continue

        for r in results:
            print("\n======================================")
            print(f"Symbol        : {r['symbol']}")
            print(f"Price growth  : {r['price_growth']*100:.2f}% "
                  f"(from {r['start_price']:.2f} to {r['end_price']:.2f})")
            print(f"ROE           : {r['roe']:.2f}")
            print(f"Debt/Equity   : {r['debt_equity_ratio']:.2f}")
            print(f"P/E           : {r['pe_ratio']:.2f}")
            print(f"Current Ratio : {r['current_ratio']:.2f}")
            print(f"Market Cap    : {r['market_cap']:.0f}")
            print("\nLLM commentary (placeholder):")
            print(r["llm_commentary"])


if __name__ == "__main__":
    main()
