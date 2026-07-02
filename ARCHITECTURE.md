# AI Personal Finance — Architecture

---

## Project Structure

```
src/
├── __init__.py
├── main.py                # Entry point — starts bot polling + agent
├── config.py              # Environment variable loading & validation
├── bot.py                 # Telegram bot handlers (logic only)
├── agent.py               # LangGraph StateGraph definition (logic only)
│                          #   Node 1: multimodal_preprocessor
│                          #   Node 2: financial_agent
│                          #   Conditional edge: tool call or respond
├── tools.py               # Agent tools (decorated with @tool)
├── multimodal.py          # MediaProcessor class (Gemini calls)
├── middleware_client.py   # HTTP client for actual-http-api
├── prompts/               # All prompt strings, separated from logic
│   ├── __init__.py
│   ├── multimodal.py      #   _TRANSCRIBE, _RECEIPT, _STATEMENT prompts
│   ├── agent.py           #   _SYSTEM_PROMPT for the LLM agent
│   └── bot.py             #   WELCOME_MESSAGE, HELP_MESSAGE
└── schemas/               # Pydantic response schemas
    ├── __init__.py
    └── multimodal.py      #   ReceiptItem, Receipt, BankTx, BankStatement
tests/
├── conftest.py            # Shared fixtures (mock client, env vars)
├── test_tools.py          # Tests for agent tools
└── __init__.py
```

---

## Design Patterns

### 1. Agentic Loop (LangGraph ReAct)

Core pattern: a **ReAct (Reasoning + Acting)** loop with `StateGraph`:

```
User Input → Preprocessor (if media) → Financial Agent (LLM + Tools)
                                             ↓
                                      ┌──────┴──────┐
                                      ↓              ↓
                                   Respond       Call Tool
                                                     ↓
                                                Middleware HTTP
                                                     ↓
                                               Actual Budget
```

**State**: `TypedDict` with `messages` (history), `media` (optional processed media), `tool_results`.

### 2. Tool-as-a-Function

Each capability is a typed Python function decorated with `@tool` from LangChain. Tools receive structured arguments from Gemini's function calling and return structured results.

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

`actual-http-api` sits between the agent and Actual Budget's Node.js SDK, translating REST/JSON ↔ sync protocol, managing sessions, and handling auth/retries/errors.

### 4. Strategy Pattern for Media Processing

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

Prompts and schemas live in `src/prompts/` and `src/schemas/`, decoupled from logic:

```
src/
├── prompts/           # Pure prompt strings
│   ├── agent.py       #   _SYSTEM_PROMPT
│   ├── bot.py         #   WELCOME_MESSAGE, HELP_MESSAGE
│   └── multimodal.py  #   _TRANSCRIBE/RECEIPT/STATEMENT_PROMPT
├── schemas/           # Pydantic models
│   └── multimodal.py  #   ReceiptItem, Receipt, BankTx, BankStatement
├── agent.py           # Imports _SYSTEM_PROMPT from prompts/agent.py
├── bot.py             # Imports WELCOME/HELP from prompts/bot.py
└── multimodal.py      # Imports prompts and schemas from their packages
```

**Rationale**: iteration speed (edit prompt ≠ touch logic), testability, single responsibility.

### 6. Singleton Configuration

`config.py` loads env vars once at startup and validates eagerly — fail fast.

---

## Key Technical Decisions

### 1. Same Process for Bot and Agent

Telegram bot + LangGraph agent run in the **same Python process**. Low latency, single container deployment. Agent instantiated once, reused across messages.

### 2. Split Transactions for Receipt Line Items

Actual Budget supports split transactions via `subtransactions`. When a user uploads a receipt:
- **Parent**: total amount (matches bank statement)
- **Children**: individual items with own `amount`, `category`, `notes`

### 3. actual-http-api Over actualpy

Uses the **official `@actual-app/api` Node.js SDK** via REST wrapper — guaranteed compatibility, handles session management and sync automatically.

### 4. Gemini as Single LLM Provider

- Multimodal natively (text, audio, images, PDFs)
- Generous free tier
- First-class function calling for ReAct loop
- Well-integrated with LangGraph via `langchain-google-genai`

### 5. No Conversational Memory Persistence

Session-only memory — no persistence between restarts. Keeps implementation simple. LangGraph supports checkpointers (SQLite, PostgreSQL) if needed later.

### 6. Amounts in Cents (Integers)

All monetary amounts are **integers in cents** (€12.99 = 1299). Use `euros_to_cents` / `cents_to_euros` from `middleware_client.py` at boundaries.

---

## Data Flow: Receipt Upload (Most Complex Path)

```
1. User sends photo of receipt
       ↓
2. Bot handler: download file → classify media
       ↓
3. Multimodal preprocessor (Gemini Vision)
   → prompt: extract receipt items as JSON
   → response: {store, date, total, items[], tax, payment_method}
   → validate & clean
       ↓
4. LangGraph Agent (financial_agent node)
   → Gemini decides: add_split_transaction
   → builds tool arguments
       ↓
5. Tool: add_split_transaction
   → POST to actual-http-api /v1/transactions
   → body: {amount, payee_name, is_parent, subtransactions}
       ↓
6. actual-http-api → @actual-app/api → Actual Budget SQLite
       ↓
7. Bot response: "✅ Mercadona €82.50 - 15 items registrados"
```

---

## Communication Protocols

| Between | Protocol | Auth | Port |
|---|---|---|---|
| Telegram Bot ↔ Telegram API | HTTPS | Bot Token | 443 (outbound) |
| LangGraph Agent ↔ Gemini API | gRPC/HTTPS | API Key | 443 (outbound) |
| LangGraph Agent ↔ actual-http-api | HTTP/REST | `x-api-key` header | 5007 (internal) |
| actual-http-api ↔ Actual Server | HTTP (Node.js SDK) | Server Password | 5006 (internal) |

---

## Extending the Architecture

### Adding a new tool

1. Define a function in `tools.py` decorated with `@tool`
2. The signature (name + param types) auto-converts to Gemini's `FunctionDeclaration` schema
3. The agent discovers and uses it automatically

### Adding a new media type

1. Add strategy method in `MediaProcessor` (`src/multimodal.py`)
2. Define output schema in `src/schemas/multimodal.py`
3. Write the Gemini prompt in `src/prompts/multimodal.py`
4. Register the handler in `src/bot.py`

### Adding a new prompt type

1. Add the prompt constant to the appropriate file under `src/prompts/`
2. Import it from the logic file that needs it

### Adding a new structured output schema

1. Define the Pydantic model in `src/schemas/` (new or existing file)
2. Import and use it with `with_structured_output(Schema)`

### Adding persistence

- Replace in-memory state with a LangGraph `Checkpointer` (SQLite, PostgreSQL)
