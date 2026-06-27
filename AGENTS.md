# AI Personal Finance — Agent Guide

## Project state

Phases 0–2 complete: `src/config.py`, `src/middleware_client.py`, and `src/tools.py` exist. The following files are **not yet implemented**:
- `src/multimodal.py`, `src/agent.py`, `src/bot.py`, `src/main.py`

Run: `python -m src.main` (module, not script — all intra-package imports use `from src.xxx`).

## Critical conventions

- **All amounts are integers in cents** (€12.99 = 1299). Use `euros_to_cents` / `cents_to_euros` from `middleware_client.py` at boundaries.
- **Config** (`src/config.py`): pydantic-settings with `SettingsConfigDict(extra="ignore", case_sensitive=False)`. Env file `.env`. Singleton `config = Config()` at module level — import via `from src.config import config`.
- **`BUDGET_SYNC_ID`** is required (Actual Budget Sync ID, not server password).
- **All middleware client methods are async** (`httpx.AsyncClient`). The agent runs in an async event loop.
- **`_transaction_to_dict`** omits `None` fields — never pass dataclass defaults as explicit `None` (they are intentionally absent).

## Architecture

Single Python process: Telegram bot + LangGraph agent in one container. Three Docker services:
`actual-server` (port 5006), `actual-http-api` (port 5007), `app` (builds from repo).

See `ARCHITECTURE.md` for the full design. `TASKS.md` tracks pending implementation items.

## Tests / lint / format / typecheck

Tests are run inside a Docker container:

```bash
docker build -f Dockerfile.test -t app-test . && docker run --rm app-test
```

No lint / format / typecheck configured yet.

## Git workflow

### Branches

- Al iniciar una tarea, crear una rama con el formato: `task/<NÚMERO>-<descripción-corta>` (ej: `task/1-telegram-bot`).
- La rama se crea a partir de `master`.
- Todas las implementaciones y commits de la tarea se hacen en esa rama.

### Commits

Después de implementar una tarea:
1. Actualizar `TASKS.md` (marcar checkboxes y actualizar conteos).
2. Hacer commit en la rama de la tarea. El agente **no debe commitear** hasta que el usuario haya probado y dado su aprobación explícita.
3. Una vez que el usuario confirma que las pruebas pasan y dice **"haz commit"** o **"commit"**, el agente ejecuta:
   ```
   git add -A && git commit -m "..."
   ```

Convención de commits:
```
git add -A && git commit -m "feat: <descripción corta>

<descripción detallada de qué se hizo y por qué>"
```

- Primera línea: prefijo `feat:` + resumen conciso (máx 72 caracteres).
- Línea en blanco, luego una descripción más larga explicando el cambio.
- La descripción debe estar en español o inglés, según el resto del proyecto.
- Ejemplo:
  ```
  feat: implement Telegram bot connection

  Se agregó la conexión inicial con el bot de Telegram usando python-telegram-bot.
  Incluye manejo de comandos /start y /help.
  ```

### Merge a master

Una vez que el usuario dice que la tarea está completa:
- El agente hace merge de la rama de la tarea a `master`.
- Luego elimina la rama de la tarea (local y remota si existe).

## Docker

```bash
docker compose up --build
```

Requires `.env` file with all vars from `.env.example`.

