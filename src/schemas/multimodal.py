from typing import Optional

from pydantic import BaseModel


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
