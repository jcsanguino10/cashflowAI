from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.middleware_client import Account, ActualClient, Category, Payee


@pytest.fixture(autouse=True)
def _env() -> None:
    """Set required env vars before any import triggers Config()."""
    import os

    os.environ.setdefault("TELEGRAM_TOKEN", "test-token")
    os.environ.setdefault("GEMINI_API_KEY", "test-key")
    os.environ.setdefault("MIDDLEWARE_API_KEY", "test-middleware-key")
    os.environ.setdefault("BUDGET_SYNC_ID", "test-sync-id")
    os.environ.setdefault("MIDDLEWARE_URL", "http://test:5007")


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock(spec=ActualClient)

    client.get_accounts = AsyncMock(
        return_value=[
            Account(
                id="acct-1",
                name="Compte Corrent",
                offbudget=False,
                closed=False,
                balance_current=150000,
            ),
            Account(
                id="acct-2",
                name="Estalvis",
                offbudget=False,
                closed=False,
                balance_current=500000,
            ),
            Account(
                id="acct-3",
                name="Targeta Credit",
                offbudget=True,
                closed=False,
                balance_current=-25000,
            ),
        ]
    )

    client.get_categories = AsyncMock(
        return_value=[
            Category(
                id="cat-food",
                name="Alimentació",
                is_income=False,
                hidden=False,
                group_id="group-1",
            ),
            Category(
                id="cat-transport",
                name="Transport",
                is_income=False,
                hidden=False,
                group_id="group-1",
            ),
            Category(
                id="cat-income",
                name="Ingressos",
                is_income=True,
                hidden=False,
                group_id="group-2",
            ),
        ]
    )

    client.get_payees = AsyncMock(
        return_value=[
            Payee(id="payee-merc", name="Mercadona", category=None, transfer_acct=None),
            Payee(
                id="payee-transfer",
                name="Transferència",
                category=None,
                transfer_acct="acct-2",
            ),
        ]
    )

    client.get_budget_month = AsyncMock(
        return_value={
            "total_budgeted": 200000,
            "total_spent": 85000,
            "total_balance": 115000,
            "to_budget": 50000,
            "total_income": 300000,
        }
    )

    client.add_transaction = AsyncMock(return_value="Transaction created")
    client.add_split_transaction = AsyncMock(
        return_value="Split transaction created"
    )

    return client


@pytest.fixture(autouse=True)
def _mock_actual_client(mock_client: MagicMock) -> AsyncGenerator[None]:
    """Replace ActualClient() in src.tools with the mock."""
    import src.tools as tools_mod

    with patch.object(tools_mod, "ActualClient", return_value=mock_client):
        tools_mod._client = mock_client
        yield
        tools_mod._client = None
