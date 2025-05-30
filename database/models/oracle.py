"""
Модели Oracle системы
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from .base import Base

if TYPE_CHECKING:
    from .asset import Asset


class Network(Base):
    """Модель блокчейн-сети"""
    __tablename__ = 'networks'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)  # ethereum, bsc, polygon
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)  # Ethereum Mainnet
    chain_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True, nullable=True)  # 1, 56, 137
    
    # Технические параметры
    rpc_endpoint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    explorer_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    native_symbol: Mapped[str] = mapped_column(String(10), nullable=False)  # ETH, BNB, MATIC
    
    # Статус
    is_mainnet: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_evm_compatible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    
    # Связи
    assets: Mapped[list["Asset"]] = relationship("Asset", back_populates="network")
    oracles: Mapped[list["Oracle"]] = relationship("Oracle", back_populates="network")
    
    def __repr__(self):
        return f"<Network(name='{self.name}', display_name='{self.display_name}', chain_id={self.chain_id})>"


class OracleType(Base):
    """Модель типа оракула"""
    __tablename__ = 'oracle_types'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)  # chainlink, coingecko_api
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)  # Chainlink Price Feeds
    
    # Характеристики
    is_onchain: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_decentralized: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    requires_gas: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Связи
    oracles: Mapped[list["Oracle"]] = relationship("Oracle", back_populates="oracle_type")
    
    def __repr__(self):
        return f"<OracleType(name='{self.name}')>"


class Oracle(Base):
    """
    Модель оракула - источник данных о цене актива к USD
    Может быть на другой сети, чем сам актив
    """
    __tablename__ = 'oracles'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Связи
    oracle_type_id: Mapped[int] = mapped_column(Integer, ForeignKey('oracle_types.id'), nullable=False)
    network_id: Mapped[int] = mapped_column(Integer, ForeignKey('networks.id'), nullable=False)
    
    # Конфигурация для получения цены к USD
    contract_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Для onchain
    api_endpoint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Для API
    trading_pair: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # ETH/USD, BTC/USDT
    
    # Технические параметры
    decimals: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Статистика
    last_price_usd: Mapped[Optional[Numeric]] = mapped_column(Numeric(20, 8), nullable=True)
    last_update: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    
    # Связи
    oracle_type: Mapped["OracleType"] = relationship("OracleType", back_populates="oracles")
    network: Mapped["Network"] = relationship("Network", back_populates="oracles")
    assets: Mapped[list["Asset"]] = relationship("Asset", back_populates="oracle")
    
    def __repr__(self):
        return f"<Oracle(type='{self.oracle_type.name}', network='{self.network.name}')>" 