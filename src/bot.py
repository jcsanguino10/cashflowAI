from langchain_core.messages import HumanMessage
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from src.agent import agent
from src.config import config
from src.prompts.bot import HELP_MESSAGE, WELCOME_MESSAGE


def _extract_text(content: str | list) -> str:
    """Extrae texto plano del content de Gemini (string en 2.x, lista en 3.x)."""
    if isinstance(content, list):
        parts = [
            p["text"] for p in content
            if isinstance(p, dict) and p.get("type") == "text"
        ]
        return " ".join(parts)
    return content


async def start(update: Update, _context):
    await update.message.reply_text(WELCOME_MESSAGE)


async def help_command(update: Update, _context):
    await update.message.reply_text(HELP_MESSAGE)


async def text_message(update: Update, _context):
    state = {
        "messages": [HumanMessage(content=update.message.text)],
        "media": None,
    }
    try:
        result = await agent.ainvoke(state)
        response = _extract_text(result["messages"][-1].content)
        await update.message.reply_text(response)
    except Exception as e:
        await update.message.reply_text(f"Lo siento, ocurrió un error: {e!s}")


async def voice_message(update: Update, _context):
    try:
        file = await update.message.voice.get_file()
        audio_bytes = await file.download_as_bytearray()
    except Exception as e:
        await update.message.reply_text(f"No pude descargar el audio: {e!s}")
        return

    state = {
        "messages": [HumanMessage(content="[Mensaje de voz recibido]")],
        "media": {"type": "voice", "data": audio_bytes, "file_type": "ogg"},
    }
    try:
        result = await agent.ainvoke(state)
        response = _extract_text(result["messages"][-1].content)
        await update.message.reply_text(response)
    except Exception as e:
        await update.message.reply_text(
            f"Lo siento, ocurrió un error al procesar el audio: {e!s}"
        )


async def photo_message(update: Update, _context):
    try:
        file = await update.message.photo[-1].get_file()
        image_bytes = await file.download_as_bytearray()
    except Exception as e:
        await update.message.reply_text(f"No pude descargar la imagen: {e!s}")
        return

    state = {
        "messages": [HumanMessage(content="[Foto de recibo recibida]")],
        "media": {"type": "photo", "data": image_bytes, "file_type": "jpg"},
    }
    try:
        result = await agent.ainvoke(state)
        response = _extract_text(result["messages"][-1].content)
        await update.message.reply_text(response)
    except Exception as e:
        await update.message.reply_text(
            f"Lo siento, ocurrió un error al procesar la foto: {e!s}"
        )


async def document_message(update: Update, _context):
    document = update.message.document
    file_name = document.file_name or ""
    mime_type = document.mime_type or ""

    print(f"[TRACE bot] document_message recibido: name={file_name}, mime={mime_type}")

    if "pdf" in mime_type or file_name.lower().endswith(".pdf"):
        file_type = "pdf"
    elif "jpeg" in mime_type or file_name.lower().endswith((".jpg", ".jpeg")):
        file_type = "jpg"
    elif "png" in mime_type or file_name.lower().endswith(".png"):
        file_type = "png"
    else:
        print(f"[TRACE bot] formato no soportado: mime={mime_type}, name={file_name}")
        await update.message.reply_text(
            "Formato de documento no soportado. Envíame PDF, JPG o PNG."
        )
        return

    print(f"[TRACE bot] tipo detectado: {file_type}")

    try:
        file = await document.get_file()
        file_bytes = await file.download_as_bytearray()
        print(f"[TRACE bot] descargado: {len(file_bytes)} bytes")
    except Exception as e:
        print(f"[TRACE bot] error descarga: {e!s}")
        await update.message.reply_text(f"No pude descargar el documento: {e!s}")
        return

    state = {
        "messages": [HumanMessage(content="[Documento recibido]")],
        "media": {"type": "document", "data": file_bytes, "file_type": file_type},
    }
    print(f"[TRACE bot] enviando state al agent con media.type={state['media']['type']}, file_type={file_type}")
    try:
        result = await agent.ainvoke(state)
        response = _extract_text(result["messages"][-1].content)
        print(f"[TRACE bot] respuesta del agent: {response[:200]}")
        await update.message.reply_text(response)
    except Exception as e:
        print(f"[TRACE bot] error agent: {e!s}")
        await update.message.reply_text(
            f"Lo siento, ocurrió un error al procesar el documento: {e!s}"
        )


def build_application(post_shutdown=None) -> Application:
    builder = Application.builder().token(config.telegram_token)
    if post_shutdown:
        builder.post_shutdown(post_shutdown)
    app = builder.build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))
    app.add_handler(MessageHandler(filters.VOICE, voice_message))
    app.add_handler(MessageHandler(filters.PHOTO, photo_message))
    app.add_handler(MessageHandler(filters.Document.ALL, document_message))
    return app
