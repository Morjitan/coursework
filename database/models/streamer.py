"""
Модель стримера
"""

from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from .base import Base

if TYPE_CHECKING:
    from .donation import Donation


class Streamer(Base):
    """Модель стримера"""
    __tablename__ = "streamers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    wallet_address: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        nullable=False
    )

    # Связи
    received_donations: Mapped[list["Donation"]] = relationship(
        "Donation", 
        back_populates="streamer",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Streamer(telegram_id={self.telegram_id}, name={self.name})>" 