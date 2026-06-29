import asyncio
from datetime import date, timedelta
from typing import Any, Optional

from langchain_core.tools import tool

from src.config import config
from src.middleware_client import (
    ActualClient,
    CategoryGroup,
    Transaction,
    cents_to_euros,
    euros_to_cents,
)

_client: ActualClient | None = None


async def _get_client() -> ActualClient:
    global _client
    if _client is None:
        _client = ActualClient()
    return _client


async def _resolve_account(account_name: str) -> str:
    client = await _get_client()
    accounts = await client.get_accounts()
    name_lower = account_name.lower()
    for acct in accounts:
        if acct.name.lower() == name_lower:
            return acct.id
    for acct in accounts:
        if name_lower in acct.name.lower():
            return acct.id
    names = ", ".join(a.name for a in accounts)
    raise ValueError(
        f"Account '{account_name}' not found. Available: {names}"
    )


async def _resolve_category(category_name: str) -> str | None:
    if not category_name:
        return None
    client = await _get_client()
    categories = await client.get_categories()
    name_lower = category_name.lower()
    for cat in categories:
        if cat.name.lower() == name_lower:
            return cat.id
    for cat in categories:
        if name_lower in cat.name.lower():
            return cat.id
    names = ", ".join(c.name for c in categories)
    print(f"[WARN] Categoría '{category_name}' no encontrada. Disponibles: {names}")
    return None


async def _resolve_category_group(group_name: str) -> str:
    client = await _get_client()
    groups = await client.get_category_groups()
    name_lower = group_name.lower()
    for g in groups:
        if g.name.lower() == name_lower:
            return g.id
    for g in groups:
        if name_lower in g.name.lower():
            return g.id
    group_names = ", ".join(g.name for g in groups)
    raise ValueError(
        f"Grupo '{group_name}' no encontrado. Disponibles: {group_names}"
    )


async def _spending_by_category(
    start_date: str, end_date: str
) -> dict[str, Any]:
    client = await _get_client()
    accounts = await client.get_accounts()
    categories = await client.get_categories()

    category_map: dict[str, str] = {c.id: c.name for c in categories}

    all_tx: list[dict] = []
    for acct in accounts:
        if acct.closed:
            continue
        try:
            txs = await client.get_transactions(acct.id, start_date, end_date)
            for t in txs:
                t["account_name"] = acct.name
            all_tx.extend(txs)
        except Exception:
            pass

    cat_spending: dict[str, float] = {}
    total = 0.0
    tx_count = 0

    for t in all_tx:
        amt = t.get("amount", 0)
        if amt >= 0:
            continue
        tx_count += 1
        amt_euros = abs(cents_to_euros(amt))
        total += amt_euros
        cat_id = t.get("category")
        cat_name = (
            category_map.get(cat_id, "Uncategorized")
            if cat_id
            else "Uncategorized"
        )
        cat_spending[cat_name] = cat_spending.get(cat_name, 0.0) + amt_euros

    return {
        "total": total,
        "tx_count": tx_count,
        "by_category": cat_spending,
        "start_date": start_date,
        "end_date": end_date,
    }


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool
async def get_accounts() -> str:
    """Get all accounts from the budget."""
    client = await _get_client()
    accounts = await client.get_accounts()
    lines = []
    for a in accounts:
        parts = [f"• {a.name}"]
        if a.closed:
            parts.append("[closed]")
        if a.offbudget:
            parts.append("[off-budget]")
        lines.append(" ".join(parts))
    return "\n".join(lines) if lines else "No accounts found."


@tool
async def get_balances() -> str:
    """Get current balances for all on-budget accounts."""
    client = await _get_client()
    accounts = await client.get_accounts()
    lines = []
    total = 0.0
    for a in accounts:
        if a.closed:
            continue
        bal = cents_to_euros(a.balance_current) if a.balance_current is not None else 0.0
        total += bal
        tag = " [off-budget]" if a.offbudget else ""
        lines.append(f"• {a.name}: €{bal:,.2f}{tag}")
    lines.append(f"\nTotal: €{total:,.2f}")
    return "\n".join(lines)


@tool
async def get_budget_month(year: int, month: int) -> str:
    """Get budget status for a specific month.

    Args:
        year: Year (e.g. 2026)
        month: Month number (1-12)
    """
    client = await _get_client()
    month_str = f"{year:04d}-{month:02d}"
    data = await client.get_budget_month(month_str)
    lines = [
        f"Budget for {month_str}",
        f"  Total budgeted:  €{cents_to_euros(data.get('total_budgeted', 0)):,.2f}",
        f"  Total spent:     €{cents_to_euros(abs(data.get('total_spent', 0))):,.2f}",
        f"  Remaining:       €{cents_to_euros(data.get('total_balance', 0)):,.2f}",
        f"  To budget:       €{cents_to_euros(data.get('to_budget', 0)):,.2f}",
    ]
    return "\n".join(lines)


@tool
async def get_transactions(
    account_name: str,
    start_date: str,
    end_date: str,
    category_name: Optional[str] = None,
) -> str:
    """Get transactions for an account within a date range.

    Args:
        account_name: Name of the account (e.g. "Compte Corrent")
        start_date: Start date YYYY-MM-DD
        end_date: End date YYYY-MM-DD
        category_name: Optional category to filter by
    """
    client = await _get_client()
    account_id = await _resolve_account(account_name)
    category_id = await _resolve_category(category_name) if category_name else None

    transactions = await client.get_transactions(account_id, start_date, end_date)
    if category_id:
        transactions = [t for t in transactions if t.get("category") == category_id]

    if not transactions:
        return "No transactions found."

    lines = [f"Transactions in {account_name} ({start_date} to {end_date}):"]
    for t in transactions:
        amt = cents_to_euros(t.get("amount", 0))
        payee = t.get("payee_name") or t.get("payee") or "Unknown"
        cat = t.get("category_name", "")
        note = t.get("notes", "")
        suffix = f" — {note}" if note else ""
        suffix += f" [{cat}]" if cat else ""
        lines.append(f"  {t['date']} | {payee} | €{amt:+,.2f}{suffix}")

    return "\n".join(lines)


@tool
async def add_transaction(
    account_name: str,
    payee_name: str,
    amount: float,
    tx_date: str = "",
    category_name: Optional[str] = None,
    notes: Optional[str] = None,
) -> str:
    """Add a transaction to the budget.

    Positive amount = income, negative amount = expense.

    Args:
        account_name: Account name (e.g. "Compte Corrent")
        payee_name: Payee or description
        amount: Amount in euros (e.g. -50.00 for an expense)
        tx_date: Date YYYY-MM-DD (defaults to today if not provided)
        category_name: Optional category name
        notes: Optional notes
    """
    if not tx_date:
        tx_date = date.today().isoformat()
    client = await _get_client()
    account_id = await _resolve_account(account_name)
    category_id = await _resolve_category(category_name) if category_name else None

    tx = Transaction(
        account=account_id,
        payee_name=payee_name,
        amount=euros_to_cents(amount),
        date=tx_date,
        category=category_id,
        notes=notes,
    )
    result = await client.add_transaction(account_id, tx)
    return f"✅ Transaction added: {payee_name} €{amount:+,.2f} — {result}"


_BATCH_CHUNK_SIZE = 10
_BATCH_CHUNK_DELAY = 0.3


@tool
async def add_transactions_batch(
    account_name: str,
    transactions: list[dict],
) -> str:
    """Add multiple transactions at once to an account.

    Use this for bank statements, receipt batches or any bulk import.
    Each transaction dict must have:
      - payee_name (str)
      - amount (float, negative for expenses, positive for income)
      - date (str YYYY-MM-DD)
    Optional fields:
      - category_name (str)
      - notes (str)

    Args:
        account_name: Account name (e.g. "Nubank Credit", "Compte Corrent")
        transactions: List of transaction dicts
    """
    client = await _get_client()
    account_id = await _resolve_account(account_name)

    total = len(transactions)
    processed = 0
    errors: list[str] = []

    chunks = [
        transactions[i : i + _BATCH_CHUNK_SIZE]
        for i in range(0, total, _BATCH_CHUNK_SIZE)
    ]

    for chunk_idx, chunk in enumerate(chunks, 1):
        txs: list[Transaction] = []
        for tx_data in chunk:
            category_id = None
            if "category_name" in tx_data and tx_data["category_name"]:
                category_id = await _resolve_category(tx_data["category_name"])
            tx_date = tx_data.get("date", "")
            if not tx_date:
                tx_date = date.today().isoformat()
            txs.append(
                Transaction(
                    account=account_id,
                    payee_name=tx_data["payee_name"],
                    amount=euros_to_cents(tx_data["amount"]),
                    date=tx_date,
                    category=category_id,
                    notes=tx_data.get("notes"),
                )
            )

        try:
            result = await client.add_transactions_batch(account_id, txs)
            processed += len(chunk)
        except Exception as e:
            errors.append(f"chunk {chunk_idx}: {e!s}")

        if chunk_idx < len(chunks):
            await asyncio.sleep(_BATCH_CHUNK_DELAY)

    parts = [f"✅ {processed}/{total} transacciones procesadas en {len(chunks)} lote(s)"]
    if errors:
        parts.append(f"Errores: {'; '.join(errors)}")
    return "\n".join(parts)


@tool
async def add_split_transaction(
    account_name: str,
    payee_name: str,
    amount: float,
    subtransactions: list[dict],
    tx_date: str = "",
    notes: Optional[str] = None,
) -> str:
    """Create a split transaction with individual line items (e.g. from a receipt).

    Each subtransaction dict must have:
      - amount (float, in euros)
      - category (str, category name)
      - notes (str, optional item description)

    The sum of subtransaction amounts must equal the total amount.

    Args:
        account_name: Account name (e.g. "Compte Corrent")
        payee_name: Store / payee name
        amount: Total amount in euros
        subtransactions: List of line items
        tx_date: Date YYYY-MM-DD (defaults to today if not provided)
        notes: Optional notes for the parent transaction
    """
    if not tx_date:
        tx_date = date.today().isoformat()
    client = await _get_client()
    account_id = await _resolve_account(account_name)

    converted = []
    for st in subtransactions:
        item = dict(st)
        item["amount"] = euros_to_cents(st["amount"])
        if "category" in st and st["category"]:
            cat_id = await _resolve_category(st["category"])
            if cat_id:
                item["category"] = cat_id
        converted.append(item)

    result = await client.add_split_transaction(
        account_id=account_id,
        payee_name=payee_name,
        total_amount=euros_to_cents(amount),
        date=tx_date,
        subtransactions=converted,
        notes=notes or "",
    )
    return f"✅ Split transaction added: {payee_name} €{amount:+,.2f} ({len(subtransactions)} items) — {result}"


@tool
async def analyze_spending(start_date: str, end_date: str) -> str:
    """Analyze spending across all accounts for a date range.

    Use this to understand where money is going.

    Args:
        start_date: Start date YYYY-MM-DD
        end_date: End date YYYY-MM-DD
    """
    data = await _spending_by_category(start_date, end_date)
    total = data["total"]
    by_cat = data["by_category"]
    sorted_cats = sorted(by_cat.items(), key=lambda x: x[1], reverse=True)

    lines = [
        f"Spending Analysis: {start_date} to {end_date}",
        f"Total spent: €{total:,.2f}",
        f"Transactions: {data['tx_count']}",
        "",
        "By category:",
    ]
    for cat_name, amt in sorted_cats:
        pct = (amt / total * 100) if total > 0 else 0
        lines.append(f"  • {cat_name}: €{amt:,.2f} ({pct:.1f}%)")

    return "\n".join(lines)


@tool
async def get_recommendations() -> str:
    """Get a financial summary with accounts, month budget, and recent spending.

    Use this to generate personalized financial recommendations.
    """
    client = await _get_client()
    today = date.today()
    month_str = f"{today.year:04d}-{today.month:02d}"
    start = f"{today.year:04d}-{today.month:02d}-01"

    if today.month == 12:
        end = date(today.year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(today.year, today.month + 1, 1) - timedelta(days=1)
    end_str = end.isoformat()

    accounts = await client.get_accounts()
    budget: dict[str, Any] = {}
    try:
        budget = await client.get_budget_month(month_str)
    except Exception:
        pass

    spending = await _spending_by_category(start, end_str)

    lines = [
        f"Financial Summary — {month_str}",
        "",
        "Accounts:",
    ]
    for a in accounts:
        if a.closed or a.balance_current is None:
            continue
        tag = " [off-budget]" if a.offbudget else ""
        lines.append(f"  • {a.name}: €{cents_to_euros(a.balance_current):,.2f}{tag}")

    total_net = sum(
        cents_to_euros(a.balance_current)
        for a in accounts
        if not a.closed and a.balance_current is not None
    )
    lines.append(f"\nNet worth: €{total_net:,.2f}")
    lines.append("")

    lines.append(f"Budget ({month_str}):")
    lines.append(f"  Budgeted:  €{cents_to_euros(budget.get('total_budgeted', 0)):,.2f}")
    lines.append(f"  Spent:     €{cents_to_euros(abs(budget.get('total_spent', 0))):,.2f}")
    lines.append(f"  Remaining: €{cents_to_euros(budget.get('total_balance', 0)):,.2f}")
    lines.append(f"  To budget: €{cents_to_euros(budget.get('to_budget', 0)):,.2f}")
    lines.append("")

    lines.append(f"Spending so far ({start} to {end_str}):")
    lines.append(f"  Total: €{spending['total']:,.2f} ({spending['tx_count']} tx)")
    for cat_name, amt in sorted(
        spending["by_category"].items(), key=lambda x: x[1], reverse=True
    ):
        pct = (amt / spending["total"] * 100) if spending["total"] > 0 else 0
        lines.append(f"  • {cat_name}: €{amt:,.2f} ({pct:.1f}%)")

    return "\n".join(lines)


@tool
async def get_categories_list() -> str:
    """Get all categories from the budget, grouped by category group.

    Use this to see what categories exist before creating transactions.
    """
    client = await _get_client()
    categories = await client.get_categories()
    groups = await client.get_category_groups()

    group_map: dict[str, str] = {g.id: g.name for g in groups}
    by_group: dict[str, list[str]] = {}
    for cat in categories:
        if cat.hidden:
            continue
        gname = group_map.get(cat.group_id, "Otros")
        by_group.setdefault(gname, []).append(cat.name)

    lines = ["Categorías disponibles:"]
    for gname, cat_names in sorted(by_group.items()):
        lines.append(f"  [{gname}]")
        for name in sorted(cat_names):
            lines.append(f"    • {name}")
    return "\n".join(lines)


@tool
async def get_category_groups_list() -> str:
    """Get all category groups from the budget.

    Use this before creating a new category to find which group to use.
    """
    client = await _get_client()
    groups = await client.get_category_groups()
    lines = ["Grupos de categorías:"]
    for g in groups:
        if not g.hidden:
            lines.append(f"  • {g.name}")
    return "\n".join(lines)


@tool
async def create_new_category(name: str, group_name: str) -> str:
    """Create a new category in the specified group.

    Call get_category_groups_list() first to see available groups.
    The category will be created in the existing group you specify.

    Args:
        name: Name for the new category (e.g. "Suscripciones Streaming")
        group_name: Name of the existing group to place it in
    """
    client = await _get_client()
    group_id = await _resolve_category_group(group_name)
    cat_id = await client.create_category(name, group_id)
    return f"✅ Categoría '{name}' creada (id: {cat_id}) en grupo '{group_name}'"


@tool
async def create_new_category_group(name: str) -> str:
    """Create a new category group.

    Use this when no existing group is suitable for a new category.

    Args:
        name: Name for the new group (e.g. "Suscripciones")
    """
    client = await _get_client()
    group_id = await client.create_category_group(name)
    return f"✅ Grupo '{name}' creado (id: {group_id})"


async def shutdown_client() -> None:
    """Close the HTTP client singleton on shutdown."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None
