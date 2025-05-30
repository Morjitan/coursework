from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from .base import Base

if TYPE_CHECKING:
    from .streamer import Streamer
    from .asset import Asset


class Donation(Base):
    __tablename__ = 'donations'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    streamer_id: Mapped[int] = mapped_column(Integer, ForeignKey('streamers.id'), nullable=False)
    asset_id: Mapped[int] = mapped_column(Integer, ForeignKey('assets.id'), nullable=False)
    
    donor_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    amount: Mapped[Numeric] = mapped_column(Numeric(20, 8), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    payment_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    nonce: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    transaction_hash: Mapped[Optional[str]] = mapped_column(String(66), nullable=True, index=True)
    
    status: Mapped[str] = mapped_column(String(20), default='pending', nullable=False, index=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False,
        index=True
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    streamer: Mapped["Streamer"] = relationship("Streamer", back_populates="received_donations")
    asset: Mapped["Asset"] = relationship("Asset", back_populates="donations")
    
    def __repr__(self):
        return f"<Donation(amount={self.amount}, asset='{self.asset.symbol}', status='{self.status}')>" 