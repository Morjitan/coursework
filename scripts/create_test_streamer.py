#!/usr/bin/env python3
import asyncio
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from database import get_database

async def create_test_streamer():
    """Создает тестового стримера"""
    
    db = await get_database()
    await db.connect()
    
    streamers = await db.get_all_streamers()
    
    if streamers:
        print(f"✅ В базе уже есть {len(streamers)} стример(ов):")
        for streamer in streamers:
            print(f"  • ID: {streamer['id']}, Name: {streamer['name']}, Telegram ID: {streamer['telegram_id']}")
        return
    
    test_telegram_id = 123456789
    
    try:
        streamer_id = await db.add_streamer(
            telegram_id=test_telegram_id,
            username="test_streamer",
            name="Тестовый Стример",
            wallet_address="0x742d35Cc6634C0532925a3b8D3fA8afe1574fc4A"
        )
        
        print(f"✅ Тестовый стример создан:")
        print(f"  • ID: {streamer_id}")
        print(f"  • Name: Тестовый Стример")
        print(f"  • Telegram ID: {test_telegram_id}")
        print(f"  • Wallet: 0x742d35Cc6634C0532925a3b8D3fA8afe1574fc4A")
        
    except Exception as e:
        print(f"❌ Ошибка создания стримера: {e}")
    
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(create_test_streamer()) 