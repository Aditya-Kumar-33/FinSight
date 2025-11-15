#!/usr/bin/env python
"""
Test script to verify LLM integration with FinSight analyzer.
This script tests both LLM-powered and fallback parsing modes.
"""

import sys

sys.path.insert(0, "src")

from src.llm_client import check_ollama_status, call_ollama
from src.analyzer import analyze_and_decompose, analyze_query_fallback


def test_ollama_connection():
    """Test if Ollama is running and accessible."""
    print("=" * 70)
    print("TEST 1: Ollama Connection")
    print("=" * 70)

    status = check_ollama_status()
    if status:
        print("✓ Ollama is running and Mistral model is available")
        return True
    else:
        print("✗ Ollama is not available")
        print("  Install Ollama and run: ollama pull mistral")
        return False


def test_llm_query_parsing():
    """Test LLM-based query parsing."""
    print("\n" + "=" * 70)
    print("TEST 2: LLM Query Parsing")
    print("=" * 70)

    test_query = (
        "show companies with price growth 20% in 2017 and debt equity < 1 and ROE > 15"
    )
    print(f"Query: {test_query}\n")

    try:
        plan = analyze_and_decompose(test_query)

        print("✓ Query parsed successfully")
        print(f"  Start Date: {plan.start_date}")
        print(f"  End Date: {plan.end_date}")
        print(f"  Symbols: {plan.symbols}")
        print(f"  Min Price Growth: {plan.min_price_growth}")
        print(f"  Max Debt/Equity: {plan.max_debt_equity}")
        print(f"  Min ROE: {plan.min_roe}")
        print(f"  Max PE: {plan.max_pe}")
        print(f"  FY: {plan.fy}")

        print("\nGenerated SQL (Price):")
        print(plan.sql_price[:200] + "...")

        print("\nGenerated SQL (Fundamentals):")
        print(plan.sql_fund[:200] + "...")

        return True
    except Exception as e:
        print(f"✗ Query parsing failed: {e}")
        return False


def test_fallback_parsing():
    """Test regex-based fallback parsing."""
    print("\n" + "=" * 70)
    print("TEST 3: Fallback Regex Parsing")
    print("=" * 70)

    test_query = "show companies with price growth 20% in 2017 and debt equity < 1"
    print(f"Query: {test_query}\n")

    try:
        plan = analyze_query_fallback(test_query)

        print("✓ Fallback parser works correctly")
        print(f"  Start Date: {plan.start_date}")
        print(f"  End Date: {plan.end_date}")
        print(f"  Min Price Growth: {plan.min_price_growth}")
        print(f"  Max Debt/Equity: {plan.max_debt_equity}")

        return True
    except Exception as e:
        print(f"✗ Fallback parsing failed: {e}")
        return False


def test_complex_queries():
    """Test various query patterns."""
    print("\n" + "=" * 70)
    print("TEST 4: Complex Query Patterns")
    print("=" * 70)

    queries = [
        "find stocks with ROE > 15 in 2017",
        "show RELIANCE and TCS performance in 2016",
        "companies with price growth 30% and PE < 20",
    ]

    results = []
    for query in queries:
        print(f"\nQuery: {query}")
        try:
            plan = analyze_and_decompose(query)
            print(f"  ✓ Parsed successfully")
            print(f"    Date range: {plan.start_date} to {plan.end_date}")
            print(f"    Symbols: {plan.symbols}")
            results.append(True)
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            results.append(False)

    return all(results)


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "FinSight LLM Integration Test Suite" + " " * 18 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    results = []

    # Test 1: Ollama connection
    ollama_available = test_ollama_connection()
    results.append(ollama_available)

    # Test 2: LLM parsing (only if Ollama is available)
    if ollama_available:
        results.append(test_llm_query_parsing())
    else:
        print("\nSkipping LLM parsing test (Ollama not available)")

    # Test 3: Fallback parsing
    results.append(test_fallback_parsing())

    # Test 4: Complex queries
    results.append(test_complex_queries())

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(results)
    total = len(results)

    print(f"Tests Passed: {passed}/{total}")

    if ollama_available:
        print("\n✓ LLM integration is working!")
        print("  The system will use Mistral for natural language query parsing.")
    else:
        print("\n⚠ LLM is not available.")
        print("  The system will use fallback regex parsing.")
        print("  To enable LLM features:")
        print("    1. Install Ollama from https://ollama.ai")
        print("    2. Run: ollama pull mistral")
        print("    3. Verify: ollama list")

    print("\nFor more information, see: OLLAMA_SETUP.md")
    print("=" * 70)

    return all(results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
