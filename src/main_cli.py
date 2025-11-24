# main_cli.py

from services import execute_query


def format_result_output(results, llm_summary, nl_query):
    """Format the output based on query results."""
    if not results:
        print("\nNo companies matched your criteria.")
        if llm_summary:
            print(f"\nNote: {llm_summary}")
        return

    # Display summary first if available
    if llm_summary:
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(llm_summary)
        print()

    # Display detailed results
    print("\n" + "=" * 70)
    print(
        f"DETAILED RESULTS ({len(results)} {'company' if len(results) == 1 else 'companies'} found)"
    )
    print("=" * 70)

    for i, r in enumerate(results, 1):
        print(f"\n[{i}] {r['symbol']}")
        print("-" * 50)

        # Only show metrics that have meaningful values
        if r["start_price"] > 0 and r["end_price"] > 0:
            print(
                f"  Price Change : {r['start_price']:.2f} -> {r['end_price']:.2f} "
                f"({r['price_growth']*100:+.2f}%)"
            )

        if r["roe"] > 0:
            print(f"  ROE          : {r['roe']:.2f}%")

        if r["debt_equity_ratio"] > 0:
            print(f"  Debt/Equity  : {r['debt_equity_ratio']:.2f}")

        if r["pe_ratio"] > 0:
            print(f"  P/E Ratio    : {r['pe_ratio']:.2f}")

        if r["current_ratio"] > 0:
            print(f"  Current Ratio: {r['current_ratio']:.2f}")

        if r["market_cap"] > 0:
            print(f"  Market Cap   : Rs {r['market_cap']:,.0f}")


def main():
    print("=" * 70)
    print("FinSight CLI - Intelligent Financial Data Query System")
    print("=" * 70)
    print("\nType your financial query in natural language (or 'q' to quit).")
    print("Example: 'Show companies with 20% price growth in 2017'")
    print()

    while True:
        nl_query = input("> ").strip()

        if not nl_query:
            continue

        if nl_query.lower() in {"q", "quit", "exit"}:
            print("\nGoodbye!")
            break

        print("\nAnalyzing query and generating SQL...")
        try:
            plan, results, llm_summary = execute_query(nl_query)
        except Exception as e:
            print(f"\nError executing query: {e}")
            continue

        print("Integrating results...")
        try:
            format_result_output(results, llm_summary, nl_query)
        except Exception as e:
            print(f"\nError processing results: {e}")
            import traceback

            traceback.print_exc()
            continue


if __name__ == "__main__":
    main()
