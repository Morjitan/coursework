"""
Репозиторий для работы со стримерами
"""

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .base_repository import BaseRepository
from ..models.streamer import Streamer


class StreamerRepository(BaseRepository[Streamer]):
    """Репозиторий для работы со стримерами"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Streamer, session)
    
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[Streamer]:
        """Получает стримера по Telegram ID"""
        return await self.find_one_by(telegram_id=telegram_id)
    
    async def get_by_wallet(self, wallet_address: str) -> Optional[Streamer]:
        """Получает стримера по адресу кошелька"""
        return await self.find_one_by(wallet_address=wallet_address)
    
    async def create_streamer(
        self,
        telegram_id: int,
        name: str,
        wallet_address: str,
        username: Optional[str] = None
    ) -> Streamer:
        """Создает нового стримера"""
        return await self.create(
            telegram_id=telegram_id,
            name=name,
            wallet_address=wallet_address,
            username=username
        )
    
    async def get_active_streamers(self) -> List[Streamer]:
        """Получает всех активных стримеров"""
        return await self.find_by(is_active=True)
    
    async def get_streamer_with_donations(self, streamer_id: int) -> Optional[Streamer]:
        """Получает стримера с загруженными донатами"""
        result = await self.session.execute(
            select(Streamer)
            .where(Streamer.id == streamer_id)
            .options(selectinload(Streamer.received_donations))
        )
        return result.scalar_one_or_none()
    
    async def update_wallet(self, telegram_id: int, new_wallet: str) -> Optional[Streamer]:
        """Обновляет адрес кошелька стримера"""
        streamer = await self.get_by_telegram_id(telegram_id)
        if streamer:
            return await self.update(streamer.id, wallet_address=new_wallet)
        return None
    
    async def deactivate_streamer(self, telegram_id: int) -> bool:
        """Деактивирует стримера"""
        streamer = await self.get_by_telegram_id(telegram_id)
        if streamer:
            await self.update(streamer.id, is_active=False)
            return True
        return False 