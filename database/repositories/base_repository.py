from typing import Generic, TypeVar, Type, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from ..models.base import Base

T = TypeVar('T', bound=Base)


class BaseRepository(Generic[T]):
    """Базовый репозиторий для работы с моделями"""
    
    def __init__(self, model: Type[T], session: AsyncSession):
        self.model = model
        self.session = session
    
    async def create(self, **kwargs) -> T:
        """Создает новую запись"""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance
    
    async def get_by_id(self, id: int) -> Optional[T]:
        """Получает запись по ID"""
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """Получает все записи с пагинацией"""
        result = await self.session.execute(
            select(self.model).limit(limit).offset(offset)
        )
        return list(result.scalars().all())
    
    async def update(self, id: int, **kwargs) -> Optional[T]:
        """Обновляет запись по ID"""
        await self.session.execute(
            update(self.model).where(self.model.id == id).values(**kwargs)
        )
        return await self.get_by_id(id)
    
    async def delete(self, id: int) -> bool:
        """Удаляет запись по ID"""
        result = await self.session.execute(
            delete(self.model).where(self.model.id == id)
        )
        return result.rowcount > 0
    
    async def exists(self, **kwargs) -> bool:
        """Проверяет существование записи по условиям"""
        query = select(self.model.id)
        for key, value in kwargs.items():
            query = query.where(getattr(self.model, key) == value)
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None
    
    async def find_by(self, **kwargs) -> List[T]:
        """Находит записи по условиям"""
        query = select(self.model)
        for key, value in kwargs.items():
            query = query.where(getattr(self.model, key) == value)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def find_one_by(self, **kwargs) -> Optional[T]:
        """Находит одну запись по условиям"""
        query = select(self.model)
        for key, value in kwargs.items():
            query = query.where(getattr(self.model, key) == value)
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def count(self, **kwargs) -> int:
        """Подсчитывает количество записей по условиям"""
        query = select(self.model.id)
        for key, value in kwargs.items():
            query = query.where(getattr(self.model, key) == value)
        
        result = await self.session.execute(query)
        return len(list(result.scalars().all())) 