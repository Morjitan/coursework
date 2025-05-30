"""
Репозиторий для работы с Oracle системой
"""

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .base_repository import BaseRepository
from ..models.oracle import Network, OracleType, Oracle


class NetworkRepository(BaseRepository[Network]):
    """Репозиторий для работы с блокчейн-сетями"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Network, session)
    
    async def get_by_name(self, name: str) -> Optional[Network]:
        """Получает сеть по имени"""
        return await self.find_one_by(name=name)
    
    async def get_by_chain_id(self, chain_id: int) -> Optional[Network]:
        """Получает сеть по chain_id"""
        return await self.find_one_by(chain_id=chain_id)
    
    async def get_active_networks(self) -> List[Network]:
        """Получает все активные сети"""
        return await self.find_by(is_active=True)
    
    async def get_evm_networks(self) -> List[Network]:
        """Получает EVM-совместимые сети"""
        return await self.find_by(is_evm_compatible=True, is_active=True)


class OracleTypeRepository(BaseRepository[OracleType]):
    """Репозиторий для работы с типами оракулов"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(OracleType, session)
    
    async def get_by_name(self, name: str) -> Optional[OracleType]:
        """Получает тип оракула по имени"""
        return await self.find_one_by(name=name)
    
    async def get_active_types(self) -> List[OracleType]:
        """Получает все активные типы оракулов"""
        return await self.find_by(is_active=True)
    
    async def get_onchain_types(self) -> List[OracleType]:
        """Получает типы on-chain оракулов"""
        return await self.find_by(is_onchain=True, is_active=True)
    
    async def get_api_types(self) -> List[OracleType]:
        """Получает типы API оракулов"""
        return await self.find_by(is_onchain=False, is_active=True)


class OracleRepository(BaseRepository[Oracle]):
    """Репозиторий для работы с оракулами"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Oracle, session)
    
    async def get_by_network_and_type(
        self, 
        network_id: int, 
        oracle_type_id: int
    ) -> List[Oracle]:
        """Получает оракулы по сети и типу"""
        return await self.find_by(
            network_id=network_id, 
            oracle_type_id=oracle_type_id,
            is_active=True
        )
    
    async def get_oracle_with_relations(self, oracle_id: int) -> Optional[Oracle]:
        """Получает оракул с загруженными связями"""
        result = await self.session.execute(
            select(Oracle)
            .where(Oracle.id == oracle_id)
            .options(
                selectinload(Oracle.oracle_type),
                selectinload(Oracle.network),
                selectinload(Oracle.assets)
            )
        )
        return result.scalar_one_or_none()
    
    async def get_active_oracles(self) -> List[Oracle]:
        """Получает все активные оракулы"""
        return await self.find_by(is_active=True)
    
    async def get_oracles_by_trading_pair(self, trading_pair: str) -> List[Oracle]:
        """Получает оракулы по торговой паре"""
        return await self.find_by(trading_pair=trading_pair, is_active=True)
    
    async def update_price(
        self, 
        oracle_id: int, 
        price_usd: float,
        last_update: Optional[str] = None
    ) -> Optional[Oracle]:
        """Обновляет цену в оракуле"""
        update_data = {'last_price_usd': price_usd}
        if last_update:
            update_data['last_update'] = last_update
        
        return await self.update(oracle_id, **update_data) 