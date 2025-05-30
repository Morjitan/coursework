import logging
from typing import Optional, Dict
from datetime import datetime

from services.chainlink_service import chainlink_service
from services.free_price_services import coingecko_service, binance_service, coinbase_service

logger = logging.getLogger(__name__)

class PriceOracleService:
    async def get_asset_price_usd(self, asset: Dict, oracle: Dict) -> Optional[float]:
        if not oracle:
            logger.warning(f"No oracle configured for asset {asset['symbol']}")
            return None
            
        oracle_type = oracle['oracle_type']['name']
        
        try:
            if oracle_type == 'chainlink':
                return await self._get_chainlink_price(asset, oracle)
            elif oracle_type == 'coingecko_api':
                return await self._get_coingecko_price(asset, oracle)
            elif oracle_type == 'binance_api':
                return await self._get_binance_price(asset, oracle)
            elif oracle_type == 'coinbase_api':
                return await self._get_coinbase_price(asset, oracle)
            else:
                logger.error(f"Unknown oracle type: {oracle_type}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting price for {asset['symbol']} via {oracle_type}: {e}")
            return None
    
    async def _get_chainlink_price(self, asset: Dict, oracle: Dict) -> Optional[float]:
        network_name = oracle['network']['name']
        trading_pair = oracle.get('trading_pair', f"{asset['symbol']}/USD")
        
        price_data = await chainlink_service.get_price_feed_data(
            trading_pair, 
            network_name, 
            'mainnet'
        )
        
        return price_data['price'] if price_data else None
    
    async def _get_coingecko_price(self, asset: Dict, oracle: Dict) -> Optional[float]:
        price_data = await coingecko_service.get_price(asset['symbol'], 'usd')
        return price_data['price'] if price_data else None
    
    async def _get_binance_price(self, asset: Dict, oracle: Dict) -> Optional[float]:
        price_data = await binance_service.get_price(asset['symbol'], 'USDT')
        return price_data['price'] if price_data else None
    
    async def _get_coinbase_price(self, asset: Dict, oracle: Dict) -> Optional[float]:
        price_data = await coinbase_service.get_price(asset['symbol'], 'USD')
        return price_data['price'] if price_data else None
    
    async def update_oracle_price(self, oracle_id: int, price_usd: float, db) -> bool:
        try:
            await db.update_oracle_price(oracle_id, price_usd, datetime.now())
            return True
        except Exception as e:
            logger.error(f"Error updating oracle {oracle_id} price: {e}")
            return False
    
    async def get_asset_price_with_update(self, asset: Dict, oracle: Dict, db) -> Optional[float]:
        price_usd = await self.get_asset_price_usd(asset, oracle)
        
        if price_usd and oracle:
            await self.update_oracle_price(oracle['id'], price_usd, db)
            
        return price_usd

price_oracle_service = PriceOracleService() 