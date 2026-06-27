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
│   ├── bot.py                 # Telegram bot handlers
│   │                          #   - text: direct message
│   │                          #   - voice: audio transcription via Gemini
│   │                          #   - photo: receipt OCR via Gemini Vision
│   │                          #   - document: PDF/bank statement parsing
│   ├── agent.py               # LangGraph StateGraph definition
│   │                          #   Node 1: multimodal_preprocessor
│   │                          #   Node 2: financial_agent
│   │                          #   Conditional edge: tool call or respond
│   ├── tools.py               # Agent tools (decorated with @tool)
│   │                          #   - add_transaction, add_split_transaction
│   │                          #   - get_accounts, get_balances, get_budget
│   │                          #   - get_transactions, analyze_spending
│   │                          #   - get_recommendations
│   ├── multimodal.py          # Gemini multimodal preprocessing
│   │                          #   - transcribe_audio()
│   │                          #   - extract_receipt_items()
│   │                          #   - parse_bank_statement()
│   └── middleware_client.py   # HTTP client for actual-http-api
│                              #   - Typed wrappers for each endpoint
│                              #   - API Key authentication
│                              #   - Amount conversion (euros ↔ cents)
├── docker-compose.yml         # 3 services: actual-server, actual-http-api, app
├── Dockerfile                 # Python application image
├── requirements.txt           # Python dependencies
├── .env.example               # Environment variable template
└── ARCHITECTURE.md            # This file
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

### 5. Singleton Configuration

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
# Actual Budget
ACTUAL_PASSWORD=your_actual_server_password

# Middleware
MIDDLEWARE_API_KEY=openssl_rand_hex_32

# Telegram
TELEGRAM_TOKEN=your_bot_token_from_botfather

# Gemini
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
```

---

## Extending the Architecture

### Adding a new tool

1. Define a new function in `tools.py` decorated with `@tool`
2. The function signature (name + parameter types) is automatically converted to Gemini's `FunctionDeclaration` schema
3. The agent will discover and use it automatically

### Adding a new media type

1. Add a new strategy method in `MediaProcessor`
2. Register the handler in `bot.py`
3. Add a new prompt to `multimodal.py`

### Adding persistence

- Replace the in-memory state with a LangGraph `Checkpointer` (SQLite, PostgreSQL)
- This enables conversation history across restarts
