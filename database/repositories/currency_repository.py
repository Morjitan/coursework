from typing import Optional, List
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timedelta

from .base_repository import BaseRepository
from ..models.currency import Currency


class CurrencyRepository(BaseRepository[Currency]):
    """Репозиторий для работы с валютами"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Currency, session)
    
    async def get_by_code(self, code: str) -> Optional[Currency]:
        """Получает валюту по коду"""
        return await self.find_one_by(code=code.upper())
    
    async def get_active_currencies(self) -> List[Currency]:
        """Получает список активных валют"""
        return await self.find_by(is_active=True)
    
    async def get_base_currency(self) -> Optional[Currency]:
        """Получает базовую валюту (USD)"""
        return await self.find_one_by(is_base=True)
    
    async def create_currency(
        self, 
        code: str, 
        name: str, 
        rate_to_usd: Decimal,
        symbol: Optional[str] = None,
        is_base: bool = False
    ) -> Currency:
        """Создает новую валюту"""
        return await self.create(
            code=code.upper(),
            name=name,
            symbol=symbol,
            rate_to_usd=rate_to_usd,
            is_base=is_base,
            is_active=True
        )
    
    async def update_rate(self, currency_id: int, new_rate: Decimal) -> Optional[Currency]:
        """Обновляет курс валюты"""
        return await self.update(
            currency_id, 
            rate_to_usd=new_rate,
            last_updated=datetime.now()
        )
    
    async def get_stale_currencies(self, max_age_hours: int = 24) -> List[Currency]:
        """Получает валюты, которые давно не обновлялись"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        result = await self.session.execute(
            select(Currency)
            .where(
                and_(
                    Currency.is_active == True,
                    Currency.last_updated < cutoff_time
                )
            )
        )
        return list(result.scalars().all())
    
    async def convert_amount(
        self, 
        amount: Decimal, 
        from_code: str, 
        to_code: str
    ) -> Optional[Decimal]:
        """Конвертирует сумму между валютами"""
        if from_code.upper() == to_code.upper():
            return amount
        
        from_currency = await self.get_by_code(from_code)
        to_currency = await self.get_by_code(to_code)
        
        if not from_currency or not to_currency:
            return None
        
        return from_currency.convert_to(amount, to_currency)
    
    async def get_exchange_rates(self, base_code: str = "USD") -> dict:
        """Получает курсы всех валют относительно базовой"""
        base_currency = await self.get_by_code(base_code)
        if not base_currency:
            return {}
        
        currencies = await self.get_active_currencies()
        rates = {}
        
        for currency in currencies:
            if currency.code == base_code:
                rates[currency.code] = Decimal('1.0')
            else:
                # Рассчитываем курс относительно базовой валюты
                if base_currency.is_base:
                    rates[currency.code] = currency.rate_to_usd
                else:
                    # Если базовая валюта не USD, пересчитываем
                    rates[currency.code] = currency.rate_to_usd / base_currency.rate_to_usd
        
        return rates 