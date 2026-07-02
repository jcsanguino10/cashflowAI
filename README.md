# cashflowIA

> Asistente de finanzas personales vía Telegram impulsado por inteligencia artificial.

cashflowIA te permite gestionar tu presupuesto en [Actual Budget](https://actualbudget.org/) directamente desde Telegram. Enviá mensajes de texto, notas de voz, fotos de tickets o estados de cuenta en PDF, y el agente con Gemini + LangGraph se encarga del resto.

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Mensajería | [python-telegram-bot](https://python-telegram-bot.org/) |
| Agente conversacional | [LangGraph](https://langchain-ai.github.io/langgraph/) (ReAct) |
| Modelo de lenguaje | [Gemini](https://ai.google.dev/) via `langchain-google-genai` |
| Middleware REST | [actual-http-api](https://hub.docker.com/r/jhonderson/actual-http-api) |
| Motor financiero | [Actual Budget](https://actualbudget.org/) |
| Contenedores | Docker + Docker Compose |

## Arquitectura

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

El bot de Telegram y el agente LangGraph se ejecutan en un mismo proceso Python. Tres servicios Docker orquestados con Docker Compose.

## Requisitos previos

- Docker y Docker Compose instalados
- Token de bot de Telegram (crealo con [@BotFather](https://t.me/BotFather))
- API Key de Google Gemini (obtenela en [AI Studio](https://aistudio.google.com))
- Sync ID de Actual Budget (Ajustes → Mostrar ajustes avanzados → Sync ID)
- Contraseña del servidor Actual Budget

## Configuración rápida

```bash
cp .env.example .env
# Completar las variables con tus credenciales
docker compose up --build
```

### Variables de entorno

| Variable | Descripción |
|---|---|
| `ACTUAL_PASSWORD` | Contraseña del servidor Actual Budget |
| `BUDGET_SYNC_ID` | Identificador de sincronización del presupuesto |
| `MIDDLEWARE_API_KEY` | Clave API para el middleware actual-http-api |
| `TELEGRAM_TOKEN` | Token del bot de Telegram |
| `GEMINI_API_KEY` | Clave API de Google Gemini |

### Servicios Docker

El archivo `docker-compose.yml` define tres servicios:

| Servicio | Imagen | Puerto | Rol |
|---|---|---|---|
| `actual-server` | `actualbudget/actual-server` | 5006 | Motor financiero (SQLite) |
| `actual-http-api` | `jhonderson/actual-http-api` | 5007 | REST wrapper sobre el SDK de Actual Budget |
| `app` | build desde `Dockerfile` | — | Bot de Telegram + Agente LangGraph |

Las variables de entorno se inyectan desde el archivo `.env` en cada servicio según corresponda.

## Cómo usarlo

Una vez que el bot está corriendo, enviale mensajes desde Telegram:

| Tipo de entrada | Ejemplo | Procesamiento |
|---|---|---|
| Texto | "Gasté €50 en Netflix ayer" | Análisis directo por Gemini |
| Voz | Graba un mensaje de voz | Transcripción con Gemini, luego análisis |
| Foto | Foto de un ticket | OCR con Gemini Vision, detección de items |
| Documento | Estado de cuenta en PDF | Parseo de transacciones con Gemini |

También podés hacer consultas como:

- "¿Cuánto gasté este mes?"
- "¿Cómo voy con el presupuesto de supermercado?"
- "Mostrame el saldo de todas mis cuentas"

## Estructura del proyecto

```
cashflowIA/
├── src/
│   ├── main.py                # Punto de entrada
│   ├── config.py              # Configuración desde variables de entorno
│   ├── bot.py                 # Handlers del bot de Telegram
│   ├── agent.py               # Grafo de estado con LangGraph
│   ├── tools.py               # Herramientas del agente financiero
│   ├── multimodal.py          # Procesamiento de audio, imágenes y PDFs
│   ├── middleware_client.py   # Cliente HTTP para actual-http-api
│   ├── prompts/               # Prompts del LLM separados por módulo
│   │   ├── agent.py
│   │   ├── bot.py
│   │   └── multimodal.py
│   └── schemas/               # Modelos Pydantic para salidas estructuradas
│       ├── agent.py
│       └── multimodal.py
├── tests/
│   ├── conftest.py            # Fixtures compartidos (mocks, env vars)
│   └── test_tools.py          # Tests para herramientas del agente
├── docker-compose.yml         # Orquestación de servicios
├── Dockerfile                 # Imagen de la aplicación
├── Dockerfile.test            # Imagen para ejecutar tests
├── .env.example               # Plantilla de configuración
├── .gitignore
├── AGENTS.md                  # Guía para el agente que programa
├── ARCHITECTURE.md            # Documentación técnica detallada
├── TASKS.md                   # Seguimiento de tareas del proyecto
└── LICENSE                    # Términos de uso
```

## Estado del proyecto

Actualmente en desarrollo activo. Consultá [`TASKS.md`](TASKS.md) para conocer el detalle de tareas pendientes y completadas.

## Tests

Los tests se ejecutan dentro de un contenedor Docker para evitar conflictos de dependencias locales:

```bash
docker build -f Dockerfile.test -t app-test . && docker run --rm app-test
```

Estructura:
- `tests/conftest.py` — fixtures compartidos (mock de `ActualClient`, variables de entorno)
- `tests/test_tools.py` — tests para las herramientas del agente

El cliente HTTP (`ActualClient`) se mockea con `unittest.mock.MagicMock` y sus métodos async con `AsyncMock`. El singleton `_client` en `tools.py` se reemplaza via `@patch`.

## Licencia

Este proyecto se distribuye bajo **Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)**.

Podés usar, compartir y modificar el código libremente siempre que sea para fines no comerciales y otorgues la atribución correspondiente. No está permitido su uso con fines comerciales.

Ver el archivo [`LICENSE`](LICENSE) para más detalles.
