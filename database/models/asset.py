from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from .base import Base

if TYPE_CHECKING:
    from .oracle import Network, Oracle
    from .donation import Donation


class Asset(Base):
    __tablename__ = 'assets'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    
    network_id: Mapped[int] = mapped_column(Integer, ForeignKey('networks.id'), nullable=False)
    oracle_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('oracles.id'), nullable=True)
    
    contract_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    decimals: Mapped[int] = mapped_column(Integer, default=18, nullable=False)
    
    asset_type: Mapped[str] = mapped_column(String(20), default='token', nullable=False)
    is_stablecoin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    website_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    
    network: Mapped["Network"] = relationship("Network", back_populates="assets")
    oracle: Mapped[Optional["Oracle"]] = relationship("Oracle", back_populates="assets")
    donations: Mapped[list["Donation"]] = relationship("Donation", back_populates="asset")
    
    def __repr__(self):
        return f"<Asset(symbol='{self.symbol}', network='{self.network.name}')>" 