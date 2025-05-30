#!/usr/bin/env python3
"""
Wrapper скрипт для запуска Telegram бота
"""

import asyncio
import sys
import os

# Добавляем корневую директорию в Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.main import setup_bot, shutdown_handler
import signal


async def main():
    """Главная функция для запуска бота"""
    try:
        bot, dp = await setup_bot()
        
        # Обработчик сигналов для корректного завершения
        def signal_handler():
            print("Получен сигнал завершения...")
            asyncio.create_task(shutdown_handler())
        
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda s, f: signal_handler())
        
        print("🤖 Бот запущен и готов к работе!")
        
        await dp.start_polling(bot)
        
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await shutdown_handler()


if __name__ == "__main__":
    asyncio.run(main()) 