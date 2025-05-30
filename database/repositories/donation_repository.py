"""
Репозиторий для работы с донатами
"""

from typing import Optional, List
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, func
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta

from .base_repository import BaseRepository
from ..models.donation import Donation


class DonationRepository(BaseRepository[Donation]):
    """Репозиторий для работы с донатами"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Donation, session)
    
    async def get_by_nonce(self, nonce: str) -> Optional[Donation]:
        """Получает донат по nonce"""
        return await self.find_one_by(nonce=nonce)
    
    async def get_by_transaction_hash(self, tx_hash: str) -> Optional[Donation]:
        """Получает донат по хешу транзакции"""
        return await self.find_one_by(transaction_hash=tx_hash)
    
    async def create_donation(
        self,
        streamer_id: int,
        asset_id: int,
        donor_name: str,
        amount: Decimal,
        payment_url: str,
        nonce: str,
        message: Optional[str] = None
    ) -> Donation:
        """Создает новый донат"""
        return await self.create(
            streamer_id=streamer_id,
            asset_id=asset_id,
            donor_name=donor_name,
            amount=amount,
            payment_url=payment_url,
            nonce=nonce,
            message=message
        )
    
    async def get_streamer_donations(
        self, 
        streamer_id: int,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Donation]:
        """Получает донаты стримера"""
        conditions = [Donation.streamer_id == streamer_id]
        if status:
            conditions.append(Donation.status == status)
        
        result = await self.session.execute(
            select(Donation)
            .where(and_(*conditions))
            .order_by(desc(Donation.created_at))
            .limit(limit)
            .options(
                selectinload(Donation.asset),
                selectinload(Donation.streamer)
            )
        )
        return list(result.scalars().all())
    
    async def get_pending_donations(self) -> List[Donation]:
        """Получает все неподтвержденные донаты"""
        return await self.find_by(status='pending')
    
    async def get_confirmed_donations(self, limit: int = 100) -> List[Donation]:
        """Получает подтвержденные донаты"""
        result = await self.session.execute(
            select(Donation)
            .where(Donation.status == 'confirmed')
            .order_by(desc(Donation.confirmed_at))
            .limit(limit)
            .options(
                selectinload(Donation.asset),
                selectinload(Donation.streamer)
            )
        )
        return list(result.scalars().all())
    
    async def update_status(
        self, 
        donation_id: int, 
        status: str,
        transaction_hash: Optional[str] = None
    ) -> Optional[Donation]:
        """Обновляет статус доната"""
        update_data = {'status': status}
        if transaction_hash:
            update_data['transaction_hash'] = transaction_hash
        if status == 'confirmed':
            update_data['confirmed_at'] = datetime.now()
        
        return await self.update(donation_id, **update_data)
    
    async def get_donations_by_asset(
        self, 
        asset_id: int,
        status: Optional[str] = None
    ) -> List[Donation]:
        """Получает донаты по активу"""
        conditions = [Donation.asset_id == asset_id]
        if status:
            conditions.append(Donation.status == status)
        
        result = await self.session.execute(
            select(Donation)
            .where(and_(*conditions))
            .order_by(desc(Donation.created_at))
            .options(
                selectinload(Donation.asset),
                selectinload(Donation.streamer)
            )
        )
        return list(result.scalars().all())
    
    async def get_large_donations(
        self, 
        min_amount: Decimal,
        limit: int = 20
    ) -> List[Donation]:
        """Получает крупные донаты"""
        result = await self.session.execute(
            select(Donation)
            .where(Donation.amount >= min_amount)
            .where(Donation.status == 'confirmed')
            .order_by(desc(Donation.amount))
            .limit(limit)
            .options(
                selectinload(Donation.asset),
                selectinload(Donation.streamer)
            )
        )
        return list(result.scalars().all())
    
    async def get_donation_stats(self, streamer_id: int) -> dict:
        """Получает статистику донатов стримера"""
        # Общая статистика
        total_result = await self.session.execute(
            select(
                func.count(Donation.id).label('total_count'),
                func.coalesce(func.sum(Donation.amount), 0).label('total_amount')
            )
            .where(
                Donation.streamer_id == streamer_id,
                Donation.status == 'confirmed'
            )
        )
        total_stats = total_result.first()
        
        # За последний месяц
        month_ago = datetime.now() - timedelta(days=30)
        month_result = await self.session.execute(
            select(
                func.count(Donation.id).label('month_count'),
                func.coalesce(func.sum(Donation.amount), 0).label('month_amount')
            )
            .where(
                Donation.streamer_id == streamer_id,
                Donation.status == 'confirmed',
                Donation.confirmed_at >= month_ago
            )
        )
        month_stats = month_result.first()
        
        # За последнюю неделю
        week_ago = datetime.now() - timedelta(days=7)
        week_result = await self.session.execute(
            select(
                func.count(Donation.id).label('week_count'),
                func.coalesce(func.sum(Donation.amount), 0).label('week_amount')
            )
            .where(
                Donation.streamer_id == streamer_id,
                Donation.status == 'confirmed',
                Donation.confirmed_at >= week_ago
            )
        )
        week_stats = week_result.first()
        
        return {
            'total': {
                'count': total_stats.total_count,
                'amount': float(total_stats.total_amount)
            },
            'month': {
                'count': month_stats.month_count,
                'amount': float(month_stats.month_amount)
            },
            'week': {
                'count': week_stats.week_count,
                'amount': float(week_stats.week_amount)
            }
        } 