#!/usr/bin/env python3
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine
from database.models import Base


async def recreate_database():
    """Пересоздает базу данных с новой структурой"""
    print("⚠️  ВНИМАНИЕ! Это удалит все существующие данные в базе данных!")
    print("Вы уверены, что хотите продолжить? (да/нет)")
    
    print("🔄 Пересоздание базы данных...\n")
    
    database_url = os.getenv(
        'DATABASE_URL', 
        'postgresql+asyncpg://postgres:password@localhost:5432/donation_bot'
    )
    
    engine = create_async_engine(
        database_url,
        echo=True,
        pool_pre_ping=True,
    )
    
    try:
        print("1️⃣ Удаление старых таблиц...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            print("   ✅ Старые таблицы удалены")
        
        print("\n2️⃣ Создание новых таблиц...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            print("   ✅ Новые таблицы созданы")
        
        print("\n🎉 База данных успешно пересоздана с новой структурой!")
        print("📋 Созданные таблицы:")
        print("   • users")
        print("   • streamers") 
        print("   • networks")
        print("   • oracle_types")
        print("   • oracles")
        print("   • assets")
        print("   • donations")
        
    except Exception as e:
        print(f"❌ Ошибка при пересоздании БД: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()


async def main():
    await recreate_database()


if __name__ == "__main__":
    asyncio.run(main()) 