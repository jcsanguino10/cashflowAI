from typing import Annotated, Any, Literal, Optional, TypedDict

from google.genai.types import AutomaticFunctionCallingConfig
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from src.config import config
from src.multimodal import get_processor
from src.tools import (
    add_split_transaction,
    add_transaction,
    add_transactions_batch,
    analyze_spending,
    create_new_category,
    create_new_category_group,
    get_accounts,
    get_balances,
    get_budget_month,
    get_categories_list,
    get_category_groups_list,
    get_recommendations,
    get_transactions,
)

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    media: Optional[dict[str, Any]]
    media_output: Optional[str]


# ---------------------------------------------------------------------------
# LLM & tools
# ---------------------------------------------------------------------------

_TOOLS = [
    get_accounts,
    get_balances,
    get_budget_month,
    get_transactions,
    add_transaction,
    add_transactions_batch,
    add_split_transaction,
    analyze_spending,
    get_recommendations,
    get_categories_list,
    get_category_groups_list,
    create_new_category,
    create_new_category_group,
]

_llm = ChatGoogleGenerativeAI(
    model=config.gemini_model,
    google_api_key=config.gemini_api_key,
    temperature=0.3,
)

_agent = _llm.bind_tools(
    _TOOLS,
    automatic_function_calling=AutomaticFunctionCallingConfig(disable=True),
)

_SYSTEM_PROMPT = """Eres un asistente de finanzas personales que ayuda a gestionar un presupuesto en Actual Budget.

Reglas importantes:
- Todos los importes están en euros (€).
- Para gastos, usa cantidades negativas en la herramienta add_transaction.
- Para ingresos, usa cantidades positivas.
- Las fechas deben estar en formato YYYY-MM-DD.
- Si el usuario no especifica una fecha, usa la fecha de hoy.
- Para gastos de supermercado o compras con varios artículos, usa add_split_transaction.
- Responde siempre en español, de forma clara y concisa.
- Cuando muestres importes usa siempre el símbolo € y dos decimales.

Selección de cuenta:
- Si no sabes qué cuenta usar, llama primero a get_accounts() para ver las cuentas disponibles.
- Por defecto, prefiere una cuenta que contenga la palabra "credit" (sin distinción de mayúsculas/minúsculas).
- Si hay varias cuentas y no está claro cuál usar, pregunta al usuario antes de continuar.

Procesamiento por lotes:
- Cuando recibas un extracto bancario con múltiples transacciones (3 o más), usa add_transactions_batch en lugar de llamar add_transaction repetidamente.
- add_transactions_batch ya maneja el particionado en lotes internamente.

Asignación de categorías:
- Siempre que crees transacciones (individuales o en lote), llama primero a get_categories_list() para ver las categorías existentes en Actual Budget.
- Clasifica cada transacción en la categoría más adecuada según la descripción o el nombre del beneficiario.
- Si ninguna categoría existente es adecuada, llama a get_category_groups_list() para ver los grupos disponibles, elige el grupo más apropiado y crea la nueva categoría con create_new_category(nombre, grupo).
- Si ni siquiera existe un grupo adecuado, créalo primero con create_new_category_group(nombre)."""


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


async def multimodal_preprocessor(state: AgentState) -> dict[str, Any]:
    media = state.get("media")
    if not media:
        print("[TRACE agent] no media en state, saltando")
        return {}

    processor = get_processor()
    media_type = media.get("type", "")
    media_data = media.get("data")
    file_type = media.get("file_type", "")

    print(f"[TRACE agent] multimodal_preprocessor: type={media_type}, file_type={file_type}, data_size={len(media_data) if media_data else 0}")

    if not media_data:
        print("[TRACE agent] media_data vacío, saltando")
        return {}

    try:
        if media_type == "voice":
            text = await processor.transcribe_audio(media_data, file_type or "ogg")
            result = f"[Transcripción de audio]: {text}"
        elif media_type == "photo":
            receipt = await processor.extract_receipt_items(media_data)
            items_str = "\n".join(
                f"  - {item.name}: €{item.amount:.2f}" + (f" ({item.category})" if item.category else "")
                for item in receipt.items
            )
            result = (
                f"[Recibo procesado]: Tienda: {receipt.store}, "
                f"Fecha: {receipt.date}, Total: €{receipt.total:.2f}\n"
                f"Artículos:\n{items_str}"
            )
        elif media_type == "document":
            print("[TRACE agent] llamando a parse_bank_statement...")
            statement = await processor.parse_bank_statement(media_data, file_type or "pdf")
            txs_count = len(statement.transactions) if statement.transactions else 0
            print(f"[TRACE agent] parse_bank_statement devolvió {txs_count} transacciones")
            txs_str = "\n".join(
                f"  - {tx.date}: {tx.description}: €{tx.amount:+.2f}" + (f" ({tx.category})" if tx.category else "")
                for tx in statement.transactions
            )
            result = f"[Extracto bancario procesado]:\n{txs_str}"
        else:
            result = f"[Medio no soportado: {media_type}]"

        print(f"[TRACE agent] resultado generado: {result[:300]}")
        return {
            "messages": [HumanMessage(content=result)],
            "media_output": result,
        }
    except Exception as e:
        print(f"[TRACE agent] EXCEPCIÓN procesando {media_type}: {e!s}")
        import traceback
        traceback.print_exc()
        error_msg = f"[Error procesando {media_type}]: {e!s}"
        return {
            "messages": [HumanMessage(content=error_msg)],
            "media_output": error_msg,
        }


async def financial_agent(state: AgentState) -> dict[str, Any]:
    messages = state["messages"]
    if not any(isinstance(m, SystemMessage) for m in messages):
        messages = [SystemMessage(content=_SYSTEM_PROMPT)] + messages

    response = await _agent.ainvoke(messages)
    return {"messages": [response]}


# ---------------------------------------------------------------------------
# Conditional edge
# ---------------------------------------------------------------------------


def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return "__end__"


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------


def build_agent() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("multimodal_preprocessor", multimodal_preprocessor)
    workflow.add_node("financial_agent", financial_agent)
    workflow.add_node("tools", ToolNode(_TOOLS))

    workflow.set_entry_point("multimodal_preprocessor")

    workflow.add_edge("multimodal_preprocessor", "financial_agent")
    workflow.add_conditional_edges("financial_agent", should_continue)
    workflow.add_edge("tools", "financial_agent")

    return workflow.compile()


agent = build_agent()
