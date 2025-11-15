# Ollama Setup Guide for FinSight

This guide will help you set up Ollama with Mistral for natural language to SQL conversion in FinSight.

## Why Mistral?

We chose **Mistral** over Llama 3.2 for the following reasons:
- **Better SQL Generation**: Mistral excels at structured outputs and technical tasks
- **Instruction Following**: Superior at following complex prompts with specific formatting requirements
- **JSON Output**: More reliable at producing valid JSON responses
- **Smaller Model Size**: Efficient performance without requiring excessive resources

## Installation Steps

### 1. Install Ollama

#### Windows
1. Download Ollama from: https://ollama.ai/download
2. Run the installer
3. Ollama will automatically start as a background service

#### Linux/Mac
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

### 2. Verify Ollama is Running

Open a terminal and run:
```bash
ollama --version
```

You should see the version number. Ollama runs on `http://localhost:11434` by default.

### 3. Pull the Mistral Model

Download the Mistral model (recommended):
```bash
ollama pull mistral
```

This will download the Mistral 7B model (~4.1GB).

**Alternative Models** (if you prefer):
```bash
# For Llama 3.2 instead (if you have more resources)
ollama pull llama3.2

# For a smaller, faster model
ollama pull mistral:7b-instruct
```

### 4. Verify Model Installation

```bash
ollama list
```

You should see `mistral` in the list of models.

### 5. Test the Model

```bash
ollama run mistral "Hello, how are you?"
```

Press `Ctrl+D` or type `/bye` to exit the interactive session.

## Configuration

The default configuration in `src/llm_client.py` is:

```python
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "mistral"  # Change to "llama3.2" if you prefer
```

### Using a Different Model

To use Llama 3.2 instead:

1. Pull the model: `ollama pull llama3.2`
2. Edit `src/llm_client.py` and change:
   ```python
   OLLAMA_MODEL = "llama3.2"
   ```

## Testing the Integration

### 1. Test Ollama Connectivity

```python
python -c "from src.llm_client import check_ollama_status; print('Ollama is', 'available' if check_ollama_status() else 'not available')"
```

### 2. Test the Analyzer

```bash
cd src
python analyzer.py
```

This will run the built-in test query with LLM-powered analysis.

### 3. Test the Full CLI

```bash
python src/main_cli.py
```

Try queries like:
- "show companies with price growth 20% in 2017"
- "find stocks with ROE > 15 and debt equity < 1"
- "show RELIANCE and TCS performance in 2016"

## How It Works

### Natural Language → SQL Pipeline

1. **User Query**: "show companies with price growth 20% in 2017 and ROE > 15"

2. **LLM Processing**: The query is sent to Mistral with a detailed prompt containing:
   - Database schema information
   - Available stock symbols
   - Expected JSON output format
   - Parsing rules for dates, percentages, etc.

3. **LLM Response**: Mistral returns structured JSON:
   ```json
   {
     "start_date": "2017-01-01",
     "end_date": "2017-12-31",
     "symbols": null,
     "min_price_growth": 0.20,
     "max_debt_equity": null,
     "min_roe": 15.0,
     "max_pe": null,
     "fy": 2017
   }
   ```

4. **SQL Generation**: The parsed parameters are used to build SQL queries:
   - Price query: Filters by date range and calculates price growth
   - Fundamentals query: Filters by financial metrics (ROE, debt/equity, etc.)

5. **Fallback**: If Ollama is unavailable or parsing fails, the system automatically falls back to regex-based parsing

## Performance Optimization

### Temperature Settings

The code uses different temperatures for different tasks:
- **SQL Query Analysis**: `temperature=0.1` (more deterministic)
- **Report Summaries**: `temperature=0.3` (more creative)

### Model Selection Guidelines

| Model | Size | Speed | Accuracy | Use Case |
|-------|------|-------|----------|----------|
| mistral | 4.1GB | Fast | High | **Recommended** - Best balance |
| llama3.2 | 2GB | Very Fast | Good | Limited resources |
| mistral:7b-instruct | 4.1GB | Fast | Very High | Maximum accuracy |

## Troubleshooting

### Ollama Not Found
```
Error: Could not connect to Ollama
```
**Solution**: Make sure Ollama is installed and running. Restart the Ollama service.

### Model Not Found
```
Warning: Ollama not available, using fallback regex parser
```
**Solution**: Pull the model with `ollama pull mistral`

### Slow Responses
**Solution**: 
- Use a smaller model like `llama3.2`
- Reduce `max_tokens` in `llm_client.py`
- Ensure you have enough RAM (8GB+ recommended)

### JSON Parsing Errors
**Solution**: The system automatically falls back to regex parsing. Check the console output for details.

## Advanced Configuration

### Custom Ollama Host

If running Ollama on a different machine:

```python
# In src/llm_client.py
OLLAMA_BASE_URL = "http://192.168.1.100:11434"
```

### Timeout Adjustment

For slower systems, increase the timeout:

```python
# In src/llm_client.py, call_ollama function
response = requests.post(url, json=payload, timeout=120)  # Increase from 60
```

## Example Queries

The LLM can understand various natural language patterns:

```
✓ "show companies with price growth 20% in 2017"
✓ "find stocks with ROE greater than 15 and debt equity less than 1"
✓ "show RELIANCE and TCS performance in 2016"
✓ "companies with PE ratio under 25 in last year"
✓ "high growth stocks in 2017 with low debt"
✓ "ICICIBANK and HDFCBANK fundamentals"
```

## Benefits Over Regex Parsing

1. **Natural Language**: More flexible query understanding
2. **Context Awareness**: Better handling of ambiguous queries
3. **Extensibility**: Easy to add new query patterns without code changes
4. **User-Friendly**: No need to learn specific syntax
5. **Robust**: Handles variations in phrasing naturally

---

**Note**: The system includes automatic fallback to regex parsing if Ollama is unavailable, ensuring continuous operation even without LLM support.
