import asyncio
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from web3 import Web3
from web3.exceptions import Web3Exception
import json

logger = logging.getLogger(__name__)

class ChainlinkPriceFeedService:
    AGGREGATOR_V3_ABI = json.loads('''[
        {
            "inputs": [],
            "name": "decimals",
            "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "description",
            "outputs": [{"internalType": "string", "name": "", "type": "string"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "latestRoundData",
            "outputs": [
                {"internalType": "uint80", "name": "roundId", "type": "uint80"},
                {"internalType": "int256", "name": "answer", "type": "int256"},
                {"internalType": "uint256", "name": "startedAt", "type": "uint256"},
                {"internalType": "uint256", "name": "updatedAt", "type": "uint256"},
                {"internalType": "uint80", "name": "answeredInRound", "type": "uint80"}
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "version",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        }
    ]''')
    
    PRICE_FEEDS = {
        'ethereum': {
            'mainnet': {
                'BTC/USD': '0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c',
                'ETH/USD': '0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419',
                'USDT/USD': '0x3E7d1eAB13ad0104d2750B8863b489D65364e32D',
                'USDC/USD': '0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6',
            }
        },
        'bsc': {
            'mainnet': {
                'BTC/USD': '0x264990fbd0A4796A3E3d8E37C4d5F87a3aCa5Ebf',
                'ETH/USD': '0x9ef1B8c0E4F7dc8bF5719Ea496883DC6401d5b2e',
                'BNB/USD': '0x0567F2323251f0Aab15c8dFb1967E4e8A7D42aeE',
            }
        }
    }
    RPC_ENDPOINTS = {
        'ethereum': {
            'mainnet': 'https://rpc.ankr.com/eth'
        },
        'bsc': {
            'mainnet': 'https://rpc.ankr.com/bsc',
        }
    }
    
    def __init__(self):
        self.web3_instances = {}
        self.cache = {}
        self.cache_ttl = timedelta(minutes=5)
        
    def _get_web3_instance(self, network: str, environment: str = 'mainnet') -> Optional[Web3]:
        key = f"{network}_{environment}"
        
        if key not in self.web3_instances:
            rpc_url = self.RPC_ENDPOINTS.get(network, {}).get(environment)
            if not rpc_url:
                logger.error(f"RPC endpoint not found for {network}_{environment}")
                return None
                
            try:
                w3 = Web3(Web3.HTTPProvider(rpc_url))
                if not w3.is_connected():
                    logger.error(f"Failed to connect to {rpc_url}")
                    return None
                    
                self.web3_instances[key] = w3
                logger.info(f"Connected to {network}_{environment}: {rpc_url}")
                
            except Exception as e:
                logger.error(f"Error connecting to {rpc_url}: {e}")
                return None
                
        return self.web3_instances[key]
    
    async def get_price_feed_data(
        self, 
        pair: str, 
        network: str = 'ethereum', 
        environment: str = 'mainnet'
    ) -> Optional[Dict]:
        """
        Get price data from Chainlink Price Feed
        
        Args:
            pair: Trading pair (e.g. 'BTC/USD')
            network: Blockchain network
            environment: Environment (mainnet/testnet)
            
        Returns:
            Dict with price data or None on error
        """
        cache_key = f"{network}_{environment}_{pair}"
        
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if datetime.now() - timestamp < self.cache_ttl:
                return cached_data
        
        try:
            w3 = self._get_web3_instance(network, environment)
            if not w3:
                return None
            
            feed_address = self.PRICE_FEEDS.get(network, {}).get(environment, {}).get(pair)
            if not feed_address:
                logger.error(f"Price feed address not found for {pair} on {network}_{environment}")
                return None
            
            contract = w3.eth.contract(address=feed_address, abi=self.AGGREGATOR_V3_ABI)
            
            round_data = contract.functions.latestRoundData().call()
            decimals = contract.functions.decimals().call()
            description = contract.functions.description().call()
            
            round_id, answer, started_at, updated_at, answered_in_round = round_data
            
            price = answer / (10 ** decimals)
            
            result = {
                'pair': pair,
                'price': float(price),
                'decimals': decimals,
                'description': description,
                'round_id': round_id,
                'updated_at': datetime.fromtimestamp(updated_at),
                'network': network,
                'environment': environment,
                'source': 'chainlink'
            }
            
            self.cache[cache_key] = (result, datetime.now())
            
            logger.info(f"Retrieved {pair} price: ${price:.2f} from Chainlink on {network}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting Chainlink price for {pair}: {e}")
            return None
    
    async def get_multiple_prices(
        self, 
        pairs: list, 
        network: str = 'ethereum', 
        environment: str = 'mainnet'
    ) -> Dict[str, Optional[Dict]]:
        """Получить цены для нескольких пар одновременно"""
        
        tasks = [
            self.get_price_feed_data(pair, network, environment) 
            for pair in pairs
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            pair: result if not isinstance(result, Exception) else None
            for pair, result in zip(pairs, results)
        }
    
    async def health_check(self) -> Dict:
        try:
            test_data = await self.get_price_feed_data('ETH/USD', 'ethereum', 'mainnet')
            
            if test_data:
                return {
                    'status': 'healthy',
                    'last_update': test_data['updated_at'].isoformat(),
                    'test_price': test_data['price'],
                    'cache_size': len(self.cache),
                    'connected_networks': list(self.web3_instances.keys())
                }
            else:
                return {
                    'status': 'unhealthy',
                    'error': 'Failed to retrieve test data'
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def get_supported_pairs(self, network: str = None) -> Dict:
        """Получить список поддерживаемых торговых пар"""
        if network:
            return self.PRICE_FEEDS.get(network, {})
        return self.PRICE_FEEDS


chainlink_service = ChainlinkPriceFeedService() 