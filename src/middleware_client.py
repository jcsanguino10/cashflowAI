import asyncio
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import httpx

from src.config import config

_RETRY_MAX = 3
_RETRY_DELAY = 1.0


class MiddlewareError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)


@dataclass
class Account:
    id: str
    name: str
    offbudget: bool
    closed: bool
    balance_current: int | None = None


@dataclass
class Category:
    id: str
    name: str
    is_income: bool
    hidden: bool
    group_id: str


@dataclass
class CategoryGroup:
    id: str
    name: str
    is_income: bool
    hidden: bool
    categories: list = field(default_factory=list)


@dataclass
class Payee:
    id: str
    name: str
    category: str | None
    transfer_acct: str | None


@dataclass
class Transaction:
    id: str | None = None
    account: str | None = None
    date: str | None = None
    amount: int | None = None
    payee: str | None = None
    payee_name: str | None = None
    category: str | None = None
    notes: str | None = None
    cleared: bool | None = None
    is_parent: bool | None = None
    is_child: bool | None = None
    parent_id: str | None = None
    subtransactions: list[dict] | None = None


@dataclass
class BudgetMonth:
    month: str
    income_available: int
    last_month_overspent: int
    for_next_month: int
    total_budgeted: int
    to_budget: int
    from_last_month: int
    total_income: int
    total_spent: int
    total_balance: int
    category_groups: list[dict]


class ActualClient:
    def __init__(self) -> None:
        self._base = f"{config.middleware_url}/v1/budgets/{config.budget_sync_id}"
        self._headers = {"x-api-key": config.middleware_api_key}
        self._client = httpx.AsyncClient(base_url=self._base, headers=self._headers, timeout=30.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, _RETRY_MAX + 1):
            try:
                resp = await self._client.get(path)
                if resp.status_code != 200:
                    raise MiddlewareError(resp.text, resp.status_code)
                return resp.json()["data"]
            except MiddlewareError as e:
                if e.status_code != 500 or attempt == _RETRY_MAX:
                    raise
                print(f"[RETRY] _get {path} failed (500), intento {attempt}/{_RETRY_MAX}")
                await asyncio.sleep(_RETRY_DELAY * attempt)
                last_error = e
        raise last_error  # type: ignore[misc]

    async def _post(self, path: str, body: dict) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, _RETRY_MAX + 1):
            try:
                resp = await self._client.post(path, json=body)
                if resp.status_code >= 400:
                    raise MiddlewareError(resp.text, resp.status_code)
                return resp.json()
            except MiddlewareError as e:
                if e.status_code != 500 or attempt == _RETRY_MAX:
                    raise
                print(f"[RETRY] _post {path} failed (500), intento {attempt}/{_RETRY_MAX}")
                await asyncio.sleep(_RETRY_DELAY * attempt)
                last_error = e
        raise last_error  # type: ignore[misc]

    async def _patch(self, path: str, body: dict) -> Any:
        resp = await self._client.patch(path, json=body)
        if resp.status_code >= 400:
            raise MiddlewareError(resp.text, resp.status_code)
        return resp.json()

    async def _delete(self, path: str) -> Any:
        resp = await self._client.delete(path)
        if resp.status_code >= 400:
            raise MiddlewareError(resp.text, resp.status_code)
        return resp.json()

    # --- Accounts ---

    async def get_accounts(self) -> list[Account]:
        data = await self._get("/accounts")
        return [Account(**a) for a in data]

    async def get_account(self, account_id: str) -> Account | None:
        try:
            data = await self._get(f"/accounts/{account_id}")
            return Account(**data)
        except MiddlewareError:
            return None

    async def get_account_balance(self, account_id: str, cutoff_date: str | None = None) -> int:
        params = f"?cutoff_date={cutoff_date}" if cutoff_date else ""
        return await self._get(f"/accounts/{account_id}/balance{params}")

    # --- Transactions ---

    async def get_transactions(
        self,
        account_id: str,
        since_date: str,
        until_date: str | None = None,
    ) -> list[dict]:
        url = f"/accounts/{account_id}/transactions?since_date={since_date}"
        if until_date:
            url += f"&until_date={until_date}"
        return await self._get(url)

    async def add_transaction(
        self,
        account_id: str,
        transaction: Transaction,
        learn_categories: bool = True,
        run_transfers: bool = False,
    ) -> str:
        body = {
            "learnCategories": learn_categories,
            "runTransfers": run_transfers,
            "transaction": _transaction_to_dict(transaction),
        }
        result = await self._post(f"/accounts/{account_id}/transactions", body)
        return result.get("message", "ok")

    async def add_transactions_batch(
        self,
        account_id: str,
        transactions: list[Transaction],
        learn_categories: bool = True,
        run_transfers: bool = False,
    ) -> str:
        body = {
            "learnCategories": learn_categories,
            "runTransfers": run_transfers,
            "transactions": [_transaction_to_dict(t) for t in transactions],
        }
        result = await self._post(f"/accounts/{account_id}/transactions/batch", body)
        return result.get("message", "ok")

    async def add_split_transaction(
        self,
        account_id: str,
        payee_name: str,
        total_amount: int,
        date: str,
        subtransactions: list[dict],
        notes: str = "",
        category: str | None = None,
    ) -> str:
        parent = Transaction(
            account=account_id,
            payee_name=payee_name,
            amount=total_amount,
            date=date,
            notes=notes,
            category=category,
            is_parent=True,
            subtransactions=subtransactions,
        )
        return await self.add_transaction(account_id, parent)

    async def update_transaction(self, transaction_id: str, transaction: Transaction) -> str:
        body = {"transaction": _transaction_to_dict(transaction)}
        result = await self._patch(f"/transactions/{transaction_id}", body)
        return result.get("message", "Transaction updated")

    async def delete_transaction(self, transaction_id: str) -> str:
        result = await self._delete(f"/transactions/{transaction_id}")
        return result.get("message", "Transaction deleted")

    async def delete_transactions_batch(self, transaction_ids: list[str]) -> str:
        result = await self._delete("/transactions/batch")
        return result.get("message", "Transactions deleted")

    # --- Budget ---

    async def get_months(self) -> list[str]:
        return await self._get("/months")

    async def get_budget_month(self, month: str) -> dict:
        return await self._get(f"/months/{month}")

    # --- Categories ---

    async def get_categories(self) -> list[Category]:
        data = await self._get("/categories")
        return [Category(**c) for c in data]

    async def get_category_groups(self) -> list[CategoryGroup]:
        data = await self._get("/categorygroups")
        return [CategoryGroup(**g) for g in data]

    async def create_category_group(
        self, name: str, is_income: bool = False, hidden: bool = False
    ) -> str:
        body = {
            "category_group": {
                "name": name,
                "is_income": is_income,
                "hidden": hidden,
            }
        }
        result = await self._post("/categorygroups", body)
        return result["data"]

    async def create_category(
        self,
        name: str,
        group_id: str,
        is_income: bool = False,
        hidden: bool = False,
    ) -> str:
        body = {
            "category": {
                "name": name,
                "group_id": group_id,
                "is_income": is_income,
                "hidden": hidden,
            }
        }
        result = await self._post("/categories", body)
        return result["data"]

    async def get_category(self, category_id: str) -> Category | None:
        try:
            data = await self._get(f"/categories/{category_id}")
            return Category(**data)
        except MiddlewareError:
            return None

    # --- Payees ---

    async def get_payees(self) -> list[Payee]:
        data = await self._get("/payees")
        return [Payee(**p) for p in data]


def _transaction_to_dict(t: Transaction) -> dict:
    d: dict[str, Any] = {}
    if t.account is not None:
        d["account"] = t.account
    if t.date is not None:
        d["date"] = t.date
    if t.amount is not None:
        d["amount"] = t.amount
    if t.payee is not None:
        d["payee"] = t.payee
    if t.payee_name is not None:
        d["payee_name"] = t.payee_name
    if t.category is not None:
        d["category"] = t.category
    if t.notes is not None:
        d["notes"] = t.notes
    if t.cleared is not None:
        d["cleared"] = t.cleared
    if t.is_parent is not None:
        d["is_parent"] = t.is_parent
    if t.is_child is not None:
        d["is_child"] = t.is_child
    if t.parent_id is not None:
        d["parent_id"] = t.parent_id
    if t.subtransactions is not None:
        d["subtransactions"] = t.subtransactions
    return d


# Amount conversion helpers
def euros_to_cents(euros: float) -> int:
    return round(euros * 100)


def cents_to_euros(cents: int) -> float:
    return cents / 100.0
