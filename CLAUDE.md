# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install (prefer uv or pip)
pip install .
# or
uv sync

# Run CLI
tradingagents
python -m cli.main

# Run a quick programmatic analysis
python main.py

# Run all tests
pytest

# Run a single test file
pytest tests/test_signal_processing.py

# Run only unit tests (fast, no external services)
pytest -m unit

# Run with Docker
cp .env.example .env   # fill in API keys first
docker compose run --rm tradingagents
```

## Architecture

The system is a **LangGraph state machine** where specialized LLM agents pass reports through a shared `AgentState` dict, culminating in a BUY/HOLD/SELL decision.

### Execution flow

```
Analysts (parallel reports) → Bull/Bear Researchers (debate) → Research Manager
  → Trader → Risk Team (3-way debate) → Portfolio Manager (final decision)
```

The graph is assembled in `graph/setup.py:GraphSetup.setup_graph()`. The set of analysts is configurable at init time via `selected_analysts`. Entry point is `TradingAgentsGraph.propagate(ticker, date)` in `graph/trading_graph.py`.

### Key layers

| Layer | Location | Role |
|---|---|---|
| **Graph orchestration** | `graph/` | LangGraph wiring, checkpointing, reflection, signal processing |
| **Agents** | `agents/analysts/`, `agents/researchers/`, `agents/risk_mgmt/`, `agents/trader/` | LLM prompt + tool binding per role |
| **Tools** | `agents/utils/*_tools.py` | LangChain `@tool` wrappers that delegate to dataflows |
| **Dataflows** | `dataflows/` | Actual data fetching (yfinance, Alpha Vantage) |
| **LLM clients** | `llm_clients/` | Provider abstraction over LangChain clients |

### Data vendor routing

All tool calls go through `dataflows/interface.py:route_to_vendor()`. Vendor selection is controlled by `config["data_vendors"]` (category level) and `config["tool_vendors"]` (tool level, takes precedence). Current vendors: `yfinance`, `alpha_vantage`.

To add a new data source: implement the function in a new `dataflows/my_vendor.py`, import it in `interface.py`, and add it to `VENDOR_METHODS`.

### Adding a new analyst

1. Create `agents/analysts/my_analyst.py` with a `create_my_analyst(llm)` factory returning a node function.
2. Add tool-routing logic in `graph/conditional_logic.py` (`should_continue_my`).
3. Register in `graph/setup.py` under `setup_graph()`.
4. Export from `agents/__init__.py`.

### State

`AgentState` (defined in `agents/utils/agent_states.py`) is the shared LangGraph state. Each analyst writes its report into a dedicated field (`market_report`, `sentiment_report`, `news_report`, `fundamentals_report`). Adding new analysts requires adding a new field here.

### LLM clients

`llm_clients/factory.py:create_llm_client(provider, model)` is the single factory. OpenAI-compatible providers (xai, deepseek, qwen, glm, ollama, openrouter) all use `OpenAIClient` with a custom `base_url`. Google and Anthropic have dedicated client classes. All clients extend `BaseLLMClient` and expose `.bind_tools()` and `.bind_structured()`.

### Persistence

- **Decision log**: Always on. Appends to `~/.tradingagents/memory/trading_memory.md`. On subsequent runs for the same ticker, prior decisions + reflections are injected into the Portfolio Manager prompt. Override path with `TRADINGAGENTS_MEMORY_LOG_PATH`.
- **Checkpoint resume**: Opt-in (`config["checkpoint_enabled"] = True` or `--checkpoint` CLI flag). SQLite DBs at `~/.tradingagents/cache/checkpoints/<TICKER>.db`. Override base with `TRADINGAGENTS_CACHE_DIR`.

### Configuration

All runtime options live in `DEFAULT_CONFIG` (`tradingagents/default_config.py`). Pass a modified copy to `TradingAgentsGraph(config=...)`. Key fields: `llm_provider`, `deep_think_llm`, `quick_think_llm`, `max_debate_rounds`, `max_risk_discuss_rounds`, `data_vendors`, `output_language`.

### Instrument support

The codebase is built for **US-listed stocks**. International stocks work via yfinance suffix notation (e.g. `HSBA.L`, `7203.T`, `0700.HK`) for price/technical data, but fundamentals and news coverage degrade for non-US tickers. Forex and crypto are not natively supported — the fundamentals analyst, news queries, and BUY/HOLD/SELL output schema all assume equity instruments.
