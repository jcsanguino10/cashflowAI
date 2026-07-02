# AI Personal Finance — Agent Guide

## Project state

Proyecto en **v2**. El estado actual se mantiene en [`TASKS.md`](TASKS.md).

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

### Ramas por grupo de tareas

- Cada grupo v2 (V2-1, V2-2, V2-3) tiene su propia rama con formato:
  `task/<grupo>-<descripción-corta>` (ej: `task/v2-1-crud`)
- Antes de empezar a trabajar:
  1. Verificar si la rama del grupo ya existe (`git branch -a | grep <rama>`)
  2. Si existe → `git checkout <rama>`
  3. Si no existe → `git checkout -b <rama> master`
- Todas las tareas del grupo se implementan y commitean en esa rama.

### Commits

1. Marcar la tarea completada en `TASKS.md`.
2. El agente **no debe commitear** hasta que el usuario haya probado y dé aprobación explícita.
3. Una vez aprobado:
   ```
   git add -A && git commit -m "feat: <descripción corta>" -m "<descripción detallada>"
   git push origin <rama-actual>
   ```
4. Siempre que se haga un commit, se debe hacer `push` a la rama.

Convención de commits:
```
feat: <resumen conciso (máx 72 caracteres)>

<descripción detallada del cambio, en español o inglés>
```

### Pull Request al completar un grupo

- Al completar la **última tarea de un grupo**, crear un PR a `master`:
  ```
  gh pr create --base master --head <rama> --title "feat(v2): <descripción del grupo>" --body "<lista de tareas incluidas>"
  ```
- No hacer merge del PR hasta que el usuario lo autorice.

## Docker

```bash
docker compose up --build
```

Requires `.env` file with all vars from `.env.example`.

