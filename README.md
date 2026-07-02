# cashflowIA

> AI-powered personal finance assistant via Telegram.

cashflowIA lets you manage your [Actual Budget](https://actualbudget.org/) directly from Telegram. Send text messages, voice notes, receipt photos, or PDF bank statements, and the Gemini + LangGraph agent handles the rest.

## Tech Stack

| Layer | Technology |
|---|---|
| Messaging | [python-telegram-bot](https://python-telegram-bot.org/) |
| Agent Framework | [LangGraph](https://langchain-ai.github.io/langgraph/) (ReAct) |
| Language Model | [Gemini](https://ai.google.dev/) via `langchain-google-genai` |
| REST Middleware | [actual-http-api](https://hub.docker.com/r/jhonderson/actual-http-api) |
| Financial Engine | [Actual Budget](https://actualbudget.org/) |
| Containerization | Docker + Docker Compose |

## Architecture

```
 ┌──────────┐    ┌──────────────────┐    ┌────────────────┐    ┌───────────────┐
 │ Telegram │──▶ │  LangGraph Agent │──▶ │ actual-http-   │──▶ │ Actual Budget │
 │   Bot    │◀── │  (Gemini + Tools) │◀── │  api           │◀── │    Server     │
 └──────────┘    └────────┬─────────┘    └────────────────┘    └───────────────┘
                          │
                          ▼
                   ┌──────────────┐
                   │  Gemini API  │
                   │ (text/audio/ │
                   │  vision)     │
                   └──────────────┘
```

The Telegram bot and LangGraph agent run in the same Python process. Three Docker services orchestrated with Docker Compose.

## Prerequisites

- Docker and Docker Compose installed
- Telegram bot token (create one with [@BotFather](https://t.me/BotFather))
- Google Gemini API key (get one at [AI Studio](https://aistudio.google.com))
- Actual Budget Sync ID (Settings → Show advanced settings → Sync ID)
- Actual Budget server password

## Quick Start

```bash
cp .env.example .env
# Fill in your credentials
docker compose up --build
```

### Environment Variables

| Variable | Description |
|---|---|
| `ACTUAL_PASSWORD` | Actual Budget server password |
| `BUDGET_SYNC_ID` | Budget synchronization identifier |
| `MIDDLEWARE_API_KEY` | API key for the actual-http-api middleware |
| `TELEGRAM_TOKEN` | Telegram bot token |
| `GEMINI_API_KEY` | Google Gemini API key |

### Docker Services

The `docker-compose.yml` file defines three services:

| Service | Image | Port | Role |
|---|---|---|---|
| `actual-server` | `actualbudget/actual-server` | 5006 | Financial engine (SQLite) |
| `actual-http-api` | `jhonderson/actual-http-api` | 5007 | REST wrapper over Actual Budget SDK |
| `app` | build from `Dockerfile` | — | Telegram bot + LangGraph agent |

Environment variables are injected from the `.env` file into each service as needed.

## Usage

Once the bot is running, send messages from Telegram:

| Input Type | Example | Processing |
|---|---|---|
| Text | "I spent €50 on Netflix yesterday" | Direct Gemini analysis |
| Voice | Record a voice message | Transcription via Gemini, then analysis |
| Photo | Receipt photo | OCR via Gemini Vision, item detection |
| Document | Bank statement PDF | Transaction parsing via Gemini |

You can also ask questions like:

- "How much did I spend this month?"
- "How's my grocery budget looking?"
- "Show me the balance of all my accounts"

## Project Structure

```
cashflowIA/
├── src/
│   ├── main.py                # Entry point
│   ├── config.py              # Environment variable loading
│   ├── bot.py                 # Telegram bot handlers
│   ├── agent.py               # LangGraph state graph
│   ├── tools.py               # Agent financial tools
│   ├── multimodal.py          # Audio, image and PDF processing
│   ├── middleware_client.py   # HTTP client for actual-http-api
│   ├── prompts/               # LLM prompts separated by module
│   │   ├── agent.py
│   │   ├── bot.py
│   │   └── multimodal.py
│   └── schemas/               # Pydantic models for structured output
│       ├── agent.py
│       └── multimodal.py
├── tests/
│   ├── conftest.py            # Shared fixtures (mocks, env vars)
│   └── test_tools.py          # Tests for agent tools
├── docker-compose.yml         # Service orchestration
├── Dockerfile                 # Application image
├── Dockerfile.test            # Test image
├── .env.example               # Configuration template
├── .gitignore
├── AGENTS.md                  # Guide for the AI coding agent
├── ARCHITECTURE.md            # Detailed technical documentation
├── TASKS.md                   # Task tracking
└── LICENSE                    # Terms of use
```

## Project Status

Currently under active development. See [`TASKS.md`](TASKS.md) for details on pending and completed tasks.

## Tests

Tests run inside a Docker container to avoid local dependency conflicts:

```bash
docker build -f Dockerfile.test -t app-test . && docker run --rm app-test
```

Structure:
- `tests/conftest.py` — shared fixtures (mocked `ActualClient`, env vars)
- `tests/test_tools.py` — tests for agent tools

The HTTP client (`ActualClient`) is mocked with `unittest.mock.MagicMock` and its async methods with `AsyncMock`. The `_client` singleton in `tools.py` is replaced via `@patch`.

## License

This project is distributed under **Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)**.

You are free to use, share, and modify the code for non-commercial purposes, provided you give appropriate attribution. Commercial use is not permitted.

See the [`LICENSE`](LICENSE) file for details.
