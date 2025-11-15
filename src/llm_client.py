# src/llm_client.py

import os
import textwrap

REPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "reports")


def load_report_text(symbol: str, fy: int) -> str:
    """
    Optional: read pre-downloaded management discussion / annual report snippets.
    If you don't have these, it just returns empty string.
    """
    fname = f"{symbol}_{fy}.txt"
    path = os.path.join(REPORT_DIR, fname)
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def build_llm_prompt(symbol: str, report_text: str) -> str:
    if not report_text:
        return f"Summarize key investment highlights for {symbol} based on quantitative metrics only."

    prompt = f"""
    You are a financial analyst. Read the following extract from the annual
    report of {symbol}.

    TASK:
      - Summarize management's view on growth, risks, and capital structure
      - Keep it to 3–5 concise bullet points.

    REPORT TEXT:
    {report_text[:6000]}
    """
    return textwrap.dedent(prompt)


def call_llm(prompt: str) -> str:
    """
    Placeholder. For the assignment demo you can print/return the prompt
    instead of actually calling a model.
    """
    # For now just return the first 200 characters so the pipeline works.
    return "LLM summary placeholder based on prompt: " + prompt[:200]
