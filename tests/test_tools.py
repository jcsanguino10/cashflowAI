from unittest.mock import AsyncMock

import pytest

from src.tools import (
    add_split_transaction,
    add_transaction,
    analyze_spending,
    get_accounts,
    get_balances,
    get_budget_month,
    get_recommendations,
    get_transactions,
)


@pytest.mark.asyncio
async def test_get_accounts() -> None:
    result = await get_accounts.ainvoke({})
    assert "Compte Corrent" in result
    assert "Estalvis" in result
    assert "Targeta Credit" in result
    assert "[off-budget]" in result
    assert "[closed]" not in result


@pytest.mark.asyncio
async def test_get_balances() -> None:
    result = await get_balances.ainvoke({})
    assert "Compte Corrent" in result
    assert "€1,500.00" in result
    assert "€5,000.00" in result
    assert "€-250.00" in result
    assert "€6,250.00" in result
    assert "[off-budget]" in result


@pytest.mark.asyncio
async def test_get_budget_month() -> None:
    result = await get_budget_month.ainvoke({"year": 2026, "month": 6})
    assert "2026-06" in result
    assert "€2,000.00" in result
    assert "€850.00" in result
    assert "€1,150.00" in result
    assert "€500.00" in result


@pytest.mark.asyncio
async def test_add_transaction(mock_client) -> None:
    result = await add_transaction.ainvoke({
        "account_name": "Compte Corrent",
        "payee_name": "Netflix",
        "amount": -50.0,
        "date": "2026-06-15",
        "category_name": "Alimentació",
        "notes": "Suscripció juny",
    })
    assert "✅" in result
    assert "Netflix" in result

    mock_client.add_transaction.assert_awaited_once()
    tx = mock_client.add_transaction.await_args.args[1]
    assert tx.amount == -5000
    assert tx.payee_name == "Netflix"
    assert tx.account == "acct-1"


@pytest.mark.asyncio
async def test_add_transaction_income(mock_client) -> None:
    await add_transaction.ainvoke({
        "account_name": "Compte Corrent",
        "payee_name": "Nòmina",
        "amount": 2500.0,
        "date": "2026-06-01",
    })
    tx = mock_client.add_transaction.await_args.args[1]
    assert tx.amount == 250000


@pytest.mark.asyncio
async def test_add_transaction_unknown_account() -> None:
    with pytest.raises(ValueError, match="Account 'No existeix' not found"):
        await add_transaction.ainvoke({
            "account_name": "No existeix",
            "payee_name": "Test",
            "amount": -10.0,
            "date": "2026-06-01",
        })


@pytest.mark.asyncio
async def test_get_transactions(mock_client) -> None:
    mock_client.get_transactions = AsyncMock(
        return_value=[
            {
                "date": "2026-06-10",
                "amount": -2000,
                "payee_name": "Mercadona",
                "category": "cat-food",
                "category_name": "Alimentació",
                "notes": "",
            },
            {
                "date": "2026-06-12",
                "amount": -500,
                "payee_name": "Bus",
                "category": "cat-transport",
                "category_name": "Transport",
                "notes": "Bitllet senzill",
            },
        ]
    )
    result = await get_transactions.ainvoke({
        "account_name": "Compte Corrent",
        "start_date": "2026-06-01",
        "end_date": "2026-06-30",
    })
    assert "Mercadona" in result
    assert "Bus" in result
    assert "€-20.00" in result
    assert "€-5.00" in result
    assert "Bitllet senzill" in result


@pytest.mark.asyncio
async def test_get_transactions_filter_category(mock_client) -> None:
    mock_client.get_transactions = AsyncMock(
        return_value=[
            {
                "date": "2026-06-10",
                "amount": -2000,
                "payee_name": "Mercadona",
                "category": "cat-food",
                "category_name": "Alimentació",
                "notes": "",
            },
            {
                "date": "2026-06-12",
                "amount": -500,
                "payee_name": "Bus",
                "category": "cat-transport",
                "category_name": "Transport",
                "notes": "",
            },
        ]
    )
    result = await get_transactions.ainvoke({
        "account_name": "Compte Corrent",
        "start_date": "2026-06-01",
        "end_date": "2026-06-30",
        "category_name": "Alimentació",
    })
    assert "Mercadona" in result
    assert "Bus" not in result


@pytest.mark.asyncio
async def test_add_split_transaction(mock_client) -> None:
    subtransactions = [
        {"amount": 3.50, "category": "Alimentació", "notes": "Pa"},
        {"amount": 8.00, "category": "Alimentació", "notes": "Llet i ous"},
        {"amount": 5.50, "category": "Transport", "notes": "Gasolina"},
    ]
    result = await add_split_transaction.ainvoke({
        "account_name": "Compte Corrent",
        "payee_name": "Mercadona",
        "amount": 17.0,
        "date": "2026-06-15",
        "subtransactions": subtransactions,
    })
    assert "✅" in result
    assert "Mercadona" in result
    assert "3 items" in result

    mock_client.add_split_transaction.assert_awaited_once()
    kwargs = mock_client.add_split_transaction.await_args.kwargs
    assert kwargs["total_amount"] == 1700
    assert kwargs["payee_name"] == "Mercadona"
    assert len(kwargs["subtransactions"]) == 3
    assert kwargs["subtransactions"][0]["amount"] == 350


@pytest.mark.asyncio
async def test_analyze_spending(mock_client) -> None:
    mock_client.get_transactions = AsyncMock(
        side_effect=[
            [
                {
                    "date": "2026-06-01",
                    "amount": -2000,
                    "payee_name": "Mercadona",
                    "category": "cat-food",
                    "category_name": "Alimentació",
                    "notes": "",
                },
                {
                    "date": "2026-06-03",
                    "amount": -5000,
                    "payee_name": "Renta",
                    "category": None,
                    "category_name": "",
                    "notes": "",
                },
            ],
            [],
            [
                {
                    "date": "2026-06-05",
                    "amount": -1500,
                    "payee_name": "Bus",
                    "category": "cat-transport",
                    "category_name": "Transport",
                    "notes": "",
                },
            ],
        ]
    )
    result = await analyze_spending.ainvoke({
        "start_date": "2026-06-01",
        "end_date": "2026-06-30",
    })
    assert "Spending Analysis" in result
    assert "Total spent: €85.00" in result
    assert "Transactions: 3" in result
    assert "Alimentació" in result
    assert "Transport" in result
    assert "Uncategorized" in result


@pytest.mark.asyncio
async def test_get_recommendations(mock_client) -> None:
    mock_client.get_transactions = AsyncMock(side_effect=[[], [], []])
    result = await get_recommendations.ainvoke({})
    assert "Financial Summary" in result
    assert "Compte Corrent" in result
    assert "Estalvis" in result
    assert "€1,500.00" in result
    assert "Net worth" in result
    assert "Budget" in result
