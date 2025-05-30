"""
Бесплатные сервисы для получения цен криптовалют
Альтернатива Chainlink с нулевыми затратами
"""

import asyncio
import logging
import aiohttp
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class CoinGeckoService:
    
    BASE_URL = "https://api.coingecko.com/api/v3"
    
    COIN_MAPPING = {
        'BTC': 'bitcoin',
        'ETH': 'ethereum', 
        'USDT': 'tether',
        'USDC': 'usd-coin',
        'BNB': 'binancecoin',
        'TRX': 'tron',
        'ADA': 'cardano',
        'SOL': 'solana',
        'MATIC': 'matic-network',
    }
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = timedelta(minutes=5)
        
    async def get_price(self, symbol: str, vs_currency: str = 'usd') -> Optional[Dict]:
        cache_key = f"coingecko_{symbol}_{vs_currency}"
        
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if datetime.now() - timestamp < self.cache_ttl:
                return cached_data
        
        coin_id = self.COIN_MAPPING.get(symbol.upper())
        if not coin_id:
            logger.error(f"CoinGecko: Unknown symbol {symbol}")
            return None
            
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/simple/price"
                params = {
                    'ids': coin_id,
                    'vs_currencies': vs_currency,
                    'include_last_updated_at': 'true'
                }
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if coin_id in data:
                            coin_data = data[coin_id]
                            result = {
                                'symbol': symbol.upper(),
                                'price': coin_data[vs_currency],
                                'last_updated': datetime.fromtimestamp(coin_data['last_updated_at']),
                                'source': 'coingecko',
                                'vs_currency': vs_currency.upper()
                            }
                            
                            self.cache[cache_key] = (result, datetime.now())
                            return result
                    
                    logger.error(f"CoinGecko API error: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"CoinGecko error for {symbol}: {e}")
            return None

    async def get_multiple_prices(self, symbols: List[str], vs_currency: str = 'usd') -> Dict[str, Optional[Dict]]:
        """Получить цены для нескольких токенов одним запросом"""
        coin_ids = []
        symbol_to_id = {}
        
        for symbol in symbols:
            coin_id = self.COIN_MAPPING.get(symbol.upper())
            if coin_id:
                coin_ids.append(coin_id)
                symbol_to_id[coin_id] = symbol.upper()
        
        if not coin_ids:
            return {symbol: None for symbol in symbols}
            
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/simple/price"
                params = {
                    'ids': ','.join(coin_ids),
                    'vs_currencies': vs_currency,
                    'include_last_updated_at': 'true'
                }
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        results = {}
                        for coin_id, coin_data in data.items():
                            symbol = symbol_to_id[coin_id]
                            results[symbol] = {
                                'symbol': symbol,
                                'price': coin_data[vs_currency],
                                'last_updated': datetime.fromtimestamp(coin_data['last_updated_at']),
                                'source': 'coingecko',
                                'vs_currency': vs_currency.upper()
                            }
                        
                        for symbol in symbols:
                            if symbol.upper() not in results:
                                results[symbol.upper()] = None
                        
                        return results
                    
        except Exception as e:
            logger.error(f"CoinGecko multiple prices error: {e}")
            
        return {symbol: None for symbol in symbols}


class BinanceService:
    BASE_URL = "https://api.binance.com/api/v3"
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = timedelta(minutes=2)
        
    async def get_price(self, symbol: str, vs_currency: str = 'USDT') -> Optional[Dict]:
        cache_key = f"binance_{symbol}_{vs_currency}"
        
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if datetime.now() - timestamp < self.cache_ttl:
                return cached_data
        
        trading_pair = f"{symbol.upper()}{vs_currency.upper()}"
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/ticker/price"
                params = {'symbol': trading_pair}
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        result = {
                            'symbol': symbol.upper(),
                            'price': float(data['price']),
                            'last_updated': datetime.now(),
                            'source': 'binance',
                            'vs_currency': vs_currency.upper(),
                            'trading_pair': trading_pair
                        }
                        
                        self.cache[cache_key] = (result, datetime.now())
                        return result
                    
                    elif response.status == 400:
                        logger.warning(f"Binance: Trading pair {trading_pair} not found")
                        return None
                    
        except Exception as e:
            logger.error(f"Binance error for {symbol}: {e}")
            return None
    
    async def get_all_prices(self) -> Dict[str, Dict]:
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/ticker/price"
                
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        results = {}
                        for item in data:
                            symbol = item['symbol']
                            if symbol.endswith('USDT') or symbol.endswith('BUSD'):
                                base_symbol = symbol[:-4]
                                vs_currency = symbol[-4:]
                                
                                results[base_symbol] = {
                                    'symbol': base_symbol,
                                    'price': float(item['price']),
                                    'last_updated': datetime.now(),
                                    'source': 'binance',
                                    'vs_currency': vs_currency,
                                    'trading_pair': symbol
                                }
                        
                        return results
                    
        except Exception as e:
            logger.error(f"Binance get_all_prices error: {e}")
            return {}


class CoinbaseService:
    BASE_URL = "https://api.coinbase.com/v2"
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = timedelta(minutes=3)
        
    async def get_price(self, symbol: str, vs_currency: str = 'USD') -> Optional[Dict]:
        """Получить цену с Coinbase"""
        cache_key = f"coinbase_{symbol}_{vs_currency}"
        
        # Проверяем кэш
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if datetime.now() - timestamp < self.cache_ttl:
                return cached_data
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/exchange-rates"
                params = {'currency': symbol.upper()}
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if 'data' in data and 'rates' in data['data']:
                            rates = data['data']['rates']
                            if vs_currency.upper() in rates:
                                rate = float(rates[vs_currency.upper()])
                                price = 1 / rate if rate != 0 else 0
                                
                                result = {
                                    'symbol': symbol.upper(),
                                    'price': price,
                                    'last_updated': datetime.now(),
                                    'source': 'coinbase',
                                    'vs_currency': vs_currency.upper()
                                }
                                
                                self.cache[cache_key] = (result, datetime.now())
                                return result
                    
        except Exception as e:
            logger.error(f"Coinbase error for {symbol}: {e}")
            return None


class AggregatedPriceService:
    def __init__(self):
        self.coingecko = CoinGeckoService()
        self.binance = BinanceService()
        self.coinbase = CoinbaseService()
        
    async def get_best_price(self, symbol: str, vs_currency: str = 'USD') -> Optional[Dict]:
        tasks = [
            self.coingecko.get_price(symbol, vs_currency.lower()),
            self.binance.get_price(symbol, 'USDT' if vs_currency.upper() == 'USD' else vs_currency),
            self.coinbase.get_price(symbol, vs_currency.upper())
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        valid_results = [
            result for result in results 
            if not isinstance(result, Exception) and result is not None
        ]
        
        if not valid_results:
            return None
        
        best_result = max(valid_results, key=lambda x: x['last_updated'])
        
        best_result['alternative_sources'] = len(valid_results) - 1
        best_result['total_sources_checked'] = len(tasks)
        
        return best_result
    
    async def get_price_comparison(self, symbol: str, vs_currency: str = 'USD') -> Dict:
        
        tasks = [
            ('CoinGecko', self.coingecko.get_price(symbol, vs_currency.lower())),
            ('Binance', self.binance.get_price(symbol, 'USDT' if vs_currency.upper() == 'USD' else vs_currency)),
            ('Coinbase', self.coinbase.get_price(symbol, vs_currency.upper()))
        ]
        
        results = {}
        for source_name, task in tasks:
            try:
                result = await task
                results[source_name] = result
            except Exception as e:
                results[source_name] = {'error': str(e)}
        
        valid_prices = [
            result['price'] for result in results.values() 
            if isinstance(result, dict) and 'price' in result
        ]
        
        if valid_prices:
            avg_price = sum(valid_prices) / len(valid_prices)
            min_price = min(valid_prices)
            max_price = max(valid_prices)
            price_spread = ((max_price - min_price) / avg_price) * 100
            
            results['statistics'] = {
                'average_price': avg_price,
                'min_price': min_price,
                'max_price': max_price,
                'price_spread_percent': price_spread,
                'valid_sources': len(valid_prices)
            }
        
        return results


coingecko_service = CoinGeckoService()
binance_service = BinanceService()
coinbase_service = CoinbaseService()
aggregated_price_service = AggregatedPriceService() 