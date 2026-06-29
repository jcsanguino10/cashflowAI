from datetime import date, timedelta
from typing import Any, Optional

from langchain_core.tools import tool

from src.config import config
from src.middleware_client import (
    ActualClient,
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
    return None


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
    date: str,
    category_name: Optional[str] = None,
    notes: Optional[str] = None,
) -> str:
    """Add a transaction to the budget.

    Positive amount = income, negative amount = expense.

    Args:
        account_name: Account name (e.g. "Compte Corrent")
        payee_name: Payee or description
        amount: Amount in euros (e.g. -50.00 for an expense)
        date: Date YYYY-MM-DD
        category_name: Optional category name
        notes: Optional notes
    """
    client = await _get_client()
    account_id = await _resolve_account(account_name)
    category_id = await _resolve_category(category_name) if category_name else None

    tx = Transaction(
        account=account_id,
        payee_name=payee_name,
        amount=euros_to_cents(amount),
        date=date,
        category=category_id,
        notes=notes,
    )
    result = await client.add_transaction(account_id, tx)
    return f"✅ Transaction added: {payee_name} €{amount:+,.2f} — {result}"


@tool
async def add_split_transaction(
    account_name: str,
    payee_name: str,
    amount: float,
    date: str,
    subtransactions: list[dict],
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
        date: Date YYYY-MM-DD
        subtransactions: List of line items
        notes: Optional notes for the parent transaction
    """
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
        date=date,
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


async def shutdown_client() -> None:
    """Close the HTTP client singleton on shutdown."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None
