# AI Personal Finance — Architecture

## Overview

AI Personal Finance is a Telegram-based personal finance assistant powered by Google Gemini and LangGraph. It allows users to manage their finances through natural language, voice messages, photos of receipts, and bank statement documents, all stored in [Actual Budget](https://actualbudget.org/).

---

## Architecture Diagram

```
┌───────────────────────────────────────┐       ┌──────────────────────────────────┐
│  Same Process (Python)                │       │  Docker                          │
│                                       │       │                                  │
│  ┌──────────┐   ┌───────────────────┐ │ HTTP  │  ┌──────────────────────────────┐ │
│  │ Telegram │──▶│  LangGraph Agent  │─┼───────┼─▶│  actual-http-api             │ │
│  │ Bot      │◀──│  (Gemini + Tools)  │◀┼───────┼──│  (jhonderson/actual-http-   │ │
│  └──────────┘   └─────────┬─────────┘ │       │  │   api)                       │ │
│                           │           │       │  └──────────┬───────────────────┘ │
│                    ┌──────▼──────┐    │       │             │ @actual-app/api     │
│                    │   Gemini    │    │       │             ▼                     │
│                    │   API       │    │       │  ┌──────────────────────────────┐ │
│                    └─────────────┘    │       │  │  Actual Budget Server       │ │
│                                       │       │  │  (actualbudget/actual-      │ │
│                                       │       │  │   server)                    │ │
│                                       │       │  └──────────────────────────────┘ │
└───────────────────────────────────────┘       └──────────────────────────────────┘
```

---

## Project Structure

```
ai-personal-finanza/
├── src/
│   ├── __init__.py
│   ├── main.py                # Entry point — starts bot polling + agent
│   ├── config.py              # Environment variable loading & validation
│   ├── bot.py                 # Telegram bot handlers (logic only)
│   │                          #   - text: direct message
│   │                          #   - voice: audio transcription via Gemini
│   │                          #   - photo: receipt OCR via Gemini Vision
│   │                          #   - document: PDF/bank statement parsing
│   ├── agent.py               # LangGraph StateGraph definition (logic only)
│   │                          #   Node 1: multimodal_preprocessor
│   │                          #   Node 2: financial_agent
│   │                          #   Conditional edge: tool call or respond
│   ├── tools.py               # Agent tools (decorated with @tool)
│   │                          #   - add_transaction, add_split_transaction
│   │                          #   - get_accounts, get_balances, get_budget
│   │                          #   - get_transactions, analyze_spending
│   │                          #   - get_recommendations
│   ├── multimodal.py          # MediaProcessor class (Gemini calls)
│   ├── middleware_client.py   # HTTP client for actual-http-api
│   ├── prompts/               # All prompt strings, separated from logic
│   │   ├── __init__.py
│   │   ├── multimodal.py      #   _TRANSCRIBE, _RECEIPT, _STATEMENT prompts
│   │   ├── agent.py           #   _SYSTEM_PROMPT for the LLM agent
│   │   └── bot.py             #   WELCOME_MESSAGE, HELP_MESSAGE
│   └── schemas/               # Pydantic response schemas
│       ├── __init__.py
│       └── multimodal.py      #   ReceiptItem, Receipt, BankTx, BankStatement
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # Shared fixtures (mock client, env vars)
│   └── test_tools.py          # 11 tests for all agent tools
├── docker-compose.yml         # 3 services: actual-server, actual-http-api, app
├── Dockerfile                 # Python application image
├── Dockerfile.test            # Test image (installs deps + runs pytest)
├── requirements.txt           # Python dependencies
├── .env.example               # Environment variable template
├── ARCHITECTURE.md            # This file
└── AGENTS.md                  # Agent / AI assistant guide
```

---

## Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Messaging** | [python-telegram-bot](https://python-telegram-bot.org/) v21+ | Telegram bot polling and message handling |
| **Agent Framework** | [LangGraph](https://langchain-ai.github.io/langgraph/) | State graph orchestration for the AI agent |
| **LLM** | [Gemini](https://ai.google.dev/) via `langchain-google-genai` | Natural language understanding, multimodal processing, financial analysis |
| **Middlewar** | [jhonderson/actual-http-api](https://hub.docker.com/r/jhonderson/actual-http-api) | REST API wrapper over the Actual Budget Node.js SDK |
| **Financial Engine** | [Actual Budget](https://actualbudget.org/) (`actualbudget/actual-server`) | Open-source personal finance manager |
| **HTTP Client** | [httpx](https://www.python-httpx.org/) | Async HTTP calls to the middleware |
| **Containerization** | Docker + Docker Compose | Service orchestration |

---

## Design Patterns

### 1. Agentic Loop (LangGraph ReAct)

The core pattern is a **ReAct (Reasoning + Acting)** loop implemented with LangGraph's `StateGraph`:

```
User Input
    │
    ▼
┌──────────────────┐
│  Preprocessor    │  Only if media is attached
│  (if needed)     │  Transcribes audio, extracts receipt items,
│                  │  parses bank statements via Gemini
└────────┬─────────┘
         │ text
         ▼
┌──────────────────┐
│  Financial Agent │  Gemini decides: respond or call a tool
│  (LLM + Tools)   │
└────────┬─────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
 Respond   Call Tool
              │
              ▼
         Middleware HTTP
              │
              ▼
         Actual Budget
```

**State**: A `TypedDict` with `messages` (conversation history), `media` (optional processed media), and `tool_results`.

### 2. Tool-as-a-Function

Each capability is exposed as a typed Python function decorated with `@tool` from LangChain. Tools receive structured arguments from Gemini's function calling and return structured results.

```python
@tool
def add_split_transaction(
    account: str,
    payee_name: str,
    amount: int,
    date: str,
    subtransactions: list[dict],
    notes: str = ""
) -> dict:
    """Create a split transaction with individual line items from a receipt."""
```

### 3. Middleware as Anti-Corruption Layer

`actual-http-api` acts as an **anti-corruption layer** between our Python agent and Actual Budget's Node.js SDK. It:

- Translates between REST/JSON and the Actual Budget sync protocol
- Manages the Actual Budget session lifecycle (init, download budget, shutdown)
- Handles authentication, retries, and error normalization
- Exposes a consistent HTTP API regardless of Actual Budget version changes

### 4. Strategy Pattern for Media Processing

The multimodal preprocessor uses a strategy pattern based on media type:

```python
class MediaProcessor:
    def process(self, media_type: str, media_data: bytes) -> str:
        strategies = {
            "voice": self._transcribe_audio,
            "photo": self._extract_receipt,
            "document": self._parse_document,
        }
        return strategies[media_type](media_data)
```

### 5. Prompt / Schema Separation

Prompts (LLM instructions) and schemas (structured output models) live in separate directories, decoupled from logic:

```
src/
├── prompts/           # Pure prompt strings — no imports from logic
│   ├── agent.py       #   _SYSTEM_PROMPT
│   ├── bot.py         #   WELCOME_MESSAGE, HELP_MESSAGE
│   └── multimodal.py  #   _TRANSCRIBE/RECEIPT/STATEMENT_PROMPT
├── schemas/           # Pydantic models — no side effects
│   └── multimodal.py  #   ReceiptItem, Receipt, BankTx, BankStatement
├── agent.py           # Imports _SYSTEM_PROMPT from prompts/agent.py
├── bot.py             # Imports WELCOME/HELP from prompts/bot.py
└── multimodal.py      # Imports prompts and schemas from their packages
```

**Rationale**:
- **Iteration speed**: editing a prompt never requires touching a logic file — reduces merge conflicts and accidental regressions.
- **Testability**: prompts can be reviewed, versioned, or A/B tested independently.
- **Single responsibility**: no file mixes LLM instructions with HTTP calls, graph definitions, or message handling.

### 6. Singleton Configuration

`config.py` loads environment variables once at startup and validates them eagerly, failing fast if anything is missing.

---

## Key Technical Decisions

### 1. Same Process for Bot and Agent

The Telegram bot and LangGraph agent run in the **same Python process**. This keeps latency low (no inter-process communication) and simplifies deployment to a single container. The agent is instantiated once and reused across all messages.

**Trade-off**: Less horizontal scalability, but for a single-user application this is negligible.

### 2. Split Transactions for Receipt Line Items

Actual Budget natively supports **split transactions** via the `subtransactions` field on a transaction object. When a user uploads a receipt:

- **Parent transaction**: Total amount (matches bank statement, for reconciliation)
- **Child transactions** (`subtransactions`): Individual line items, each with its own `amount`, `category`, and `notes`

This was chosen over storing items as JSON in the `notes` field because:

| Aspect | JSON in notes | Native split transactions |
|---|---|---|
| UI visibility | Invisible in register | Expandable in register |
| Per-item categorization | Not possible | Each child has own category |
| Queries | Requires parsing | Native ActualQL support |
| Reports | Items invisible | Items appear in reports |

### 3. actual-http-api Over actualpy

`jhonderson/actual-http-api` wraps the official `@actual-app/api` Node.js SDK and exposes it via REST. This was chosen over `actualpy` (a pure Python implementation of the Actual sync protocol) because:

- Uses the **official SDK** — guaranteed compatibility with Actual Budget versions
- More robust and battle-tested
- Handles session management, encryption, and sync automatically
- Adds minimal complexity — just another Docker container

### 4. Gemini as Single LLM Provider

Gemini is the sole LLM provider because:

- **Multimodal natively**: Processes text, audio, images, and PDFs without separate transcription/OCR services
- **Google AI Studio**: Generous free tier for development
- **Tool calling**: First-class support for function calling (essential for the ReAct loop)
- **`langchain-google-genai`**: Well-integrated with LangGraph

### 5. No Conversational Memory Persistence

The agent operates with **session-only memory** — it doesn't persist conversation history between restarts. For a single-user finance assistant focused on transactions and queries (rather than ongoing conversation), this keeps the implementation simple and avoids data privacy concerns.

**Note:** If conversational memory becomes desirable, LangGraph supports checkpointers backed by SQLite or PostgreSQL.

### 6. Amounts in Cents (Integers)

Following Actual Budget's convention, all monetary amounts are stored as **integers in cents** (e.g., €12.99 = 1299). This avoids floating-point precision issues. The middleware and agent handle conversion at the boundaries.

---

## Data Flow: Receipt Upload (Most Complex Path)

```
1. User sends photo of receipt
       │
2. Bot handler (photo)
       │  ├── download file from Telegram → bytes
       │  └── classify media type
       │
3. Multimodal preprocessor (Gemini Vision)
       │  ├── prompt: "Extract all items from this receipt as JSON"
       │  ├── response: {store, date, total, items[], tax, payment_method}
       │  └── validate & clean extracted data
       │
4. LangGraph Agent (financial_agent node)
       │  ├── receives structured JSON
       │  ├── Gemini decides to call add_split_transaction
       │  └── builds tool arguments
       │
5. Tool: add_split_transaction
       │  ├── constructs HTTP request body
       │  │   {
       │  │     "amount": 8250,
       │  │     "payee_name": "Mercadona",
       │  │     "is_parent": true,
       │  │     "subtransactions": [...]
       │  │   }
       │  └── POST to actual-http-api /v1/transactions
       │
6. actual-http-api (Node.js)
       │  ├── @actual-app/api.init()
       │  ├── api.addTransactions(accountId, [parent + children])
       │  └── api.shutdown()
       │
7. Actual Budget Server
       │  └── stores split transaction in SQLite
       │
8. Bot response
       └── "✅ Mercadona €82.50 - 15 items registrados"
```

---

## Communication Protocols

| Between | Protocol | Auth | Port |
|---|---|---|---|
| Telegram Bot ↔ Telegram API | HTTPS (Webhook/Polling) | Bot Token | 443 (outbound) |
| LangGraph Agent ↔ Gemini API | gRPC/HTTPS | API Key | 443 (outbound) |
| LangGraph Agent ↔ actual-http-api | HTTP/REST | `x-api-key` header | 5007 (internal) |
| actual-http-api ↔ Actual Server | HTTP (Node.js SDK) | Server Password | 5006 (internal) |

---

## Environment Variables (.env)

```
# Actual Budget Server (for actual-http-api container)
ACTUAL_PASSWORD=your_actual_server_password

# Actual Budget Sync ID (Settings → Show advanced settings → Sync ID)
BUDGET_SYNC_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# Middleware API Key (generate with: openssl rand -hex 32)
MIDDLEWARE_API_KEY=openssl_rand_hex_32

# Middleware URL (override for local dev outside Docker)
MIDDLEWARE_URL=http://actual-http-api:5007

# Telegram Bot (get from @BotFather)
TELEGRAM_TOKEN=your_bot_token_from_botfather

# Google Gemini (get from https://aistudio.google.com)
GEMINI_API_KEY=your_gemini_api_key_from_aistudio
```

---

## docker-compose.yml Services

```yaml
services:
  actual-server:      # Financial engine (port 5006)
    image: actualbudget/actual-server:latest

  actual-http-api:    # REST wrapper (port 5007)
    image: jhonderson/actual-http-api:latest
    environment:
      ACTUAL_SERVER_URL: http://actual-server:5006/
      ACTUAL_SERVER_PASSWORD: ${ACTUAL_PASSWORD}
      API_KEY: ${MIDDLEWARE_API_KEY}

  app:                # Bot + Agent
    build: .
    environment:
      TELEGRAM_TOKEN: ${TELEGRAM_TOKEN}
      GEMINI_API_KEY: ${GEMINI_API_KEY}
      MIDDLEWARE_URL: http://actual-http-api:5007
      MIDDLEWARE_API_KEY: ${MIDDLEWARE_API_KEY}
      BUDGET_SYNC_ID: ${BUDGET_SYNC_ID}
```

---

## Testing

Tests are written with **pytest** + **pytest-asyncio** and run inside a dedicated Docker container to avoid local dependency conflicts.

```bash
# Build and run all tests
docker build -f Dockerfile.test -t app-test . && docker run --rm app-test
```

### Test structure

```
tests/
├── conftest.py          # Mocks ActualClient, sets env vars, resets singleton
├── test_tools.py        # 11 tests covering all 8 tools
└── __init__.py
```

### Mocking strategy

- `ActualClient` is mocked via `unittest.mock.MagicMock(spec=ActualClient)`.
- Every async method (`get_accounts`, `add_transaction`, etc.) is replaced with `AsyncMock`.
- The module-level `_client` singleton in `tools.py` is replaced with the mock via `@patch`.
- `conftest.py` provides an `autouse` fixture that resets the singleton before each test.

---

## Extending the Architecture

### Adding a new tool

1. Define a new function in `tools.py` decorated with `@tool`
2. The function signature (name + parameter types) is automatically converted to Gemini's `FunctionDeclaration` schema
3. The agent will discover and use it automatically

### Adding a new media type

1. Add a new strategy method in `MediaProcessor` (`src/multimodal.py`)
2. Define the structured output schema in `src/schemas/` (e.g. `schemas/multimodal.py`)
3. Write the Gemini prompt in the corresponding `src/prompts/` file
4. Register the handler in `src/bot.py`

### Adding a new prompt type

1. Add the prompt constant to the appropriate file under `src/prompts/`
2. Import it from the logic file that needs it — no changes to the prompt file are required later

### Adding a new structured output schema

1. Define the Pydantic model in `src/schemas/` (create a new file or add to an existing one)
2. Import and use it wherever the structured output is needed (e.g. `multimodal.py` with `with_structured_output(Schema)`)

### Adding persistence

- Replace the in-memory state with a LangGraph `Checkpointer` (SQLite, PostgreSQL)
- This enables conversation history across restarts
