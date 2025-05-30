"""
Репозиторий для работы с пользователями
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from .base_repository import BaseRepository
from ..models.user import User


class UserRepository(BaseRepository[User]):
    """Репозиторий для работы с пользователями"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)
    
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Получает пользователя по telegram_id"""
        return await self.find_one_by(telegram_id=telegram_id)
    
    async def create_user(self, telegram_id: int, username: str = None, 
                         first_name: str = None, last_name: str = None,
                         preferred_currency: str = 'USD') -> User:
        """Создает нового пользователя"""
        return await self.create(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            preferred_currency=preferred_currency
        )
    
    async def update_user_info(self, telegram_id: int, **kwargs) -> Optional[User]:
        """Обновляет информацию о пользователе"""
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            return await self.update(user.id, **kwargs)
        return None
    
    async def set_preferred_currency(self, telegram_id: int, currency_code: str) -> Optional[User]:
        """Устанавливает предпочитаемую валюту для пользователя"""
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            return await self.update(user.id, preferred_currency=currency_code.upper())
        return None
    
    async def get_preferred_currency(self, telegram_id: int) -> str:
        """Получает предпочитаемую валюту пользователя"""
        user = await self.get_by_telegram_id(telegram_id)
        return user.preferred_currency if user else 'USD'
    
    async def get_or_create_user(
        self, 
        telegram_id: int, 
        username: str = None,
        first_name: str = None, 
        last_name: str = None
    ) -> User:
        """Получает пользователя или создает нового, если не существует"""
        user = await self.get_by_telegram_id(telegram_id)
        
        if user:
            # Обновляем информацию если есть изменения
            update_data = {}
            if username and user.username != username:
                update_data['username'] = username
            if first_name and user.first_name != first_name:
                update_data['first_name'] = first_name
            if last_name and user.last_name != last_name:
                update_data['last_name'] = last_name
            
            if update_data:
                await self.update(user.id, **update_data)
                # Обновляем локальный объект
                for key, value in update_data.items():
                    setattr(user, key, value)
            
            return user
        else:
            return await self.create_user(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name
            ) 