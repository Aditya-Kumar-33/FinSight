# FinSight System Architecture

## Complete System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                              │
│                        (main_cli.py)                                │
│                                                                     │
│  > "show companies with price growth 20% in 2017 and ROE > 15"     │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    QUERY ANALYZER (analyzer.py)                     │
│                                                                     │
│  ┌──────────────────┐          ┌──────────────────────────────┐   │
│  │  LLM Analysis    │          │   Fallback Regex Analysis     │   │
│  │  (Primary)       │  Fails?  │   (Automatic)                 │   │
│  │                  ├─────────►│                                │   │
│  │ • Mistral LLM    │          │ • Pattern matching            │   │
│  │ • Natural Lang   │          │ • Regex extraction            │   │
│  │ • JSON output    │          │ • Deterministic               │   │
│  └────────┬─────────┘          └──────────────┬───────────────┘   │
│           │                                   │                    │
│           └───────────────┬───────────────────┘                    │
│                           ▼                                        │
│                   ┌───────────────┐                                │
│                   │  Query Plan   │                                │
│                   │  (Dataclass)  │                                │
│                   └───────┬───────┘                                │
└───────────────────────────┼────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    SQL BUILDER (analyzer.py)                        │
│                                                                     │
│  QueryPlan → SQL Queries                                            │
│  ┌──────────────────────────┐   ┌──────────────────────────┐      │
│  │  Price Query             │   │  Fundamentals Query       │      │
│  │                          │   │                           │      │
│  │  SELECT symbol,          │   │  SELECT symbol, fy,       │      │
│  │    MIN(close_price),     │   │    roe, debt_equity,      │      │
│  │    MAX(close_price),     │   │    pe_ratio, ...          │      │
│  │    price_growth          │   │  FROM fundamentals        │      │
│  │  FROM prices             │   │  WHERE fy = 2017          │      │
│  │  WHERE date BETWEEN ...  │   │    AND ...                │      │
│  │  GROUP BY symbol         │   │                           │      │
│  └────────────┬─────────────┘   └──────────────┬───────────┘      │
└───────────────┼─────────────────────────────────┼──────────────────┘
                │                                 │
                ▼                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  FEDERATOR (federator.py)                           │
│                                                                     │
│  Executes queries on distributed databases                          │
│                                                                     │
│  ┌────────────────┐                    ┌────────────────┐          │
│  │  DB Utils      │                    │  DB Utils      │          │
│  │  (db_utils.py) │                    │  (db_utils.py) │          │
│  └────────┬───────┘                    └────────┬───────┘          │
└───────────┼─────────────────────────────────────┼──────────────────┘
            │                                     │
            ▼                                     ▼
┌──────────────────────┐            ┌──────────────────────┐
│   MySQL Container    │            │   MySQL Container    │
│                      │            │                      │
│   price_db           │            │   fundamentals_db    │
│   Port: 3307         │            │   Port: 3308         │
│                      │            │                      │
│   ┌────────────┐     │            │   ┌────────────┐     │
│   │  prices    │     │            │   │fundamental │     │
│   │  table     │     │            │   │    table   │     │
│   │            │     │            │   │            │     │
│   │ • symbol   │     │            │   │ • symbol   │     │
│   │ • date     │     │            │   │ • fy       │     │
│   │ • price    │     │            │   │ • roe      │     │
│   │ • volume   │     │            │   │ • de_ratio │     │
│   └────────────┘     │            │   │ • pe_ratio │     │
│                      │            │   └────────────┘     │
└──────────┬───────────┘            └──────────┬───────────┘
           │                                   │
           │  DataFrame                        │  DataFrame
           ▼                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  INTEGRATOR (integrator.py)                         │
│                                                                     │
│  1. Merge DataFrames on 'symbol'                                    │
│  2. Apply filters from QueryPlan                                    │
│  3. Generate LLM commentary per result                              │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │  For each matched stock:                                 │      │
│  │    • Merge price + fundamentals data                     │      │
│  │    • Apply threshold filters                             │      │
│  │    • Call LLM for commentary (via llm_client.py)         │      │
│  │    • Build result dictionary                             │      │
│  └──────────────────────────────────────────────────────────┘      │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      RESULTS OUTPUT                                 │
│                                                                     │
│  ======================================                             │
│  Symbol        : TCS                                                │
│  Price growth  : 25.34% (from 2250.50 to 2820.75)                  │
│  ROE           : 18.50                                              │
│  Debt/Equity   : 0.15                                               │
│  P/E           : 22.30                                              │
│  Current Ratio : 2.45                                               │
│  Market Cap    : 850000000000                                       │
│                                                                     │
│  LLM commentary:                                                    │
│  [AI-generated summary of company performance...]                   │
└─────────────────────────────────────────────────────────────────────┘
```

## LLM Integration Detail

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LLM CLIENT (llm_client.py)                       │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────┐     │
│  │  check_ollama_status()                                    │     │
│  │  • Pings http://localhost:11434/api/tags                  │     │
│  │  • Checks if 'mistral' model is available                 │     │
│  │  • Returns True/False                                     │     │
│  └───────────────────────────────────────────────────────────┘     │
│                              │                                      │
│                              ▼                                      │
│  ┌───────────────────────────────────────────────────────────┐     │
│  │  build_nl_to_sql_prompt(query)                            │     │
│  │  • Includes database schema                               │     │
│  │  • Lists available symbols                                │     │
│  │  • Specifies JSON output format                           │     │
│  │  • Provides parsing rules                                 │     │
│  └───────────────────────────────────────────────────────────┘     │
│                              │                                      │
│                              ▼                                      │
│  ┌───────────────────────────────────────────────────────────┐     │
│  │  call_ollama(prompt, temp=0.1)                            │     │
│  │  • POST to http://localhost:11434/api/generate            │     │
│  │  • Model: mistral                                         │     │
│  │  • Temperature: 0.1 (deterministic for SQL)               │     │
│  │  • Timeout: 60 seconds                                    │     │
│  └───────────────────────────────────────────────────────────┘     │
│                              │                                      │
│                              ▼                                      │
│                      ┌───────────────┐                              │
│                      │  Ollama API   │                              │
│                      │  (External)   │                              │
│                      └───────┬───────┘                              │
│                              │                                      │
│                              ▼                                      │
│  ┌───────────────────────────────────────────────────────────┐     │
│  │  parse_llm_response(response)                             │     │
│  │  • Extract JSON from response text                        │     │
│  │  • Validate structure                                     │     │
│  │  • Handle errors gracefully                               │     │
│  └───────────────────────────────────────────────────────────┘     │
│                              │                                      │
│                              ▼                                      │
│                      ┌───────────────┐                              │
│                      │  QueryPlan    │                              │
│                      │  Parameters   │                              │
│                      └───────────────┘                              │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow Timeline

```
Time  │ Component        │ Action
──────┼──────────────────┼─────────────────────────────────────────────
0.0s  │ User             │ Types query
      │                  │ "show companies with 20% growth in 2017"
──────┼──────────────────┼─────────────────────────────────────────────
0.1s  │ main_cli.py      │ Receives input
      │                  │ Calls run_federated_query()
──────┼──────────────────┼─────────────────────────────────────────────
0.2s  │ federator.py     │ Calls analyze_and_decompose()
──────┼──────────────────┼─────────────────────────────────────────────
0.3s  │ analyzer.py      │ Calls analyze_query_with_llm()
      │                  │ Checks Ollama status → Available
──────┼──────────────────┼─────────────────────────────────────────────
0.4s  │ llm_client.py    │ Builds prompt with schema + rules
      │                  │ Sends to Ollama API
──────┼──────────────────┼─────────────────────────────────────────────
0.5s  │ Ollama (Mistral) │ Processes natural language
  -   │                  │ [LLM inference...]
2.0s  │                  │ Returns JSON response
──────┼──────────────────┼─────────────────────────────────────────────
2.1s  │ llm_client.py    │ Parses JSON
      │                  │ Validates structure
──────┼──────────────────┼─────────────────────────────────────────────
2.2s  │ analyzer.py      │ Creates QueryPlan object
      │                  │ Calls build_sql()
──────┼──────────────────┼─────────────────────────────────────────────
2.3s  │ analyzer.py      │ Generates SQL queries:
      │                  │ • Price query with filters
      │                  │ • Fundamentals query with filters
──────┼──────────────────┼─────────────────────────────────────────────
2.4s  │ federator.py     │ Executes queries in parallel:
──────┼──────────────────┼─────────────────────────────────────────────
2.5s  │ db_utils.py      │ Connects to price_db (port 3307)
      │                  │ Runs price query
──────┼──────────────────┼─────────────────────────────────────────────
2.6s  │ MySQL (price_db) │ Executes SELECT with aggregation
      │                  │ Returns 9 rows (one per symbol)
──────┼──────────────────┼─────────────────────────────────────────────
2.7s  │ db_utils.py      │ Connects to fundamentals_db (port 3308)
      │                  │ Runs fundamentals query
──────┼──────────────────┼─────────────────────────────────────────────
2.8s  │ MySQL (fund_db)  │ Executes SELECT with filters
      │                  │ Returns matching rows
──────┼──────────────────┼─────────────────────────────────────────────
2.9s  │ federator.py     │ Returns QueryPlan + 2 DataFrames
──────┼──────────────────┼─────────────────────────────────────────────
3.0s  │ main_cli.py      │ Calls integrate()
──────┼──────────────────┼─────────────────────────────────────────────
3.1s  │ integrator.py    │ Merges DataFrames on 'symbol'
      │                  │ Applies threshold filters
──────┼──────────────────┼─────────────────────────────────────────────
3.2s  │ integrator.py    │ For each result:
      │                  │ • Loads report text (if exists)
      │                  │ • Calls LLM for commentary
──────┼──────────────────┼─────────────────────────────────────────────
3.3s  │ llm_client.py    │ Generates summaries via Ollama
  -   │                  │ [Per-stock commentary...]
4.0s  │                  │ Returns commentary
──────┼──────────────────┼─────────────────────────────────────────────
4.1s  │ integrator.py    │ Returns list of result dicts
──────┼──────────────────┼─────────────────────────────────────────────
4.2s  │ main_cli.py      │ Formats and prints results
──────┼──────────────────┼─────────────────────────────────────────────
4.3s  │ User             │ Sees formatted output
      │                  │ Prompt for next query
──────┴──────────────────┴─────────────────────────────────────────────

Total Time: ~4.3 seconds (with LLM)
            ~1.0 seconds (fallback regex mode)
```

## Component Responsibilities

| Component | File | Responsibility |
|-----------|------|----------------|
| **CLI** | `main_cli.py` | User interaction, output formatting |
| **Federator** | `federator.py` | Query orchestration, DB execution |
| **Analyzer** | `analyzer.py` | NL→SQL conversion, query decomposition |
| **LLM Client** | `llm_client.py` | Ollama communication, prompt engineering |
| **Integrator** | `integrator.py` | Result merging, filtering, commentary |
| **DB Utils** | `db_utils.py` | Database connectivity, query execution |
| **Config** | `config.py` | Database connection settings |

## Database Schema

### prices table (price_db:3307)
```sql
CREATE TABLE prices (
  id INT AUTO_INCREMENT PRIMARY KEY,
  symbol VARCHAR(32) NOT NULL,
  trade_date DATE NOT NULL,
  open_price DECIMAL(12,4),
  high_price DECIMAL(12,4),
  low_price DECIMAL(12,4),
  close_price DECIMAL(12,4) NOT NULL,
  volume BIGINT,
  INDEX idx_symbol_date (symbol, trade_date)
);
```

### fundamentals table (fundamentals_db:3308)
```sql
CREATE TABLE fundamentals (
  id INT AUTO_INCREMENT PRIMARY KEY,
  symbol VARCHAR(32) NOT NULL,
  fy INT NOT NULL,
  roe FLOAT,
  debt_equity_ratio FLOAT,
  pe_ratio FLOAT,
  current_ratio FLOAT,
  market_cap BIGINT,
  -- ... 30+ other financial metrics
  INDEX idx_symbol_fy (symbol, fy)
);
```

## External Dependencies

| Dependency | Purpose | Version |
|------------|---------|---------|
| **Ollama** | LLM inference engine | Latest |
| **Mistral** | Language model | 7B |
| **MySQL** | Database server | 8.0 |
| **Docker** | Container runtime | Latest |
| **Python** | Runtime environment | 3.10+ |

## Security Considerations

1. **Database**: Root password in config (development only)
2. **Ollama**: Local API, no authentication needed
3. **Network**: All services on localhost
4. **SQL Injection**: Parameterized queries prevent injection
5. **LLM Prompts**: User input sanitized before LLM

## Scalability Notes

- **LLM**: Single-threaded, ~2s per query
- **Database**: Can handle concurrent queries
- **Caching**: Not implemented (future enhancement)
- **Rate Limiting**: Not needed (local deployment)

---

This architecture provides a robust, extensible foundation for natural language financial data queries with automatic fallback and comprehensive error handling.
