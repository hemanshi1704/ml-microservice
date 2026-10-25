from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class PortfolioIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    currency: str = Field("USD", min_length=3, max_length=3)


class PortfolioOut(PortfolioIn):
    id: int
    model_config = {"from_attributes": True}


class TransactionIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=16)
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)
    fees: float = Field(0, ge=0)
    trade_date: date = Field(default_factory=date.today)

    @field_validator("symbol")
    @classmethod
    def up(cls, v: str) -> str:
        return v.strip().upper()


class TransactionOut(TransactionIn):
    id: int
    model_config = {"from_attributes": True}
