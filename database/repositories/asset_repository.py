from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .base_repository import BaseRepository
from ..models.asset import Asset


class AssetRepository(BaseRepository[Asset]):
    """Репозиторий для работы с активами"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Asset, session)
    
    async def get_by_symbol_and_network(
        self, 
        symbol: str, 
        network_id: int
    ) -> Optional[Asset]:
        """Получает актив по символу и сети"""
        return await self.find_one_by(symbol=symbol, network_id=network_id)
    
    async def get_by_contract_address(
        self, 
        contract_address: str, 
        network_id: int
    ) -> Optional[Asset]:
        """Получает актив по адресу контракта"""
        return await self.find_one_by(
            contract_address=contract_address, 
            network_id=network_id
        )
    
    async def get_assets_by_network(self, network_id: int) -> List[Asset]:
        """Получает все активы определенной сети"""
        return await self.find_by(network_id=network_id, is_active=True)
    
    async def get_active_assets(self) -> List[Asset]:
        """Получает все активные активы"""
        result = await self.session.execute(
            select(Asset)
            .where(Asset.is_active == True)
            .options(selectinload(Asset.network))
        )
        return list(result.scalars().all())
    
    async def get_verified_assets(self) -> List[Asset]:
        """Получает все верифицированные активы"""
        return await self.find_by(is_verified=True, is_active=True)
    
    async def get_stablecoins(self) -> List[Asset]:
        """Получает все стейблкоины"""
        return await self.find_by(is_stablecoin=True, is_active=True)
    
    async def get_asset_with_oracle(self, asset_id: int) -> Optional[Asset]:
        """Получает актив с загруженным оракулом"""
        result = await self.session.execute(
            select(Asset)
            .where(Asset.id == asset_id)
            .options(
                selectinload(Asset.oracle),
                selectinload(Asset.network)
            )
        )
        return result.scalar_one_or_none()
    
    async def get_assets_with_oracle(self) -> List[Asset]:
        """Получает все активы, у которых есть оракул"""
        result = await self.session.execute(
            select(Asset)
            .where(Asset.oracle_id.isnot(None))
            .where(Asset.is_active == True)
            .options(
                selectinload(Asset.oracle),
                selectinload(Asset.network)
            )
        )
        return list(result.scalars().all())
    
    async def link_oracle(self, asset_id: int, oracle_id: int) -> Optional[Asset]:
        """Привязывает оракул к активу"""
        return await self.update(asset_id, oracle_id=oracle_id)
    
    async def unlink_oracle(self, asset_id: int) -> Optional[Asset]:
        """Отвязывает оракул от актива"""
        return await self.update(asset_id, oracle_id=None)
    
    async def search_assets(self, query: str, limit: int = 10) -> List[Asset]:
        """Поиск активов по символу или названию"""
        # Простой поиск - можно улучшить с помощью full-text search
        result = await self.session.execute(
            select(Asset)
            .where(
                (Asset.symbol.ilike(f'%{query}%')) |
                (Asset.name.ilike(f'%{query}%'))
            )
            .where(Asset.is_active == True)
            .limit(limit)
            .options(selectinload(Asset.network))
        )
        return list(result.scalars().all()) 