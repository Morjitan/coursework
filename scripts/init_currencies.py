#!/usr/bin/env python3
import asyncio
import sys
import os
from decimal import Decimal
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from database import get_database
from database.repositories import CurrencyRepository
from services.currency_service import CurrencyService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def init_currencies():
    db = await get_database()
    await db.connect()
    
    try:
        logger.info("🔄 Получение актуальных курсов валют...")
        async with CurrencyService() as currency_service:
            rates = await currency_service.get_combined_rates()
        
        if not rates:
            logger.error("❌ Не удалось получить курсы валют")
            return False

        async with db.get_session() as session:
            currency_repo = CurrencyRepository(session)
            
            currencies_to_add = [
                {
                    'code': 'USD',
                    'name': 'US Dollar',
                    'symbol': '$',
                    'rate_to_usd': Decimal('1.0'),
                    'is_base': True
                },
                {
                    'code': 'RUB',
                    'name': 'Russian Ruble',
                    'symbol': '₽',
                    'rate_to_usd': rates.get('RUB', Decimal('0.011')),
                    'is_base': False
                }
            ]
            
            created_count = 0
            updated_count = 0
            
            for currency_data in currencies_to_add:
                code = currency_data['code']
                
                existing = await currency_repo.get_by_code(code)
                
                if existing:
                    updated = await currency_repo.update_rate(
                        existing.id, 
                        currency_data['rate_to_usd']
                    )
                    if updated:
                        logger.info(f"✅ Обновлен курс {code}: {currency_data['rate_to_usd']}")
                        updated_count += 1
                    else:
                        logger.warning(f"⚠️  Не удалось обновить курс {code}")
                else:
                    new_currency = await currency_repo.create_currency(
                        code=currency_data['code'],
                        name=currency_data['name'],
                        rate_to_usd=currency_data['rate_to_usd'],
                        symbol=currency_data['symbol'],
                        is_base=currency_data['is_base']
                    )
                    logger.info(f"✅ Создана валюта {code}: {currency_data['name']} ({currency_data['rate_to_usd']})")
                    created_count += 1
            
            await session.commit()
            
            logger.info(f"🎉 Инициализация завершена:")
            logger.info(f"   - Создано валют: {created_count}")
            logger.info(f"   - Обновлено курсов: {updated_count}")
            
            currencies = await currency_repo.get_active_currencies()
            logger.info("📋 Активные валюты в базе:")
            for currency in currencies:
                base_marker = " (базовая)" if currency.is_base else ""
                logger.info(f"   - {currency.code}: {currency.display_name} = {currency.rate_to_usd} USD{base_marker}")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации валют: {e}")
        return False
    finally:
        await db.disconnect()


async def test_currency_conversion():
    """Тестирует конвертацию валют"""
    
    db = await get_database()
    await db.connect()
    
    try:
        async with db.get_session() as session:
            currency_repo = CurrencyRepository(session)
            
            usd_amount = Decimal('100.0')
            converted = await currency_repo.convert_amount(usd_amount, 'USD', 'RUB')
            
            if converted:
                logger.info(f"💱 Конвертация: {usd_amount} USD = {converted:.2f} RUB")
            else:
                logger.error("❌ Не удалось выполнить конвертацию")
            
            rates = await currency_repo.get_exchange_rates('USD')
            logger.info("📊 Курсы относительно USD:")
            for code, rate in rates.items():
                logger.info(f"   - 1 USD = {rate} {code}")
                
    except Exception as e:
        logger.error(f"❌ Ошибка тестирования: {e}")
    finally:
        await db.disconnect()


async def main():
    logger.info("🚀 Запуск инициализации валют...")
    
    success = await init_currencies()
    
    if success:
        logger.info("🧪 Тестирование конвертации...")
        await test_currency_conversion()
        logger.info("✅ Все готово!")
    else:
        logger.error("❌ Инициализация не удалась")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 