#!/usr/bin/env python3
"""
Инициализация Oracle системы с новой структурой репозиториев
"""

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import get_database


async def init_networks_and_oracles():
    """Инициализация Networks, OracleTypes, Oracles и Assets"""
    print("🚀 Инициализация Oracle системы...\n")
    
    db = await get_database()
    await db.connect()
    
    try:
        # Получаем репозитории
        users, streamers, networks, oracle_types, oracles, assets, donations = await db.get_repositories()
        
        # 1. Создаем сети
        print("1️⃣ Создание блокчейн-сетей:")
        
        networks_data = [
            {
                'name': 'ethereum',
                'display_name': 'Ethereum Mainnet',
                'chain_id': 1,
                'rpc_endpoint': 'https://eth.llamarpc.com',
                'explorer_url': 'https://etherscan.io',
                'native_symbol': 'ETH',
                'is_mainnet': True,
                'is_evm_compatible': True
            },
            {
                'name': 'bsc',
                'display_name': 'BNB Smart Chain',
                'chain_id': 56,
                'rpc_endpoint': 'https://bsc.nodereal.io',
                'explorer_url': 'https://bscscan.com',
                'native_symbol': 'BNB',
                'is_mainnet': True,
                'is_evm_compatible': True
            },
            {
                'name': 'polygon',
                'display_name': 'Polygon Mainnet',
                'chain_id': 137,
                'rpc_endpoint': 'https://polygon.llamarpc.com',
                'explorer_url': 'https://polygonscan.com',
                'native_symbol': 'MATIC',
                'is_mainnet': True,
                'is_evm_compatible': True
            },
            {
                'name': 'tron',
                'display_name': 'Tron Mainnet',
                'chain_id': None,
                'rpc_endpoint': 'https://api.trongrid.io',
                'explorer_url': 'https://tronscan.org',
                'native_symbol': 'TRX',
                'is_mainnet': True,
                'is_evm_compatible': False
            },
            {
                'name': 'virtual',
                'display_name': 'Virtual Network (API)',
                'chain_id': None,
                'rpc_endpoint': None,
                'explorer_url': None,
                'native_symbol': 'API',
                'is_mainnet': False,
                'is_evm_compatible': False
            }
        ]
        
        network_ids = {}
        for net_data in networks_data:
            network_id = await db.add_network(**net_data)
            network_ids[net_data['name']] = network_id
            print(f"   ✅ {net_data['display_name']} (ID: {network_id})")
        
        # 2. Создаем типы Oracle
        print("\n2️⃣ Создание типов Oracle:")
        
        oracle_types_data = [
            {
                'name': 'chainlink',
                'display_name': 'Chainlink Price Feeds',
                'is_onchain': True,
                'is_decentralized': True,
                'requires_gas': True
            },
            {
                'name': 'coingecko_api',
                'display_name': 'CoinGecko API',
                'is_onchain': False,
                'is_decentralized': False,
                'requires_gas': False
            },
            {
                'name': 'binance_api',
                'display_name': 'Binance API',
                'is_onchain': False,
                'is_decentralized': False,
                'requires_gas': False
            },
            {
                'name': 'coinbase_api',
                'display_name': 'Coinbase API',
                'is_onchain': False,
                'is_decentralized': False,
                'requires_gas': False
            }
        ]
        
        oracle_type_ids = {}
        for ot_data in oracle_types_data:
            ot_id = await db.add_oracle_type(**ot_data)
            oracle_type_ids[ot_data['name']] = ot_id
            print(f"   ✅ {ot_data['display_name']} (ID: {ot_id})")
        
        # 3. Создаем Oracle
        print("\n3️⃣ Создание Oracle:")
        
        oracles_data = [
            # CoinGecko API Oracle (виртуальная сеть)
            {
                'oracle_type_id': oracle_type_ids['coingecko_api'],
                'network_id': network_ids['virtual'],
                'api_endpoint': 'https://api.coingecko.com/api/v3/simple/price',
                'trading_pair': 'USD',
                'priority': 1
            },
            
            # Binance API Oracle (виртуальная сеть)
            {
                'oracle_type_id': oracle_type_ids['binance_api'],
                'network_id': network_ids['virtual'],
                'api_endpoint': 'https://api.binance.com/api/v3/ticker/price',
                'trading_pair': 'USDT',
                'priority': 2
            },
            
            # Chainlink ETH/USD (Ethereum)
            {
                'oracle_type_id': oracle_type_ids['chainlink'],
                'network_id': network_ids['ethereum'],
                'contract_address': '0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419',
                'trading_pair': 'ETH/USD',
                'decimals': 8,
                'priority': 1
            }
        ]
        
        oracle_ids = []
        for i, o_data in enumerate(oracles_data):
            o_id = await db.add_oracle(**o_data)
            oracle_ids.append(o_id)
            oracle_type_name = [k for k, v in oracle_type_ids.items() if v == o_data['oracle_type_id']][0]
            network_name = [k for k, v in network_ids.items() if v == o_data['network_id']][0]
            print(f"   ✅ {oracle_type_name} на {network_name} (ID: {o_id})")
        
        # 4. Создаем активы с привязкой к Oracle
        print("\n4️⃣ Создание активов с Oracle:")
        
        assets_data = [
            # Ethereum активы
            {
                'symbol': 'ETH',
                'name': 'Ethereum',
                'network_id': network_ids['ethereum'],
                'oracle_id': oracle_ids[0],  # CoinGecko API
                'asset_type': 'native',
                'decimals': 18,
                'is_verified': True
            },
            {
                'symbol': 'USDT',
                'name': 'Tether USD',
                'network_id': network_ids['ethereum'],
                'oracle_id': oracle_ids[0],  # CoinGecko API
                'contract_address': '0xdAC17F958D2ee523a2206206994597C13D831ec7',
                'asset_type': 'token',
                'decimals': 6,
                'is_stablecoin': True,
                'is_verified': True
            },
            
            # BSC активы
            {
                'symbol': 'BNB',
                'name': 'BNB',
                'network_id': network_ids['bsc'],
                'oracle_id': oracle_ids[0],  # CoinGecko API
                'asset_type': 'native',
                'decimals': 18,
                'is_verified': True
            },
            {
                'symbol': 'USDT',
                'name': 'Tether USD (BSC)',
                'network_id': network_ids['bsc'],
                'oracle_id': oracle_ids[0],  # CoinGecko API
                'contract_address': '0x55d398326f99059fF775485246999027B3197955',
                'asset_type': 'token',
                'decimals': 18,
                'is_stablecoin': True,
                'is_verified': True
            },
            
            # Polygon активы
            {
                'symbol': 'MATIC',
                'name': 'Polygon',
                'network_id': network_ids['polygon'],
                'oracle_id': oracle_ids[0],  # CoinGecko API
                'asset_type': 'native',
                'decimals': 18,
                'is_verified': True
            },
            {
                'symbol': 'USDT',
                'name': 'Tether USD (Polygon)',
                'network_id': network_ids['polygon'],
                'oracle_id': oracle_ids[0],  # CoinGecko API
                'contract_address': '0xc2132D05D31c914a87C6611C10748AEb04B58e8F',
                'asset_type': 'token',
                'decimals': 6,
                'is_stablecoin': True,
                'is_verified': True
            },
            
            # Tron активы
            {
                'symbol': 'TRX',
                'name': 'Tron',
                'network_id': network_ids['tron'],
                'oracle_id': oracle_ids[0],  # CoinGecko API
                'asset_type': 'native',
                'decimals': 6,
                'is_verified': True
            },
            {
                'symbol': 'USDT',
                'name': 'Tether USD (Tron)',
                'network_id': network_ids['tron'],
                'oracle_id': oracle_ids[0],  # CoinGecko API
                'contract_address': 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t',
                'asset_type': 'token',
                'decimals': 6,
                'is_stablecoin': True,
                'is_verified': True
            }
        ]
        
        for asset_data in assets_data:
            asset_id = await db.add_asset_new(**asset_data)
            print(f"   ✅ {asset_data['symbol']} на {[k for k, v in network_ids.items() if v == asset_data['network_id']][0]} (ID: {asset_id})")
        
        # Commit всех изменений
        if hasattr(db, '_session') and db._session:
            await db._session.commit()
        
        print(f"\n🎉 Инициализация завершена успешно!")
        print(f"📊 Создано:")
        print(f"   • {len(networks_data)} сетей")
        print(f"   • {len(oracle_types_data)} типов Oracle")
        print(f"   • {len(oracles_data)} Oracle")
        print(f"   • {len(assets_data)} активов")
        
    except Exception as e:
        print(f"❌ Ошибка при инициализации: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db.disconnect()


async def main():
    """Главная функция"""
    await init_networks_and_oracles()


if __name__ == "__main__":
    asyncio.run(main()) 