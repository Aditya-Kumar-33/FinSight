# FINSIGHT – Federated Stock Analytics with MySQL + Python + LLM

This project demonstrates an Information Integration / Federated Query system over:

* a prices database (`price_db`) with daily stock prices
* a fundamentals database (`fundamentals_db`) with financial ratios
* a Python pipeline that:

  * **parses natural-language queries using LLM (Ollama with Mistral)**
  * decomposes queries into SQL for both databases
  * executes and joins the results
  * generates LLM-powered commentary on results

**NEW**: This system now uses **Ollama with Mistral** for intelligent natural language to SQL conversion, providing more flexible and user-friendly query understanding compared to regex-based parsing.

The repository contains:

* cleaned CSVs (`data/prices.csv`, `data/fundamentals.csv`) that match the database schema
* all Python source files with complete LLM integration
* a Docker Compose file to spin up both databases
* **Ollama integration for natural language query understanding**

---

## 1. Folder Structure

From the root `FINSIGHT/`:

```text
FINSIGHT/
├── .venv/                 # optional virtual environment (created locally)
├── data/
│   ├── cleanup.py         # script used to clean fundamentals.csv (not required to run system)
│   ├── fundamentals.csv   # cleaned fundamentals data, ready to import
│   └── prices.csv         # cleaned price data, ready to import
├── db/
│   └── docker-compose.yml # defines two MySQL containers: price_db, fundamentals_db
└── src/
    ├── analyzer.py        # NL query analyzer + SQL decomposition
    ├── config.py          # DB connection configuration
    ├── db_utils.py        # helpers to run SQL and return pandas DataFrames
    ├── federator.py       # orchestrates NL → QueryPlan → federated DB calls
    ├── integrator.py      # joins and filters results, adds LLM commentary
    ├── llm_client.py      # stub LLM client; builds prompts / dummy summaries
    └── main_cli.py        # CLI entrypoint for demos
```

---

## 2. Prerequisites

Install on your machine:

* **Docker Desktop** - for MySQL databases
* **MySQL Workbench** - for database management
* **Python 3.10+** (3.11/3.12 also fine)
* **Ollama** - for LLM-powered natural language processing (see [OLLAMA_SETUP.md](OLLAMA_SETUP.md))
* Git / unzip capability (to obtain the project)

All commands below assume the repository root is called `FINSIGHT`.

> **Note**: The system includes automatic fallback to regex-based parsing if Ollama is not available, so you can run the basic system without LLM support. However, for the best experience, installing Ollama is recommended.

---

## 3. Start the Databases via Docker

1. Open a terminal in the `db/` folder:

   ```bash
   cd FINSIGHT/db
   ```

2. Start the containers:

   ```bash
   docker compose up -d
   ```

   This creates two MySQL servers:

   * `price_db` exposed on `localhost:3307`
   * `fundamentals_db` exposed on `localhost:3308`

   Both use:

   * user: `root`
   * password: `rootpass`

To check they are running:

```bash
docker ps
```

You should see two `mysql:8.0` containers.

---

## 4. Connect with MySQL Workbench

### 4.1 Create a connection for `price_db`

1. Open MySQL Workbench.

2. Click the `+` icon next to “MySQL Connections”.

3. Fill in:

   * Connection Name: `price_db_docker`
   * Hostname: `127.0.0.1`
   * Port: `3307`
   * Username: `root`
   * Password: `rootpass` (Click “Store in Vault”)

4. Click “Test Connection” → OK → Save.

### 4.2 Create a connection for `fundamentals_db`

Repeat the same steps, but:

* Connection Name: `fundamentals_db_docker`
* Port: `3308`

---

## 5. Create Databases and Tables

You must do this once per fresh Docker instance.

### 5.1 Price database schema

1. Open the `price_db_docker` connection.
2. Create a new query tab and run:

```sql
CREATE DATABASE IF NOT EXISTS price_db;
USE price_db;

CREATE TABLE IF NOT EXISTS prices (
  id INT AUTO_INCREMENT PRIMARY KEY,
  symbol VARCHAR(32) NOT NULL,
  trade_date DATE NOT NULL,
  open_price  DECIMAL(12,4),
  high_price  DECIMAL(12,4),
  low_price   DECIMAL(12,4),
  close_price DECIMAL(12,4) NOT NULL,
  volume BIGINT,
  INDEX idx_symbol_date (symbol, trade_date)
);
```

3. In the “Schemas” panel, right-click and choose “Refresh All”.
   You should see a schema `price_db` with a `prices` table under it.

### 5.2 Fundamentals database schema

1. Open the `fundamentals_db_docker` connection.
2. Create a new query tab and run:

```sql
CREATE DATABASE IF NOT EXISTS fundamentals_db;
USE fundamentals_db;

CREATE TABLE IF NOT EXISTS fundamentals (
  id INT AUTO_INCREMENT PRIMARY KEY,
  symbol VARCHAR(32) NOT NULL,
  fy INT NOT NULL,
  gross_profit_margin FLOAT NULL,
  operating_profit_margin FLOAT NULL,
  net_profit_margin FLOAT NULL,
  roe FLOAT NULL,
  roic FLOAT NULL,
  return_on_assets FLOAT NULL,
  return_on_capital_employed FLOAT NULL,
  debt_equity_ratio FLOAT NULL,
  debt_ratio FLOAT NULL,
  net_debt_to_ebitda FLOAT NULL,
  interest_coverage FLOAT NULL,
  current_ratio FLOAT NULL,
  quick_ratio FLOAT NULL,
  cash_ratio FLOAT NULL,
  asset_turnover FLOAT NULL,
  inventory_turnover FLOAT NULL,
  receivables_turnover FLOAT NULL,
  payables_turnover FLOAT NULL,
  cash_conversion_cycle FLOAT NULL,
  operating_cf_per_share FLOAT NULL,
  free_cf_per_share FLOAT NULL,
  free_cf_yield FLOAT NULL,
  pe_ratio FLOAT NULL,
  pb_ratio FLOAT NULL,
  price_to_sales_ratio FLOAT NULL,
  price_to_fcf_ratio FLOAT NULL,
  price_to_ocf_ratio FLOAT NULL,
  dividend_yield FLOAT NULL,
  dividend_payout_ratio FLOAT NULL,
  earnings_yield FLOAT NULL,
  ev_to_sales FLOAT NULL,
  ev_to_ebitda FLOAT NULL,
  market_cap BIGINT NULL,
  book_value_per_share FLOAT NULL,
  revenue_per_share FLOAT NULL,
  net_income_per_share FLOAT NULL,
  shareholders_equity_per_share FLOAT NULL,
  INDEX idx_symbol_fy (symbol, fy)
);
```

3. Refresh the “Schemas” panel.
   You should see `fundamentals_db` with a `fundamentals` table.

---

## 6. Import CSV data into MySQL

Both CSVs are already cleaned and match the schemas exactly.

### 6.1 Import `prices.csv` into `price_db.prices`

1. Make sure `data/prices.csv` from the repo is accessible from your machine.
2. In Workbench, open `price_db_docker`.
3. In the Schemas panel:

   * Expand `price_db → Tables`
   * Right-click `prices`
   * Choose “Table Data Import Wizard”
4. Select the file `FINSIGHT/data/prices.csv`.
5. Confirm target table `prices`.
6. Mapping step:

   * Map `symbol` → `symbol`
   * Map `trade_date` → `trade_date`
   * Map `open_price` → `open_price`
   * Map `high_price` → `high_price`
   * Map `low_price` → `low_price`
   * Map `close_price` → `close_price`
   * Map `volume` → `volume`
   * Do not map anything to `id` (it is auto-increment)
7. Complete the wizard.

To check:

```sql
USE price_db;
SELECT symbol, COUNT(*) AS n FROM prices GROUP BY symbol;
```

You should see counts for the nine target symbols.

### 6.2 Import `fundamentals.csv` into `fundamentals_db.fundamentals`

1. In Workbench, open `fundamentals_db_docker`.
2. In the Schemas panel:

   * Expand `fundamentals_db → Tables`
   * Right-click `fundamentals`
   * Choose “Table Data Import Wizard”
3. Select `FINSIGHT/data/fundamentals.csv`.
4. Confirm target table `fundamentals`.
5. Mapping step: map each CSV column name to the identically-named table column; do not map to `id`.
6. Complete the wizard.

To check:

```sql
USE fundamentals_db;
SELECT symbol, COUNT(*) AS n FROM fundamentals GROUP BY symbol;
```

You should see rows for each of the chosen companies.

At this point, the data layer is ready.

---

## 7. Python Environment Setup

These commands are run from the `FINSIGHT` root.

### 7.1 Create and activate a virtual environment (optional but recommended)

```bash
cd FINSIGHT
python -m venv .venv
```

Activate:

* On Windows (PowerShell):

  ```bash
  .venv\Scripts\Activate.ps1
  ```

* On Windows (cmd):

  ```bash
  .venv\Scripts\activate.bat
  ```

* On Linux/macOS:

  ```bash
  source .venv/bin/activate
  ```

### 7.2 Install Python dependencies

```bash
pip install -r requirements.txt
```

Or manually:

```bash
pip install pandas mysql-connector-python python-dateutil requests
```

These packages provide:
- `pandas` - Data manipulation
- `mysql-connector-python` - MySQL database connectivity
- `python-dateutil` - Date parsing
- `requests` - HTTP client for Ollama API calls

### 7.3 Set up Ollama (Optional but Recommended)

For LLM-powered natural language query understanding:

1. **Install Ollama** - Follow the detailed guide in [OLLAMA_SETUP.md](OLLAMA_SETUP.md)
2. **Pull Mistral model**:
   ```bash
   ollama pull mistral
   ```
3. **Verify installation**:
   ```bash
   ollama list
   ```

**Without Ollama**: The system will automatically fall back to regex-based parsing. You'll see a warning message but the system will continue to work.

---

## 8. Configure DB access in Python

Open `src/config.py`. It should look like this (edit ports/passwords only if you changed the Docker setup):

```python
# src/config.py

PRICE_DB = {
    "host": "127.0.0.1",
    "port": 3307,          # port mapped for price_db
    "user": "root",
    "password": "rootpass",
    "database": "price_db",
}

FUND_DB = {
    "host": "127.0.0.1",
    "port": 3308,          # port mapped for fundamentals_db
    "user": "root",
    "password": "rootpass",
    "database": "fundamentals_db",
}
```

Adjust only if your Docker ports or credentials are different.

---

## 9. Testing DB connectivity from Python

From the `FINSIGHT` root (with the virtual environment active):

```bash
cd src
python db_utils.py
```

This script:

* connects to both databases using `config.py`
* runs simple `SELECT` queries counting rows per symbol
* prints the resulting DataFrames

If this completes and shows counts for each symbol, the Python ↔ MySQL path is working.

---

## 10. What each Python file does

All Python files are in `src/`.

### 10.1 `config.py`

Holds configuration dictionaries for the two MySQL databases:

* `PRICE_DB`
* `FUND_DB`

These are used by `db_utils.py` to create connections.

### 10.2 `db_utils.py`

Provides helper functions to run SQL and return `pandas.DataFrame` objects:

* `query_price_db(sql: str, params=None) -> DataFrame`

  * Connects to `price_db` using `mysql.connector`
  * Executes the given query using `pandas.read_sql`
  * Returns the result as a DataFrame

* `query_fund_db(sql: str, params=None) -> DataFrame`

  * Same pattern, but connects to `fundamentals_db`

The `__main__` block at the bottom runs a simple smoke test when you call:

```bash
python db_utils.py
```

### 10.3 `analyzer.py`

Implements the query analysis and decomposition logic.

Key components:

* `QueryPlan` dataclass:

  * Holds parsed information such as:

    * `start_date`, `end_date`
    * list of `symbols` mentioned
    * thresholds like `min_price_growth`, `max_debt_equity`, `min_roe`, `max_pe`
    * `fy` (financial year)
    * `sql_price`, `sql_fund` for the actual sub-queries

* `_parse_time_window(text)`:

  * Extracts year-related information (e.g., 2016, 2017, “last year”) and maps to a date range and FY.

* `_parse_thresholds(text)`:

  * Uses regex to find patterns like:

    * “price growth 20%”
    * “debt equity < 1”
    * “ROE > 15”
    * “PE < 25”

* `_detect_symbols(text)`:

  * Matches known tickers (RELIANCE, HDFCBANK, etc.) in the text.

* `analyze_query(nl_query) -> QueryPlan`:

  * Combines the above helpers to produce a filled `QueryPlan` without SQL.

* `build_sql(plan) -> QueryPlan`:

  * Uses the information in `plan` to construct:

    * `plan.sql_price` – a grouped query over the `prices` table computing start price, end price, and price growth.
    * `plan.sql_fund` – a query over `fundamentals` selecting ROE, debt-equity, PE, and related fields.

* `analyze_and_decompose(nl_query) -> QueryPlan`:

  * External entrypoint: runs `analyze_query` then `build_sql`.

This file directly addresses “Analyze” and “Decompose” parts of your assignment rubric.

### 10.4 `federator.py`

Coordinates NL query analysis and database execution.

* Imports:

  * `analyze_and_decompose` from `analyzer`
  * `query_price_db`, `query_fund_db` from `db_utils`

* `run_federated_query(nl_query: str) -> (QueryPlan, DataFrame, DataFrame)`:

  * Calls `analyze_and_decompose` to obtain a `QueryPlan`.
  * Executes `plan.sql_price` on `price_db` and `plan.sql_fund` on `fundamentals_db`.
  * Returns:

    * the `QueryPlan`
    * the price DataFrame
    * the fundamentals DataFrame

Running:

```bash
python federator.py
```

runs a sample query and prints sample results.
This covers the “federate” and “execute” parts of your assignment.

### 10.5 `integrator.py`

Merges the federated results and applies filters from the `QueryPlan`.

Main function:

* `integrate(plan, df_price, df_fund) -> list[dict]`:

  * Deduplicates fundamentals data to the latest FY per symbol.
  * Merges `df_price` and `df_fund` on `symbol`.
  * Applies thresholds from `plan`:

    * minimum price growth
    * maximum debt-equity ratio
    * minimum ROE
    * maximum PE
  * For each matching stock, creates a result dictionary containing:

    * symbol
    * start and end prices
    * computed `price_growth`
    * ROE
    * debt-equity ratio
    * PE
    * current ratio
    * market cap
    * `llm_commentary` (see `llm_client.py`)

This is the “results integration” step.

### 10.6 `llm_client.py`

**LLM integration module** that handles communication with Ollama.

Functions:

* **NEW** `check_ollama_status() -> bool`:
  * Checks if Ollama is running and the configured model is available
  * Used to determine whether to use LLM or fallback parsing

* **NEW** `call_ollama(prompt, temperature, max_tokens) -> str`:
  * Sends HTTP request to Ollama API
  * Configured for `mistral` model by default
  * Uses low temperature (0.1) for SQL generation for more deterministic outputs
  * Returns the generated response

* `load_report_text(symbol, fy)`:
  * Looks for `data/reports/{SYMBOL}_{FY}.txt` and returns its contents if present.
  * In this zipped project you may not have reports; in that case it returns an empty string.

* `build_llm_prompt(symbol, report_text)`:
  * Constructs a natural-language prompt that explains what the LLM should summarize.

* `call_llm(prompt)`:
  * Wrapper for calling Ollama for general text generation (report summaries)
  * Uses higher temperature (0.3) for more creative output
  * Returns placeholder if Ollama is not available

**Configuration**:
```python
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "mistral"  # Can be changed to "llama3.2" or other models
```

See [OLLAMA_SETUP.md](OLLAMA_SETUP.md) for detailed configuration options.

### 10.7 `main_cli.py`

Command-line interface for demonstrating the full pipeline.

* Prompts the user:

  ```text
  Finsight CLI – type a query (or 'q' to quit).
  ```

* For each input query:

  1. Calls `run_federated_query` to:

     * analyze and decompose the query
     * execute on both databases

  2. Calls `integrate(plan, df_price, df_fund)` to:

     * join the results
     * apply filters and build result objects
     * attach an LLM commentary placeholder

  3. Prints a summary block for each matched stock.

To run:

```bash
cd FINSIGHT/src
python main_cli.py
```

Example queries the system is designed to handle:

**With LLM (Ollama + Mistral)**:
* `show companies with price growth 20% in 2017 and debt equity < 1 and ROE > 15 and PE < 25`
* `which stocks had strong price growth last year with low debt equity`
* `compare price growth and ROE for RELIANCE and HDFCBANK in 2016`
* `find stocks with good fundamentals in 2017`
* `show me high growth companies with low PE ratio`
* `stocks with debt equity below 1.5 and ROE above 12`

**Without LLM (Fallback regex parser)**:
* Requires more specific phrasing with exact keywords
* `show companies with price growth 20% in 2017 and debt equity < 1 and ROE > 15`
* Works but less flexible than LLM mode

The LLM mode provides much better natural language understanding and can handle variations in phrasing.

---

## 11. Running the full system end to end

1. Ensure Docker containers are running:

   ```bash
   cd FINSIGHT/db
   docker compose up -d
   ```

2. Verify MySQL data is present via Workbench:

   * `SELECT COUNT(*) FROM price_db.prices;`
   * `SELECT COUNT(*) FROM fundamentals_db.fundamentals;`

3. Activate the virtual environment and install requirements:

   ```bash
   cd FINSIGHT
   .venv\Scripts\Activate.ps1     # or activate.bat / source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **(Optional but Recommended)** Set up Ollama:

   ```bash
   # Install Ollama from https://ollama.ai
   ollama pull mistral
   ollama list  # Verify installation
   ```

   See detailed instructions in [OLLAMA_SETUP.md](OLLAMA_SETUP.md)

5. Test DB connections:

   ```bash
   cd src
   python db_utils.py
   ```

6. Run a federated query test:

   ```bash
   python federator.py
   ```

7. Run the interactive CLI:

   ```bash
   python main_cli.py
   ```

   If Ollama is running, you'll see:
   ```
   Finsight CLI – type a query (or 'q' to quit).
   >
   ```

   If Ollama is not available, you'll see:
   ```
   Warning: Ollama not available, using fallback regex parser
   ```

8. Type a query, observe the integrated output.

Example session:
```
> show companies with price growth 20% in 2017 and ROE > 15

Analyzing and decomposing query...

Executing and integrating results...

======================================
Symbol        : TCS
Price growth  : 25.34% (from 2250.50 to 2820.75)
ROE           : 18.50
Debt/Equity   : 0.15
P/E           : 22.30
Current Ratio : 2.45
Market Cap    : 850000000000

LLM commentary:
[Generated summary based on fundamentals...]
```

---

## 12. Architecture Overview

### Data Flow

```
User Query (Natural Language)
         ↓
    Analyzer (with LLM)
         ↓
    Query Plan (parsed parameters)
         ↓
    SQL Builder (generates queries)
         ↓
    Federator (executes on both DBs)
         ↓
    Integrator (joins & filters results)
         ↓
    Output (with LLM commentary)
```

### LLM Integration Benefits

1. **Natural Language Understanding**: More flexible query interpretation
2. **User-Friendly**: No need to learn specific syntax
3. **Extensible**: Easy to add new query patterns
4. **Robust**: Automatic fallback ensures system always works
5. **Context-Aware**: Better handling of ambiguous queries

---

## 13. Troubleshooting

### LLM Issues

**"Ollama not available"**:
- Install Ollama from https://ollama.ai
- Ensure Ollama service is running
- Pull the Mistral model: `ollama pull mistral`

**Slow LLM responses**:
- Consider using a smaller model like `llama3.2`
- Increase timeout in `llm_client.py`
- Check system resources (8GB+ RAM recommended)

### Database Issues

**Connection refused**:
- Ensure Docker containers are running: `docker ps`
- Check ports 3307 and 3308 are not in use
- Verify credentials in `src/config.py`

**No data returned**:
- Verify CSVs were imported correctly
- Run test queries in MySQL Workbench
- Check for authentication plugin errors (see docker-compose.yml for fix)

---

## 14. Additional Resources

- **[OLLAMA_SETUP.md](OLLAMA_SETUP.md)** - Comprehensive Ollama installation and configuration guide
- **requirements.txt** - Python package dependencies
- **db/docker-compose.yml** - Database container configuration

---



## Web UI (Flask + React SPA)

Steps (from repo root):
1. Start databases: `docker compose -f db/docker-compose.yml up -d`
2. (Optional) Activate venv: `python -m venv .venv` then `.venv\Scripts\Activate.ps1` (or `source .venv/bin/activate`)
3. Install deps (Flask included): `pip install -r requirements.txt`
4. Run the web app: `python src/web_app.py`
5. Open http://localhost:5000 in your browser.

API endpoints:
- `POST /api/query` with `{ "nl_query": "..." }` returns `plan`, `results`, and optional `llm_summary`.
- `GET /api/health` checks DB connectivity and Ollama status.

The CLI in `src/main_cli.py` still works; the web UI is an additional entrypoint served from `web/index.html`.
