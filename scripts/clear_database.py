#!/usr/bin/env python3
import asyncio
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from database import get_database
from database.models import User, Streamer, Donation
from sqlalchemy import delete, select, func

async def clear_all_data():
    """Очищает все данные из базы данных"""
    print("🗑️ Очистка всех данных из базы данных...")
    print("=" * 50)
    
    try:
        db = await get_database()
        await db.connect()
        
        async with db.get_session() as session:
            
            users_count = await session.scalar(select(func.count(User.id)))
            streamers_count = await session.scalar(select(func.count(Streamer.id)))
            donations_count = await session.scalar(select(func.count(Donation.id)))
            
            print(f"📊 Статистика до очистки:")
            print(f"   👤 Пользователи: {users_count}")
            print(f"   👑 Стримеры: {streamers_count}")
            print(f"   💰 Донаты: {donations_count}")
            print()
            
            if users_count == 0 and streamers_count == 0 and donations_count == 0:
                print("✅ База данных уже пуста!")
                return
            
            print("⚠️  ВНИМАНИЕ: Будут удалены ВСЕ данные!")
            response = input("Вы уверены? Введите 'YES' для подтверждения: ").strip()
            
            if response != 'YES':
                print("❌ Очистка отменена.")
                return
            
            print("\n🗑️ Удаление данных...")
            
            print("   🗑️ Удаление донатов...")
            result = await session.execute(delete(Donation))
            print(f"   ✅ Удалено донатов: {result.rowcount}")
            
            print("   🗑️ Удаление стримеров...")
            result = await session.execute(delete(Streamer))
            print(f"   ✅ Удалено стримеров: {result.rowcount}")
            
            print("   🗑️ Удаление пользователей...")
            result = await session.execute(delete(User))
            print(f"   ✅ Удалено пользователей: {result.rowcount}")
            
            await session.commit()
            
            print("\n✅ Все данные успешно удалены!")
            print("🎉 База данных очищена и готова к использованию.")
        
        await db.disconnect()
        
    except Exception as e:
        print(f"❌ Ошибка при очистке базы данных: {e}")
        import traceback
        traceback.print_exc()

async def clear_specific_table():
    print("🎯 Выборочная очистка базы данных")
    print("=" * 40)
    print("Выберите что очистить:")
    print("1. Только донаты")
    print("2. Только стримеры (и их донаты)")
    print("3. Только пользователи")
    print("4. Всё (полная очистка)")
    print("5. Отмена")
    
    choice = input("\nВаш выбор (1-5): ").strip()
    
    try:
        db = await get_database()
        await db.connect()
        
        async with db.get_session() as session:
            if choice == "1":
                print("🗑️ Удаление всех донатов...")
                result = await session.execute(delete(Donation))
                print(f"✅ Удалено донатов: {result.rowcount}")
                
            elif choice == "2":
                print("🗑️ Удаление донатов...")
                result = await session.execute(delete(Donation))
                print(f"✅ Удалено донатов: {result.rowcount}")
                
                print("🗑️ Удаление стримеров...")
                result = await session.execute(delete(Streamer))
                print(f"✅ Удалено стримеров: {result.rowcount}")
                
            elif choice == "3":
                print("🗑️ Удаление пользователей...")
                result = await session.execute(delete(User))
                print(f"✅ Удалено пользователей: {result.rowcount}")
                
            elif choice == "4":
                await clear_all_data()
                return
                
            elif choice == "5":
                print("❌ Отменено.")
                return
                
            else:
                print("❌ Неверный выбор.")
                return
            
            await session.commit()
            print("✅ Выборочная очистка завершена!")
        
        await db.disconnect()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

async def show_database_stats():
    print("📊 Статистика базы данных")
    print("=" * 30)
    
    try:
        db = await get_database()
        await db.connect()
        
        async with db.get_session() as session:
            users_count = await session.scalar(select(func.count(User.id)))
            streamers_count = await session.scalar(select(func.count(Streamer.id)))
            active_streamers_count = await session.scalar(
                select(func.count(Streamer.id)).where(Streamer.is_active == True)
            )
            donations_count = await session.scalar(select(func.count(Donation.id)))
            
            print(f"👤 Всего пользователей: {users_count}")
            print(f"👑 Всего стримеров: {streamers_count}")
            print(f"✅ Активных стримеров: {active_streamers_count}")
            print(f"❌ Неактивных стримеров: {streamers_count - active_streamers_count}")
            print(f"💰 Всего донатов: {donations_count}")
            
            if donations_count > 0:
                confirmed_donations = await session.scalar(
                    select(func.count(Donation.id)).where(Donation.status == 'confirmed')
                )
                pending_donations = await session.scalar(
                    select(func.count(Donation.id)).where(Donation.status == 'pending')
                )
                print(f"   ✅ Подтвержденных: {confirmed_donations}")
                print(f"   ⏳ Ожидающих: {pending_donations}")
        
        await db.disconnect()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

def main():
    print("🗃️ Утилита управления базой данных")
    print("=" * 40)
    print("1. Показать статистику")
    print("2. Полная очистка (удалить всё)")
    print("3. Выборочная очистка")
    print("4. Выход")
    
    choice = input("\nВаш выбор (1-4): ").strip()
    
    if choice == "1":
        asyncio.run(show_database_stats())
    elif choice == "2":
        asyncio.run(clear_all_data())
    elif choice == "3":
        asyncio.run(clear_specific_table())
    elif choice == "4":
        print("👋 До свидания!")
    else:
        print("❌ Неверный выбор.")

if __name__ == "__main__":
    main() 