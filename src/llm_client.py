# src/llm_client.py

import os
import textwrap
import json
import requests
from typing import Optional, Dict, Any

REPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "reports")

# Ollama configuration
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "mistral"  # or "llama3.2" - mistral is better for SQL generation


def check_ollama_status() -> bool:
    """Check if Ollama is running and the model is available."""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            model_names = [m["name"] for m in models]
            # Check for exact match or partial match (e.g., "mistral:latest")
            return any(OLLAMA_MODEL in name for name in model_names)
        return False
    except Exception as e:
        print(f"Warning: Could not connect to Ollama: {e}")
        return False


def call_ollama(prompt: str, temperature: float = 0.1, max_tokens: int = 2000) -> str:
    """
    Call Ollama API with the given prompt.
    Lower temperature for more deterministic SQL generation.
    """
    try:
        url = f"{OLLAMA_BASE_URL}/api/generate"
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()

        result = response.json()
        return result.get("response", "").strip()

    except Exception as e:
        print(f"Error calling Ollama: {e}")
        return f"Error: Could not generate response - {str(e)}"


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
    Call the LLM for general text generation (report summaries, etc.).
    """
    if not check_ollama_status():
        return "LLM summary unavailable - Ollama not running or model not found."

    return call_ollama(prompt, temperature=0.3)
