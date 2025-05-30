import logging
from typing import Dict, Optional, List
from decimal import Decimal
from datetime import datetime, timedelta

from database import get_database
from database.repositories import AssetRepository, OracleRepository
from services.price_oracle_service import price_oracle_service

logger = logging.getLogger(__name__)


class CryptoRatesService:
    """Сервис для получения актуальных курсов криптовалют через оракулы"""
    
    def __init__(self):
        self._rates_cache = {}
        self._cache_expiry = {}
        self.cache_duration = timedelta(minutes=5)
    
    async def get_crypto_rates(self, symbols: List[str] = None) -> Dict[str, float]:
        if symbols is None:
            symbols = ['ETH', 'BTC', 'USDT', 'USDC', 'BNB', 'MATIC', 'TRX']
        
        rates = {}
        
        for symbol in symbols:
            cached_rate = self._get_cached_rate(symbol)
            if cached_rate is not None:
                rates[symbol] = cached_rate
            else:
                fresh_rate = await self._fetch_rate_from_oracle(symbol)
                if fresh_rate is not None:
                    rates[symbol] = fresh_rate
                    self._cache_rate(symbol, fresh_rate)
                else:
                    rates[symbol] = self._get_fallback_rate(symbol)
        
        return rates
    
    async def get_single_rate(self, symbol: str) -> Optional[float]:
        """
        Получает курс одной криптовалюты
        
        Args:
            symbol: Символ криптовалюты (ETH, BTC, etc.)
        
        Returns:
            float: Курс к USD или None если не удалось получить
        """
        rates = await self.get_crypto_rates([symbol])
        return rates.get(symbol)
    
    async def _fetch_rate_from_oracle(self, symbol: str) -> Optional[float]:
        try:
            db = await get_database()
            await db.connect()
            
            try:
                async with db.get_session() as session:
                    asset_repo = AssetRepository(session)
                    oracle_repo = OracleRepository(session)
                    
                    assets = await asset_repo.get_assets_with_oracle()
                    
                    target_asset = None
                    target_oracle = None
                    
                    for asset in assets:
                        if asset.symbol.upper() == symbol.upper() and asset.oracle:
                            target_asset = {
                                'id': asset.id,
                                'symbol': asset.symbol,
                                'name': asset.name,
                                'network': asset.network.name if asset.network else 'unknown'
                            }
                            
                            oracle_full = await oracle_repo.get_oracle_with_relations(asset.oracle.id)
                            if oracle_full:
                                target_oracle = {
                                    'id': oracle_full.id,
                                    'oracle_type': {
                                        'name': oracle_full.oracle_type.name
                                    },
                                    'network': {
                                        'name': oracle_full.network.name
                                    },
                                    'trading_pair': oracle_full.trading_pair,
                                    'contract_address': oracle_full.contract_address,
                                    'api_endpoint': oracle_full.api_endpoint
                                }
                            break
                    
                    if target_asset and target_oracle:
                        price = await price_oracle_service.get_asset_price_with_update(
                            target_asset, target_oracle, db
                        )
                        
                        if price:
                            logger.info(f"Получен курс {symbol}: ${price:.2f} через оракул")
                            return float(price)
                    
                    logger.warning(f"Не найден оракул для {symbol}")
                    return None
                    
            finally:
                await db.disconnect()
                
        except Exception as e:
            logger.error(f"Ошибка получения курса {symbol} из оракула: {e}")
            return None
    
    def _get_cached_rate(self, symbol: str) -> Optional[float]:
        if symbol in self._rates_cache and symbol in self._cache_expiry:
            if datetime.now() < self._cache_expiry[symbol]:
                return self._rates_cache[symbol]
        return None
    
    def _cache_rate(self, symbol: str, rate: float):
        """Сохраняет курс в кеш"""
        self._rates_cache[symbol] = rate
        self._cache_expiry[symbol] = datetime.now() + self.cache_duration
    
    def _get_fallback_rate(self, symbol: str) -> float:
        fallback_rates = {
            'ETH': 2600.0,
            'BTC': 42000.0,
            'USDT': 1.0,
            'USDC': 1.0,
            'BNB': 300.0,
            'MATIC': 0.8,
            'TRX': 0.1,
        }
        
        rate = fallback_rates.get(symbol.upper(), 1.0)
        logger.warning(f"Используется fallback курс для {symbol}: ${rate:.2f}")
        return rate
    
    def clear_cache(self):
        self._rates_cache.clear()
        self._cache_expiry.clear()
        logger.info("Кеш курсов очищен")


crypto_rates_service = CryptoRatesService() 