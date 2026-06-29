import base64
from typing import Optional

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

from src.config import config


# ---------------------------------------------------------------------------
# Structured output schemas
# ---------------------------------------------------------------------------


class ReceiptItem(BaseModel):
    name: str
    amount: float
    category: Optional[str] = None


class Receipt(BaseModel):
    store: str
    date: str
    total: float
    currency: str = "EUR"
    items: list[ReceiptItem]
    payment_method: Optional[str] = None


class BankTx(BaseModel):
    date: str
    description: str
    amount: float
    category: Optional[str] = None


class BankStatement(BaseModel):
    transactions: list[BankTx]


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_TRANSCRIBE_PROMPT = (
    "Transcribe el siguiente mensaje de voz sobre finanzas personales "
    "al español. Devuelve SOLO el texto transcrito, sin explicaciones."
)

_RECEIPT_PROMPT = "Extrae los datos de este recibo de compra."

_STATEMENT_PROMPT = (
    "Extrae todas las transacciones de este extracto bancario. "
    "Los gastos son cantidades negativas, los ingresos son positivas."
)

# ---------------------------------------------------------------------------
# MIME type mapping
# ---------------------------------------------------------------------------

_MIME_MAP = {
    "ogg": "audio/ogg",
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "pdf": "application/pdf",
}


def _mime_type(file_type: str) -> str:
    return _MIME_MAP.get(file_type.lower(), "application/octet-stream")


# ---------------------------------------------------------------------------
# Processor
# ---------------------------------------------------------------------------


class MediaProcessor:
    """Process audio, images and documents using Gemini multimodal."""

    def __init__(self) -> None:
        self._llm = ChatGoogleGenerativeAI(
            model=config.gemini_model,
            google_api_key=config.gemini_api_key,
            temperature=0.1,
        )
        self._receipt_chain = self._llm.with_structured_output(Receipt)
        self._statement_chain = self._llm.with_structured_output(BankStatement)

    def _build_message(
        self, prompt: str, data_bytes: bytes, mime: str
    ) -> HumanMessage:
        if mime.startswith("audio/"):
            b64 = base64.b64encode(data_bytes).decode("utf-8")
            return HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {"type": "audio", "base64": b64, "mime_type": mime},
                ]
            )
        b64 = base64.b64encode(data_bytes).decode("utf-8")
        return HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"},
                },
            ]
        )

    async def transcribe_audio(
        self, audio_bytes: bytes, file_type: str = "ogg"
    ) -> str:
        """Transcribe a voice message to text."""
        mime = _mime_type(file_type)
        msg = self._build_message(_TRANSCRIBE_PROMPT, audio_bytes, mime)
        response = await self._llm.ainvoke([msg])
        content = response.content
        if isinstance(content, list):
            text_parts = [
                p["text"] for p in content
                if isinstance(p, dict) and p.get("type") == "text"
            ]
            return " ".join(text_parts).strip()
        return content.strip()

    async def extract_receipt_items(self, image_bytes: bytes) -> Receipt:
        """Extract structured data from a receipt image."""
        msg = self._build_message(_RECEIPT_PROMPT, image_bytes, "image/jpeg")
        result: Receipt = await self._receipt_chain.ainvoke([msg])
        return result

    async def parse_bank_statement(
        self, file_bytes: bytes, file_type: str = "pdf"
    ) -> BankStatement:
        """Parse a bank statement (PDF or image) into transactions."""
        mime = _mime_type(file_type)
        msg = self._build_message(_STATEMENT_PROMPT, file_bytes, mime)
        result: BankStatement = await self._statement_chain.ainvoke([msg])
        return result


# Module-level singleton
_processor: MediaProcessor | None = None


def get_processor() -> MediaProcessor:
    global _processor
    if _processor is None:
        _processor = MediaProcessor()
    return _processor
