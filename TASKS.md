# Tasks — AI Personal Finance

> Priority: 🔴 High / 🟡 Medium / 🟢 Low
> Status: ⬜ Pending / 🔄 In Progress / ✅ Done / ❌ Blocked

---

## Phase 0: Project Setup

- [x] **T-000** 🔴 Create `requirements.txt` with all Python dependencies
      Dependencies: _none_

- [x] **T-001** 🔴 Create `Dockerfile` for the Python application
      Dependencies: T-000

- [x] **T-002** 🔴 Create `.env.example` with all required environment variables
      Dependencies: _none_

- [x] **T-003** 🔴 Create `docker-compose.yml` with 3 services:
      actual-server, actual-http-api, app
      Dependencies: T-001

- [x] **T-004** 🟢 Create `.gitignore` (Python + Docker + .env patterns)
      Dependencies: _none_

---

## Phase 1: Configuration & HTTP Client

- [x] **T-100** 🔴 Implement `src/config.py`
      - Load and validate all environment variables at startup
      - Typed dataclass with `EnvConfig`
      - Fail fast on missing variables
      Dependencies: _none_

- [x] **T-101** 🔴 Implement `src/middleware_client.py`
      - Async HTTP client wrapping `jhonderson/actual-http-api`
      - Typed methods: get_accounts, get_balances, get_budget,
        get_transactions, add_transaction, get_categories, get_payees
      - Amount conversion (EUR ↔ cents)
      - API Key authentication via `x-api-key` header
      - Error handling and response parsing
      Dependencies: T-100

---

## Phase 2: Agent Tools

- [x] **T-200** 🔴 Implement `src/tools.py`
      - `get_accounts()` → list all accounts
      - `get_balances()` → current balances per account
      - `get_budget(year, month)` → budget status for a month
      - `get_transactions(account, start_date, end_date, category)`
      - `add_transaction(account, payee_name, amount, date, category, notes)`
      - `add_split_transaction(account, payee_name, amount, date,
         subtransactions, notes)` → creates parent + child transactions
      - `analyze_spending(period)` → fetches data, returns raw for LLM
      - `get_recommendations()` → fetches financial summary for LLM
      Dependencies: T-101

---

## Phase 3: Multimodal Processing

- [x] **T-300** 🔴 Implement `src/multimodal.py`
      - `transcribe_audio(audio_bytes)` → text via Gemini
      - `extract_receipt_items(image_bytes)` → structured JSON via Gemini Vision
      - `parse_bank_statement(file_bytes, file_type)` → transaction list via Gemini
      - Prompt templates for each media type
      Dependencies: T-100

---

## Phase 4: LangGraph Agent

- [ ] **T-400** 🔴 Implement `src/agent.py`
      - Define `AgentState` TypedDict with messages, media, tool_results
      - `multimodal_preprocessor` node (calls T-300 if media present)
      - `financial_agent` node (Gemini LLM + bound tools from T-200)
      - Conditional edge: tool call loop or respond
      - Compile and export the graph
      Dependencies: T-200, T-300

---

## Phase 5: Telegram Bot

- [ ] **T-500** 🔴 Implement `src/bot.py`
      - `start` handler — welcome message
      - `text_message` handler → invokes agent (T-400)
      - `voice_message` handler → download audio → T-300 → T-400
      - `photo_message` handler → download image → T-300 → T-400
      - `document_message` handler → download file → T-300 → T-400
      - `help` handler — available commands
      Dependencies: T-400

- [ ] **T-501** 🟡 Rate limiting and user validation
      - Single-user guard (reject messages from unknown chat IDs)
      - Basic rate limiting per minute
      Dependencies: T-500

---

## Phase 6: Entry Point

- [ ] **T-600** 🔴 Implement `src/main.py`
      - Initialize config
      - Build and compile the LangGraph agent
      - Create bot application with all handlers
      - Start polling (or webhook)
      - Graceful shutdown handler
      Dependencies: T-100, T-400, T-500

---

## Phase 7: Testing & Validation

- [ ] **T-700** 🟡 Test basic text transactions
      - "Gasté €50 en Netflix"
      - Verify transaction appears in Actual Budget
      Dependencies: T-600

- [ ] **T-701** 🟡 Test split transaction from receipt photo
      - Upload a receipt image
      - Verify parent + children in Actual Budget
      Dependencies: T-600, T-300

- [ ] **T-702** 🟡 Test voice command
      - Send voice message with expense
      - Verify correct transcription and transaction
      Dependencies: T-600, T-300

- [ ] **T-703** 🟡 Test bank statement PDF
      - Upload a PDF with multiple transactions
      - Verify all transactions created
      Dependencies: T-600, T-300

- [ ] **T-704** 🟡 Test financial queries
      - "¿Cuánto gasté este mes?"
      - "¿Cómo voy con el presupuesto?"
      - Verify responses are coherent and accurate
      Dependencies: T-600

- [ ] **T-705** 🟢 Test error handling
      - Invalid amounts, missing fields, network errors
      - Verify user receives helpful error messages
      Dependencies: T-600

---

## Phase 8: Polish & Documentation

- [ ] **T-800** 🟡 Add proper logging throughout
      - Structured logging with context (request ID, user, action)
      - Log level configuration via env var
      Dependencies: T-600

- [ ] **T-801** 🟢 Add health check endpoint (FastAPI lite or simple HTTP)
      - Verify connectivity to middleware and Actual Budget
      Dependencies: T-600

- [ ] **T-802** 🟢 Add receipts image storage (optional)
      - Mount volume for receipt images referenced in notes
      Dependencies: T-600

---

## Dependency Graph (simplified)

```
T-000 ──▶ T-001 ──▶ T-003
                        │
T-004 ──────────────────┤
                        │
T-100 ──▶ T-101 ──▶ T-200 ──┐
                        │     │
T-300 ──────────────────┼────┤
                        │     │
                 T-400 ◀┘     │
                        │     │
                 T-500 ──▶ T-600 ──▶ T-700──T-704
                                    │
                                    └──▶ T-800
                                         │
                                         └──▶ T-801
                                              │
                                              └──▶ T-802
```

---

## Task Status Summary

| Phase | Count | Status |
|---|---|---|
| 0 — Project Setup | 5 | ✅ 5/5 Done |
| 1 — Config & HTTP | 2 | ✅ 2/2 Done |
| 2 — Agent Tools | 1 | ✅ 1/1 Done |
| 3 — Multimodal | 1 | ✅ 1/1 Done |
| 4 — LangGraph Agent | 1 | ⬜ Pending |
| 5 — Telegram Bot | 2 | ⬜ Pending |
| 6 — Entry Point | 1 | ⬜ Pending |
| 7 — Testing | 6 | ⬜ Pending |
| 8 — Polish | 3 | ⬜ Pending |
| **Total** | **22** | **✅ 9/22 · ⬜ 13 Pending** |
