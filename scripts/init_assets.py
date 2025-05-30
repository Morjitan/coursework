#!/usr/bin/env python3
import asyncio
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from database import get_database


async def init_base_assets():
    """Инициализирует базовые активы для всех поддерживаемых сетей"""
    print("Инициализация базовых активов...")
    print("=" * 50)
    
    base_assets = [
        {
            "symbol": "ETH",
            "name": "Ethereum",
            "network": "ethereum",
            "contract_address": None,
            "decimals": 18
        },
        {
            "symbol": "USDT",
            "name": "Tether USD",
            "network": "ethereum",
            "contract_address": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
            "decimals": 6
        },
        {
            "symbol": "USDC",
            "name": "USD Coin",
            "network": "ethereum",
            "contract_address": "0xA0b86a33E6d53e4Ea71654A1CC9A4eC1e0Adc0F3",
            "decimals": 6
        },
        
        {
            "symbol": "BNB",
            "name": "BNB",
            "network": "bsc",
            "contract_address": None,
            "decimals": 18
        },
        {
            "symbol": "USDT",
            "name": "Tether USD",
            "network": "bsc",
            "contract_address": "0x55d398326f99059fF775485246999027B3197955",
            "decimals": 18
        },
        {
            "symbol": "USDC",
            "name": "USD Coin",
            "network": "bsc",
            "contract_address": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
            "decimals": 18
        },

        {
            "symbol": "TRX",
            "name": "Tron",
            "network": "tron",
            "contract_address": None,
            "decimals": 6
        },
        {
            "symbol": "USDT",
            "name": "Tether USD",
            "network": "tron",
            "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
            "decimals": 6
        },
        
        {
            "symbol": "ETH",
            "name": "Ethereum",
            "network": "base",
            "contract_address": None,
            "decimals": 18
        },
        {
            "symbol": "USDC",
            "name": "USD Coin", 
            "network": "base",
            "contract_address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "decimals": 6
        }
    ]
    
    try:
        db = await get_database()
        await db.connect()
        
        created_count = 0
        updated_count = 0
        
        for asset_data in base_assets:
            print(f"⚡ Добавление {asset_data['symbol']} ({asset_data['network'].upper()})...")
            
            existing_asset = await db.get_asset_by_symbol_and_network(
                asset_data['symbol'], 
                asset_data['network']
            )
            
            asset_id = await db.add_asset(
                symbol=asset_data['symbol'],
                name=asset_data['name'],
                network=asset_data['network'],
                contract_address=asset_data['contract_address'],
                decimals=asset_data['decimals'],
                is_active=True
            )
            
            if existing_asset:
                print(f"   ✅ Обновлён актив ID: {asset_id}")
                updated_count += 1
            else:
                print(f"   🆕 Создан новый актив ID: {asset_id}")
                created_count += 1
        
        print(f"\n📊 Результат инициализации:")
        print(f"   🆕 Создано новых активов: {created_count}")
        print(f"   ✅ Обновлено существующих: {updated_count}")
        print(f"   📋 Всего обработано: {len(base_assets)}")
        
        print(f"\n📋 Список всех активов в системе:")
        all_assets = await db.get_all_assets()
        
        current_network = None
        for asset in all_assets:
            if current_network != asset['network']:
                current_network = asset['network']
                print(f"\n🌐 {current_network.upper()}:")
            
            status = "✅" if asset['is_active'] else "❌"
            contract_info = f" (Contract: {asset['contract_address'][:10]}...)" if asset['contract_address'] else " (Native)"
            print(f"   {status} {asset['symbol']} - {asset['name']}{contract_info}")
        
        await db.disconnect()
        
        print(f"\n🎉 Инициализация завершена успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка при инициализации активов: {e}")
        import traceback
        traceback.print_exc()


async def show_supported_networks():
    print("🌐 Поддерживаемые блокчейн-сети")
    print("=" * 40)
    
    networks = {
        "ethereum": {
            "name": "Ethereum Mainnet",
            "native_token": "ETH",
            "description": "Основная сеть Ethereum с поддержкой ERC-20 токенов"
        },
        "bsc": {
            "name": "Binance Smart Chain",
            "native_token": "BNB", 
            "description": "EVM-совместимая сеть Binance с низкими комиссиями"
        },
        "tron": {
            "name": "Tron Network",
            "native_token": "TRX",
            "description": "Высокопроизводительная сеть с поддержкой TRC-20 токенов"
        },
        "base": {
            "name": "Base (Coinbase)",
            "native_token": "ETH",
            "description": "L2 решение на основе Optimism от Coinbase"
        }
    }
    
    for network_id, info in networks.items():
        print(f"\n🔗 {info['name']} ({network_id})")
        print(f"   💰 Нативный токен: {info['native_token']}")
        print(f"   📝 Описание: {info['description']}")


def main():
    print("🏦 Утилита управления активами")
    print("=" * 40)
    print("1. Инициализировать базовые активы")
    print("2. Показать поддерживаемые сети")
    print("3. Выход")
    
    choice = input("\nВаш выбор (1-3): ").strip()
    
    if choice == "1":
        asyncio.run(init_base_assets())
    elif choice == "2":
        asyncio.run(show_supported_networks())
    elif choice == "3":
        print("👋 До свидания!")
    else:
        print("❌ Неверный выбор.")


if __name__ == "__main__":
    main() 