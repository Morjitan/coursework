from sqlalchemy import Column, Integer, String, DateTime, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional
from decimal import Decimal

from .base import Base


class Currency(Base):
    __tablename__ = "currencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    rate_to_usd: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    is_base: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        nullable=False
    )

    def __repr__(self) -> str:
        return f"<Currency(code={self.code}, rate_to_usd={self.rate_to_usd})>"
    
    @property
    def display_name(self) -> str:
        if self.symbol:
            return f"{self.name} ({self.symbol})"
        return self.name
    
    def convert_to(self, amount: Decimal, target_currency: 'Currency') -> Decimal:
        if self.code == target_currency.code:
            return amount
        
        if self.is_base:
            usd_amount = amount
        else:
            usd_amount = amount * self.rate_to_usd
        
        if target_currency.is_base:
            return usd_amount
        else:
            return usd_amount / target_currency.rate_to_usd 