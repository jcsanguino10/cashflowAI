"""Entry point for the AI Personal Finance bot.

Initializes config, builds the LangGraph agent, creates the Telegram bot
application, and starts polling with graceful shutdown.
"""

import logging
import sys

from telegram import Update
from telegram.ext import Application

from src.bot import build_application
from src.tools import shutdown_client

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
_log = logging.getLogger(__name__)


async def _post_shutdown(app: Application) -> None:
    await shutdown_client()
    _log.info("HTTP client closed.")


def main() -> None:
    _log.info("Starting AI Personal Finance bot...")

    app = build_application(post_shutdown=_post_shutdown)

    _log.info("Bot is polling. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
