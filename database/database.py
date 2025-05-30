import os
from typing import Optional
from decimal import Decimal
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

from .models import Base
from .repositories import (
    UserRepository,
    StreamerRepository,
    NetworkRepository,
    OracleTypeRepository,
    OracleRepository,
    AssetRepository,
    DonationRepository,
    CurrencyRepository
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Database:
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.getenv(
            'DATABASE_URL', 
            'postgresql+asyncpg://postgres:password@localhost:5432/donation_bot'
        )
        self.engine = None
        self.session_factory = None

        self._session = None

    async def connect(self) -> None:
        """Создаёт подключение к базе данных"""
        self.engine = create_async_engine(
            self.database_url,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def disconnect(self) -> None:
        """Закрывает подключение к базе данных"""
        if self._session:
            await self._session.close()
            self._session = None
        
        if self.engine:
            await self.engine.dispose()

    def get_session(self) -> AsyncSession:
        """Возвращает новую сессию для работы с БД"""
        if not self.session_factory:
            raise RuntimeError("Database не подключена. Вызовите connect() сначала.")
        return self.session_factory()

    async def get_repositories(self) -> tuple:
        """
        Возвращает все репозитории для текущей сессии
        
        Returns:
            tuple: (users, streamers, networks, oracle_types, oracles, assets, donations, currencies)
        """
        if not self._session:
            self._session = self.get_session()
        
        return (
            UserRepository(self._session),
            StreamerRepository(self._session),
            NetworkRepository(self._session),
            OracleTypeRepository(self._session),
            OracleRepository(self._session),
            AssetRepository(self._session),
            DonationRepository(self._session),
            CurrencyRepository(self._session)
        )

    async def add_user(self, telegram_id: int, **kwargs) -> int:
        """Добавляет пользователя - обратная совместимость"""
        async with self.get_session() as session:
            repo = UserRepository(session)
            existing = await repo.get_by_telegram_id(telegram_id)
            
            if existing:
                if kwargs:
                    updated = await repo.update_user_info(telegram_id, **kwargs)
                    await session.commit()
                    return updated.id if updated else existing.id
                else:
                    return existing.id
            else:
                user = await repo.create_user(telegram_id, **kwargs)
                await session.commit()
                return user.id

    async def add_streamer(self, telegram_id: int, wallet_address: str, name: str, **kwargs) -> int:
        """Добавляет стримера - обратная совместимость"""
        async with self.get_session() as session:
            repo = StreamerRepository(session)
            existing = await repo.get_by_telegram_id(telegram_id)
            
            if existing:
                updated = await repo.update(existing.id, 
                    wallet_address=wallet_address, 
                    name=name, 
                    is_active=True,
                    **kwargs
                )
                await session.commit()
                return updated.id
            else:
                streamer = await repo.create_streamer(telegram_id, name, wallet_address, **kwargs)
                await session.commit()
                return streamer.id

    async def get_streamer(self, telegram_id: int, include_inactive: bool = False) -> Optional[dict]:
        """Получает стримера - обратная совместимость"""
        async with self.get_session() as session:
            repo = StreamerRepository(session)
            streamer = await repo.get_by_telegram_id(telegram_id)
            
            if streamer and (include_inactive or streamer.is_active):
                return {
                    'id': streamer.id,
                    'telegram_id': streamer.telegram_id,
                    'username': streamer.username,
                    'wallet_address': streamer.wallet_address,
                    'name': streamer.name,
                    'is_active': streamer.is_active,
                    'created_at': streamer.created_at
                }
            return None

    async def get_all_assets(self) -> list:
        async with self.get_session() as session:
            repo = AssetRepository(session)
            assets = await repo.get_active_assets()
            
            result = []
            for asset in assets:
                result.append({
                    'id': asset.id,
                    'symbol': asset.symbol,
                    'name': asset.name,
                    'network': asset.network.name if asset.network else 'unknown',
                    'contract_address': asset.contract_address,
                    'decimals': asset.decimals,
                    'is_active': asset.is_active,
                    'created_at': asset.created_at,
                    'full_name': f"{asset.name} ({asset.symbol})",
                    'oracle_id': asset.oracle_id
                })
            return result

    async def create_donation(self, streamer_id: int, asset_id: int, donor_name: str, 
                            amount: float, message: str = "", payment_url: str = "", 
                            nonce: str = "") -> int:
        """Создает донат - обратная совместимость"""
        async with self.get_session() as session:
            repo = DonationRepository(session)
            donation = await repo.create_donation(
                streamer_id=streamer_id,
                asset_id=asset_id,
                donor_name=donor_name,
                amount=amount,
                message=message,
                payment_url=payment_url,
                nonce=nonce
            )
            await session.commit()
            return donation.id

    async def get_donation_by_nonce(self, nonce: str) -> Optional[dict]:
        """Получает донат по nonce - обратная совместимость"""
        async with self.get_session() as session:
            from sqlalchemy import select
            from .models.donation import Donation
            from .models.streamer import Streamer
            from .models.asset import Asset
            from .models.oracle import Network
            
            result = await session.execute(
                select(
                    Donation,
                    Streamer.name.label('streamer_name'),
                    Streamer.wallet_address,
                    Asset.symbol.label('asset_symbol'),
                    Asset.name.label('asset_name'),
                    Asset.decimals.label('asset_decimals'),
                    Network.name.label('network_name')
                )
                .join(Streamer, Donation.streamer_id == Streamer.id)
                .join(Asset, Donation.asset_id == Asset.id)
                .join(Network, Asset.network_id == Network.id)
                .where(Donation.nonce == nonce)
            )
            row = result.first()
            
            if row:
                donation = row[0]
                return {
                    'id': donation.id,
                    'streamer_id': donation.streamer_id,
                    'asset_id': donation.asset_id,
                    'donor_name': donation.donor_name,
                    'amount': donation.amount,
                    'message': donation.message,
                    'payment_url': donation.payment_url,
                    'transaction_hash': donation.transaction_hash,
                    'nonce': donation.nonce,
                    'status': donation.status,
                    'created_at': donation.created_at,
                    'confirmed_at': donation.confirmed_at,
                    'streamer_name': row[1],
                    'wallet_address': row[2],
                    'asset_symbol': row[3],
                    'asset_name': row[4],
                    'asset_network': row[6],  # network_name
                    'asset_decimals': row[5]
                }
            return None

    async def add_network(self, name: str, display_name: str, **kwargs) -> int:
        """Добавляет новую сеть"""
        async with self.get_session() as session:
            repo = NetworkRepository(session)
            existing = await repo.get_by_name(name)
            
            if existing:
                updated = await repo.update(existing.id, display_name=display_name, **kwargs)
                await session.commit()
                return updated.id
            else:
                network = await repo.create(name=name, display_name=display_name, **kwargs)
                await session.commit()
                return network.id

    async def add_oracle_type(self, name: str, display_name: str, **kwargs) -> int:
        """Добавляет новый тип оракула"""
        async with self.get_session() as session:
            repo = OracleTypeRepository(session)
            existing = await repo.get_by_name(name)
            
            if existing:
                updated = await repo.update(existing.id, display_name=display_name, **kwargs)
                await session.commit()
                return updated.id
            else:
                oracle_type = await repo.create(name=name, display_name=display_name, **kwargs)
                await session.commit()
                return oracle_type.id

    async def add_oracle(self, oracle_type_id: int, network_id: int, **kwargs) -> int:
        """Добавляет новый оракул"""
        async with self.get_session() as session:
            repo = OracleRepository(session)
            oracle = await repo.create(
                oracle_type_id=oracle_type_id,
                network_id=network_id,
                **kwargs
            )
            await session.commit()
            return oracle.id

    async def add_asset_new(self, symbol: str, name: str, network_id: int, **kwargs) -> int:
        """Добавляет новый актив с поддержкой Oracle"""
        async with self.get_session() as session:
            repo = AssetRepository(session)
            existing = await repo.get_by_symbol_and_network(symbol, network_id)
            
            if existing:
                updated = await repo.update(existing.id, name=name, **kwargs)
                await session.commit()
                return updated.id
            else:
                asset = await repo.create(
                    symbol=symbol,
                    name=name,
                    network_id=network_id,
                    **kwargs
                )
                await session.commit()
                return asset.id

    async def get_received_donations_stats(self, streamer_id: int) -> dict:
        """Получает статистику полученных донатов для стримера"""
        async with self.get_session() as session:
            repo = DonationRepository(session)
            return await repo.get_donation_stats(streamer_id)

    async def get_sent_donations_by_user(self, donor_name: str, limit: int = 5, offset: int = 0) -> dict:
        """Получает отправленные донаты пользователя с пагинацией"""
        async with self.get_session() as session:
            from sqlalchemy import select, func
            from .models.donation import Donation
            from .models.streamer import Streamer
            from .models.asset import Asset
            from .models.oracle import Network
            
            # Получаем донаты с пагинацией
            donations_result = await session.execute(
                select(
                    Donation, 
                    Streamer.name.label('streamer_name'),
                    Asset.symbol,
                    Asset.name.label('asset_name'),
                    Network.name.label('network_name')
                )
                .join(Streamer, Donation.streamer_id == Streamer.id)
                .join(Asset, Donation.asset_id == Asset.id)
                .join(Network, Asset.network_id == Network.id)
                .where(Donation.donor_name == donor_name)
                .order_by(Donation.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            donations_data = donations_result.all()
            
            # Получаем общее количество донатов
            total_result = await session.execute(
                select(func.count(Donation.id))
                .where(Donation.donor_name == donor_name)
            )
            total_count = total_result.scalar()
            
            # Получаем общую потраченную сумму
            total_amount_result = await session.execute(
                select(func.coalesce(func.sum(Donation.amount), 0))
                .where(
                    Donation.donor_name == donor_name,
                    Donation.status.in_(['confirmed', 'pending'])
                )
            )
            total_amount = total_amount_result.scalar()
            
            donations = []
            for row in donations_data:
                donation = row[0]
                donations.append({
                    'id': donation.id,
                    'streamer_name': row[1],
                    'amount': donation.amount,
                    'asset_symbol': row[2],
                    'asset_name': row[3],
                    'asset_network': row[4],  # network_name из JOIN
                    'message': donation.message,
                    'status': donation.status,
                    'created_at': donation.created_at,
                    'confirmed_at': donation.confirmed_at
                })
            
            return {
                'donations': donations,
                'total_count': total_count,
                'total_amount_usd': float(total_amount),
                'has_more': (offset + limit) < total_count
            }

    async def update_donation_status(self, donation_id: int, status: str, transaction_hash: Optional[str] = None) -> None:
        """Обновляет статус доната"""
        async with self.get_session() as session:
            repo = DonationRepository(session)
            await repo.update_status(donation_id, status, transaction_hash)
            await session.commit()

    async def get_recent_donations(self, streamer_id: int, limit: int = 10) -> list:
        """Получает последние донаты для стримера"""
        async with self.get_session() as session:
            from sqlalchemy import select
            from .models.donation import Donation
            from .models.asset import Asset
            from .models.oracle import Network
            
            # Используем прямой JOIN запрос вместо lazy loading
            result = await session.execute(
                select(
                    Donation,
                    Asset.symbol.label('asset_symbol'),
                    Asset.name.label('asset_name'),
                    Network.name.label('network_name')
                )
                .join(Asset, Donation.asset_id == Asset.id)
                .join(Network, Asset.network_id == Network.id)
                .where(Donation.streamer_id == streamer_id)
                .where(Donation.status == 'confirmed')
                .order_by(Donation.created_at.desc())
                .limit(limit)
            )
            
            donations_data = result.all()
            
            result_list = []
            for row in donations_data:
                donation = row[0]
                result_list.append({
                    'id': donation.id,
                    'streamer_id': donation.streamer_id,
                    'asset_id': donation.asset_id,
                    'donor_name': donation.donor_name,
                    'amount': donation.amount,
                    'message': donation.message,
                    'payment_url': donation.payment_url,
                    'transaction_hash': donation.transaction_hash,
                    'nonce': donation.nonce,
                    'status': donation.status,
                    'created_at': donation.created_at,
                    'confirmed_at': donation.confirmed_at,
                    'asset_symbol': row[1],  # asset_symbol
                    'asset_name': row[2],    # asset_name
                    'asset_network': row[3]  # network_name
                })
            return result_list

    async def remove_streamer(self, telegram_id: int) -> bool:
        """Удаляет стримера (деактивирует)"""
        async with self.get_session() as session:
            repo = StreamerRepository(session)
            result = await repo.deactivate_streamer(telegram_id)
            await session.commit()
            return result

    async def get_user_by_name_pattern(self, telegram_id: int) -> str:
        """Получает имя пользователя для поиска донатов"""
        async with self.get_session() as session:
            repo = UserRepository(session)
            user = await repo.get_by_telegram_id(telegram_id)
            
            if not user:
                return str(telegram_id)
            
            # Формируем паттерн имени для поиска
            if user.username:
                return f"@{user.username}"
            elif user.first_name:
                name_parts = [user.first_name]
                if user.last_name:
                    name_parts.append(user.last_name)
                return ' '.join(name_parts)
            else:
                return str(telegram_id)

    async def get_user(self, telegram_id: int) -> Optional[dict]:
        """Получает информацию о пользователе"""
        async with self.get_session() as session:
            repo = UserRepository(session)
            user = await repo.get_by_telegram_id(telegram_id)
            
            if user:
                return {
                    'id': user.id,
                    'telegram_id': user.telegram_id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'created_at': user.created_at
                }
            return None

    async def get_all_streamers(self) -> list:
        """Получает список всех активных стримеров"""
        async with self.get_session() as session:
            repo = StreamerRepository(session)
            streamers = await repo.get_active_streamers()
            
            result = []
            for streamer in streamers:
                result.append({
                    'id': streamer.id,
                    'telegram_id': streamer.telegram_id,
                    'username': streamer.username,
                    'wallet_address': streamer.wallet_address,
                    'name': streamer.name,
                    'is_active': streamer.is_active,
                    'created_at': streamer.created_at
                })
            return result

    async def get_streamer_by_id(self, streamer_id: int) -> Optional[dict]:
        """Получает информацию о стримере по ID"""
        async with self.get_session() as session:
            repo = StreamerRepository(session)
            streamer = await repo.get_by_id(streamer_id)
            
            if streamer:
                return {
                    'id': streamer.id,
                    'telegram_id': streamer.telegram_id,
                    'username': streamer.username,
                    'wallet_address': streamer.wallet_address,
                    'name': streamer.name,
                    'is_active': streamer.is_active,
                    'created_at': streamer.created_at
                }
            return None

    async def get_asset_by_id(self, asset_id: int) -> Optional[dict]:
        """Получает информацию об активе по ID"""
        async with self.get_session() as session:
            repo = AssetRepository(session)
            asset = await repo.get_asset_with_oracle(asset_id)
            
            if asset:
                return {
                    'id': asset.id,
                    'symbol': asset.symbol,
                    'name': asset.name,
                    'network': asset.network.name if asset.network else 'unknown',
                    'contract_address': asset.contract_address,
                    'decimals': asset.decimals,
                    'is_active': asset.is_active,
                    'created_at': asset.created_at,
                    'full_name': f"{asset.name} ({asset.symbol})"
                }
            return None

    async def get_donation_by_payment_url(self, payment_url: str) -> Optional[dict]:
        """Получает донат по payment_url"""
        async with self.get_session() as session:
            from sqlalchemy import select
            from .models.donation import Donation
            from .models.streamer import Streamer
            from .models.asset import Asset
            
            result = await session.execute(
                select(
                    Donation, 
                    Streamer.name.label('streamer_name'),
                    Streamer.wallet_address,
                    Asset.symbol,
                    Asset.name.label('asset_name'),
                    Asset.decimals
                )
                .join(Streamer, Donation.streamer_id == Streamer.id)
                .join(Asset, Donation.asset_id == Asset.id)
                .where(Donation.payment_url == payment_url)
            )
            row = result.first()
            
            if row:
                donation = row[0]
                return {
                    'id': donation.id,
                    'streamer_id': donation.streamer_id,
                    'asset_id': donation.asset_id,
                    'donor_name': donation.donor_name,
                    'amount': donation.amount,
                    'message': donation.message,
                    'payment_url': donation.payment_url,
                    'transaction_hash': donation.transaction_hash,
                    'nonce': donation.nonce,
                    'status': donation.status,
                    'created_at': donation.created_at,
                    'confirmed_at': donation.confirmed_at,
                    'streamer_name': row[1],
                    'wallet_address': row[2],
                    'asset_symbol': row[3],
                    'asset_name': row[4],
                    'asset_decimals': row[5]
                }
            return None

    # Новые методы для работы с валютами
    async def add_currency(self, code: str, name: str, rate_to_usd: Decimal, symbol: str = None, is_base: bool = False) -> int:
        """Добавляет валюту в базу данных"""
        async with self.get_session() as session:
            repo = CurrencyRepository(session)
            existing = await repo.get_by_code(code)
            
            if existing:
                updated = await repo.update_rate(existing.id, rate_to_usd)
                await session.commit()
                return updated.id if updated else existing.id
            else:
                currency = await repo.create_currency(code, name, rate_to_usd, symbol, is_base)
                await session.commit()
                return currency.id

    async def get_currency_by_code(self, code: str) -> Optional[dict]:
        """Получает валюту по коду"""
        async with self.get_session() as session:
            repo = CurrencyRepository(session)
            currency = await repo.get_by_code(code)
            
            if currency:
                return {
                    'id': currency.id,
                    'code': currency.code,
                    'name': currency.name,
                    'symbol': currency.symbol,
                    'rate_to_usd': currency.rate_to_usd,
                    'is_base': currency.is_base,
                    'is_active': currency.is_active,
                    'last_updated': currency.last_updated,
                    'display_name': currency.display_name
                }
            return None

    async def get_all_currencies(self) -> list:
        """Получает все активные валюты"""
        async with self.get_session() as session:
            repo = CurrencyRepository(session)
            currencies = await repo.get_active_currencies()
            
            result = []
            for currency in currencies:
                result.append({
                    'id': currency.id,
                    'code': currency.code,
                    'name': currency.name,
                    'symbol': currency.symbol,
                    'rate_to_usd': currency.rate_to_usd,
                    'is_base': currency.is_base,
                    'is_active': currency.is_active,
                    'last_updated': currency.last_updated,
                    'display_name': currency.display_name
                })
            return result

    async def convert_currency(self, amount: Decimal, from_code: str, to_code: str) -> Optional[Decimal]:
        """Конвертирует сумму между валютами"""
        async with self.get_session() as session:
            repo = CurrencyRepository(session)
            return await repo.convert_amount(amount, from_code, to_code)

    async def update_currency_rate(self, currency_id: int, new_rate: Decimal) -> bool:
        """Обновляет курс валюты"""
        async with self.get_session() as session:
            repo = CurrencyRepository(session)
            updated = await repo.update_rate(currency_id, new_rate)
            await session.commit()
            return updated is not None

    async def get_exchange_rates(self, base_code: str = "USD") -> dict:
        """Получает курсы всех валют относительно базовой"""
        async with self.get_session() as session:
            repo = CurrencyRepository(session)
            return await repo.get_exchange_rates(base_code)

    async def update_donation_payment_info(self, donation_id: int, payment_url: str, nonce: str) -> bool:
        """Обновляет информацию о платеже для доната"""
        try:
            async with self.get_session() as session:
                result = await session.execute(
                    text("""
                        UPDATE donations 
                        SET payment_url = :payment_url, nonce = :nonce
                        WHERE id = :donation_id
                    """),
                    {
                        'payment_url': payment_url,
                        'nonce': nonce,
                        'donation_id': donation_id
                    }
                )
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка обновления информации о платеже: {e}")
            return False

    async def get_donation_by_id(self, donation_id: int) -> Optional[dict]:
        """Получает информацию о донате по ID"""
        try:
            async with self.get_session() as session:
                result = await session.execute(
                    text("""
                        SELECT d.*, s.name as streamer_name, a.symbol as asset_symbol, 
                               a.name as asset_name, n.name as asset_network
                        FROM donations d
                        JOIN streamers s ON d.streamer_id = s.id
                        JOIN assets a ON d.asset_id = a.id
                        JOIN networks n ON a.network_id = n.id
                        WHERE d.id = :donation_id
                    """),
                    {'donation_id': donation_id}
                )
                row = result.fetchone()
                if row:
                    return dict(row._mapping)
                return None
        except Exception as e:
            logger.error(f"Ошибка получения доната по ID: {e}")
            return None


# Глобальный экземпляр для обратной совместимости
_database = None

async def get_database() -> Database:
    """Получает глобальный экземпляр базы данных"""
    global _database
    if _database is None:
        _database = Database()
    return _database 