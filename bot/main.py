import os
import uuid
import logging
import datetime
from decimal import Decimal
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BufferedInputFile
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters.state import StateFilter
from bot.grpc_client import DonationClient
from bot.config_reader import config
from database import get_database
from bot.keyboards.main_menu import get_main_menu_keyboard
from bot.handlers.settings import (
    get_user_currency_amount,
    router as settings_router,
    get_settings_keyboard,
    AVAILABLE_CURRENCIES,
    convert_user_currency_to_usd
)
from database.repositories import UserRepository
from services.crypto_rates_service import crypto_rates_service

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BOT_TOKEN = config.bot_token.get_secret_value()
if not BOT_TOKEN:
    raise RuntimeError("Не задан BOT_TOKEN")

grpc_client = DonationClient()


class DonateStates(StatesGroup):
    waiting_for_streamer = State()
    waiting_for_currency = State()
    waiting_for_network = State()
    waiting_for_amount_currency = State()
    waiting_for_amount = State()
    waiting_for_message = State()


class StreamerRegistration(StatesGroup):
    waiting_for_name = State()
    waiting_for_wallet = State()


async def setup_bot():
    db = await get_database()
    await db.connect()
    
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    
    dp.include_router(settings_router)

    async def create_main_menu(telegram_id: int) -> InlineKeyboardMarkup:
        """Creates main menu with user status"""
        streamer = await db.get_streamer(telegram_id, include_inactive=False)
        is_active_streamer = streamer is not None
        
        if is_active_streamer:
            keyboard = [
                [
                    InlineKeyboardButton(text="🎁 Отправить донат", callback_data="donate"),
                    InlineKeyboardButton(text="📊 Мои донаты", callback_data="my_donations")
                ],
                [
                    InlineKeyboardButton(text="💰 Полученные донаты", callback_data="streamer_donations"),
                    InlineKeyboardButton(text="❌ Перестать быть стримером", callback_data="stop_being_streamer")
                ],
                [
                    InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings_menu"),
                    InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")
                ]
            ]
        else:
            keyboard = [
                [
                    InlineKeyboardButton(text="🎁 Отправить донат", callback_data="donate"),
                    InlineKeyboardButton(text="📊 Мои донаты", callback_data="my_donations")
                ],
                [
                    InlineKeyboardButton(text="📈 Стать стримером", callback_data="become_streamer"),
                    InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings_menu")
                ],
                [
                    InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")
                ]
            ]
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        await db.add_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
        
        markup = await create_main_menu(message.from_user.id)
        await message.answer("👋 Выберите действие:", reply_markup=markup)

    @dp.callback_query(lambda c: c.data == "settings_menu")
    async def cb_settings_menu(callback: CallbackQuery):
        try:
            db = await get_database()
            await db.connect()
            
            try:
                async with db.get_session() as session:
                    user_repo = UserRepository(session)
                    
                    user = await user_repo.get_or_create_user(
                        telegram_id=callback.from_user.id,
                        username=callback.from_user.username,
                        first_name=callback.from_user.first_name,
                        last_name=callback.from_user.last_name
                    )
                    await session.commit()
                    
                    current_currency = user.preferred_currency
                    currency_info = next(
                        (c for c in AVAILABLE_CURRENCIES if c['code'] == current_currency), 
                        AVAILABLE_CURRENCIES[0]
                    )
                    
                    text = (
                        "⚙️ <b>Настройки</b>\n\n"
                        f"👤 <b>Пользователь:</b> {user.display_name}\n"
                        f"💱 <b>Валюта отображения:</b> {currency_info['flag']} {currency_info['name']} ({currency_info['symbol']})\n\n"
                        "Выберите что хотите изменить:"
                    )
                    
                    await callback.message.edit_text(
                        text,
                        reply_markup=get_settings_keyboard(),
                        parse_mode="HTML"
                    )
                    
            finally:
                await db.disconnect()
                
        except Exception as e:
            logger.error(f"Ошибка в cb_settings_menu: {e}")
            await callback.message.edit_text("❌ Произошла ошибка при загрузке настроек")
        
        await callback.answer()

    @dp.callback_query(lambda c: c.data == "donate")
    async def cb_donate(callback: CallbackQuery, state: FSMContext):
        streamers = await db.get_all_streamers()
        
        if not streamers:
            await callback.message.edit_text(
                "😔 Пока нет зарегистрированных стримеров.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад", callback_data="main_menu")]
                ])
            )
            await callback.answer()
            return

        keyboard, row = [], []
        for idx, streamer in enumerate(streamers, start=1):
            row.append(InlineKeyboardButton(text=streamer['name'], callback_data=f"streamer_{streamer['id']}"))
            if idx % 2 == 0:
                keyboard.append(row)
                row = []
        if row: 
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton(text="Назад", callback_data="main_menu")])
        
        await callback.message.edit_text("Выберите стримера:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        await state.set_state(DonateStates.waiting_for_streamer)
        await callback.answer()

    @dp.callback_query(lambda c: c.data == "become_streamer")
    async def cb_become_streamer(callback: CallbackQuery, state: FSMContext):
        existing_streamer = await db.get_streamer(callback.from_user.id, include_inactive=True)
        
        if existing_streamer and existing_streamer.get('is_active', False):
            await callback.message.edit_text(
                f"Вы уже зарегистрированы как активный стример!\n"
                f"Имя: {existing_streamer['name']}\n"
                f"Кошелёк: {existing_streamer['wallet_address'][:6]}...{existing_streamer['wallet_address'][-4:]}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад", callback_data="main_menu")]
                ])
            )
        elif existing_streamer and not existing_streamer.get('is_active', False):
            await callback.message.edit_text(
                f"🔄 Ваш аккаунт стримера был деактивирован.\n"
                f"Хотите снова стать стримером?\n\n"
                f"Прежние данные:\n"
                f"Имя: {existing_streamer['name']}\n"
                f"Кошелёк: {existing_streamer['wallet_address'][:6]}...{existing_streamer['wallet_address'][-4:]}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Да, реактивировать", callback_data="reactivate_streamer")],
                    [InlineKeyboardButton(text="🆕 Новая регистрация", callback_data="new_streamer_registration")],
                    [InlineKeyboardButton(text="Назад", callback_data="main_menu")]
                ])
            )
        else:
            await callback.message.edit_text(
                "Введите ваше имя стримера:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад", callback_data="main_menu")]
                ])
            )
            await state.set_state(StreamerRegistration.waiting_for_name)
        
        await callback.answer()

    @dp.message(StreamerRegistration.waiting_for_name)
    async def process_streamer_name(message: types.Message, state: FSMContext):
        name = message.text.strip()
        if len(name) < 2:
            await message.answer("❌ Имя должно содержать минимум 2 символа.")
            return
        
        await state.update_data(name=name)
        await message.answer("Введите адрес вашего кошелька (например, 0x...):")
        await state.set_state(StreamerRegistration.waiting_for_wallet)

    @dp.message(StreamerRegistration.waiting_for_wallet)
    async def process_streamer_wallet(message: types.Message, state: FSMContext):
        wallet = message.text.strip()
        if not (wallet.startswith('0x') and len(wallet) == 42):
            await message.answer("❌ Введите корректный адрес кошелька (должен начинаться с 0x и содержать 42 символа).")
            return
        
        data = await state.get_data()
        name = data['name']
        
        streamer_id = await db.add_streamer(
            telegram_id=message.from_user.id,
            wallet_address=wallet,
            name=name,
            username=message.from_user.username
        )
        
        await message.answer(
            f"✅ Вы успешно зарегистрированы как стример!\n"
            f"Имя: {name}\n"
            f"Кошелёк: {wallet[:6]}...{wallet[-4:]}\n"
            f"ID стримера: {streamer_id}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
            ])
        )
        await state.clear()

    @dp.callback_query(lambda c: c.data == "main_menu")
    async def cb_main_menu(callback: CallbackQuery, state: FSMContext):
        markup = await create_main_menu(callback.from_user.id)
        
        # Проверяем, есть ли в сообщении текст для редактирования
        if callback.message.text:
            # Если сообщение содержит текст, редактируем его
            await callback.message.edit_text("👋 Выберите действие:", reply_markup=markup)
        else:
            # Если сообщение содержит изображение или медиа, отправляем новое сообщение
            await callback.message.answer("👋 Выберите действие:", reply_markup=markup)
        
        await state.clear()
        await callback.answer()

    @dp.callback_query(StateFilter(DonateStates.waiting_for_streamer), lambda c: c.data.startswith("streamer_"))
    async def cb_streamer(callback: CallbackQuery, state: FSMContext):
        streamer_id = int(callback.data.split("_", 1)[1])
        streamer = await db.get_streamer_by_id(streamer_id)
        
        if not streamer:
            await callback.answer("❌ Стример не найден", show_alert=True)
            return
        
        if streamer['telegram_id'] == callback.from_user.id:
            await callback.answer("❌ Вы не можете донатить самому себе!", show_alert=True)
            return
        
        await state.update_data(streamer_id=streamer_id, streamer_info=streamer)
        
        assets = await db.get_all_assets()
        
        if not assets:
            await callback.message.edit_text(
                "😔 В системе пока нет доступных активов для донатов.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад", callback_data="donate")]
                ])
            )
            await callback.answer()
            return
        
        unique_assets = {}
        for asset in assets:
            symbol = asset['symbol']
            if symbol not in unique_assets:
                unique_assets[symbol] = []
            unique_assets[symbol].append(asset)
        
        keyboard, row = [], []
        for idx, symbol in enumerate(unique_assets.keys(), start=1):
            row.append(InlineKeyboardButton(text=symbol, callback_data=f"symbol_{symbol}"))
            if idx % 3 == 0:
                keyboard.append(row)
                row = []
        if row: 
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton(text="Назад", callback_data="donate")])
        
        await callback.message.edit_text(
            f"Донат для стримера: {streamer['name']}\nВыберите актив:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        await state.set_state(DonateStates.waiting_for_currency)
        await callback.answer()

    @dp.callback_query(StateFilter(DonateStates.waiting_for_currency), lambda c: c.data.startswith("symbol_"))
    async def cb_currency(callback: CallbackQuery, state: FSMContext):
        symbol = callback.data.split("_", 1)[1]
        
        assets = await db.get_all_assets()
        
        symbol_assets = [asset for asset in assets if asset['symbol'] == symbol]
        
        if not symbol_assets:
            await callback.answer("❌ Активы с таким символом не найдены", show_alert=True)
            return
        
        await state.update_data(selected_symbol=symbol, available_assets=symbol_assets)
        
        keyboard, row = [], []
        for idx, asset in enumerate(symbol_assets, start=1):
            network_name = asset['network'].upper()
            row.append(InlineKeyboardButton(text=network_name, callback_data=f"asset_{asset['id']}"))
            if idx % 2 == 0:
                keyboard.append(row)
                row = []
        if row: 
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton(text="Назад", callback_data="donate")])
        
        await callback.message.edit_text(
            f"Вы выбрали: {symbol}\nВыберите сеть:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        await state.set_state(DonateStates.waiting_for_network)
        await callback.answer()

    @dp.callback_query(StateFilter(DonateStates.waiting_for_network), lambda c: c.data.startswith("asset_"))
    async def cb_network(callback: CallbackQuery, state: FSMContext):
        asset_id = int(callback.data.split("_", 1)[1])
        
        asset = await db.get_asset_by_id(asset_id)
        if not asset:
            await callback.answer("❌ Актив не найден", show_alert=True)
            return
        
        await state.update_data(asset_id=asset_id, asset_info=asset)
        await state.set_state(DonateStates.waiting_for_amount_currency)
        
        async with db.get_session() as session:
            user_repo = UserRepository(session)
            user_currency = await user_repo.get_preferred_currency(callback.from_user.id)
        
        user_currency_info = next(
            (c for c in AVAILABLE_CURRENCIES if c['code'] == user_currency),
            {'name': 'USD', 'symbol': '$', 'flag': '🇺🇸'}
        )
        
        keyboard = [
            [InlineKeyboardButton(
                text=f"💰 В {asset['symbol']} (криптовалюта)", 
                callback_data=f"amount_currency_{asset['symbol']}"
            )],
            [InlineKeyboardButton(
                text=f"{user_currency_info['flag']} В {user_currency_info['name']} ({user_currency_info['symbol']})", 
                callback_data=f"amount_currency_{user_currency}"
            )],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="donate")]
        ]
        
        await callback.message.edit_text(
            f"Вы выбрали: {asset['symbol']} ({asset['network'].upper()})\n\n"
            f"В какой валюте хотите ввести сумму доната?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        await callback.answer()

    @dp.callback_query(StateFilter(DonateStates.waiting_for_amount_currency), lambda c: c.data.startswith("amount_currency_"))
    async def cb_amount_currency(callback: CallbackQuery, state: FSMContext):
        """Обработчик выбора валюты для ввода суммы"""
        selected_currency = callback.data.split("_", 2)[2]  # amount_currency_USD -> USD
        
        data = await state.get_data()
        asset_info = data.get("asset_info")
        
        await state.update_data(amount_currency=selected_currency)
        await state.set_state(DonateStates.waiting_for_amount)
        
        if selected_currency == asset_info['symbol']:
            currency_display = f"{selected_currency} (криптовалюта)"
        else:
            currency_info = next(
                (c for c in AVAILABLE_CURRENCIES if c['code'] == selected_currency),
                {'name': selected_currency, 'symbol': selected_currency}
            )
            currency_display = f"{currency_info['name']} ({currency_info['symbol']})"
        
        await callback.message.edit_text(
            f"Актив: {asset_info['symbol']} ({asset_info['network'].upper()})\n"
            f"Валюта ввода: {currency_display}\n\n"
            f"Введите сумму доната:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="donate")]
            ])
        )
        await callback.answer()

    @dp.message(DonateStates.waiting_for_amount)
    async def process_amount(message: types.Message, state: FSMContext):
        try:
            amount = float(message.text.strip())
            if amount <= 0:
                raise ValueError("Сумма должна быть положительной")
        except ValueError:
            await message.answer("❌ Введите корректное положительное число.")
            return
        
        data = await state.get_data()
        asset_info = data.get("asset_info")
        amount_currency = data.get("amount_currency")
        
        if amount_currency == asset_info['symbol']:
            try:
                crypto_rate = await crypto_rates_service.get_single_rate(amount_currency)
                if crypto_rate is None:
                    fallback_rates = {
                        'ETH': 2600.0, 'BTC': 42000.0, 'USDT': 1.0, 'USDC': 1.0,
                        'BNB': 300.0, 'MATIC': 0.8, 'TRX': 0.1,
                    }
                    crypto_rate = fallback_rates.get(amount_currency, 1.0)
                    logger.warning(f"Используется fallback курс для {amount_currency}: ${crypto_rate:.2f}")
            except Exception as e:
                logger.error(f"Ошибка получения курса {amount_currency}: {e}")
                crypto_rate = {'ETH': 2600.0, 'BTC': 42000.0, 'USDT': 1.0, 'USDC': 1.0, 'BNB': 300.0, 'MATIC': 0.8, 'TRX': 0.1}.get(amount_currency, 1.0)
            
            payment_amount_usd = amount * crypto_rate
            display_amount = f"{amount:.4f} {amount_currency} (≈${payment_amount_usd:.2f} USD)"
            
        else:
            if amount_currency == 'USD':
                payment_amount_usd = amount
            else:
                payment_amount_usd = float(await convert_user_currency_to_usd(
                    message.from_user.id, Decimal(str(amount))
                ))
            
            currency_info = next(
                (c for c in AVAILABLE_CURRENCIES if c['code'] == amount_currency),
                {'symbol': amount_currency}
            )
            display_amount = f"{amount:.2f} {currency_info['symbol']} (≈${payment_amount_usd:.2f} USD)"
        
        await state.update_data(
            amount=payment_amount_usd,
            original_amount=amount,
            amount_currency=amount_currency,
            display_amount=display_amount
        )
        await message.answer("Введите сообщение для стримера (или отправьте /skip чтобы пропустить):")
        await state.set_state(DonateStates.waiting_for_message)

    @dp.message(DonateStates.waiting_for_message)
    async def process_message(message: types.Message, state: FSMContext):
        data = await state.get_data()
        streamer_info = data["streamer_info"]
        asset_id = data.get("asset_id")
        asset_info = data.get("asset_info")
        amount = data["amount"]
        original_amount = data.get("original_amount")
        amount_currency = data.get("amount_currency")
        display_amount = data.get("display_amount")
        
        if not asset_id or not asset_info:
            await message.answer("❌ Ошибка: информация об активе не найдена.")
            return
        
        donation_message = "" if message.text == "/skip" else message.text.strip()
        
        if amount_currency == asset_info['symbol']:
            payment_amount = original_amount
        else:
            try:
                crypto_rate = await crypto_rates_service.get_single_rate(asset_info['symbol'])
                if crypto_rate is None:
                    fallback_rates = {
                        'ETH': 2600.0, 'BTC': 42000.0, 'USDT': 1.0, 'USDC': 1.0,
                        'BNB': 300.0, 'MATIC': 0.8, 'TRX': 0.1,
                    }
                    crypto_rate = fallback_rates.get(asset_info['symbol'], 1.0)
                    logger.warning(f"Используется fallback курс для {asset_info['symbol']}: ${crypto_rate:.2f}")
            except Exception as e:
                logger.error(f"Ошибка получения курса {asset_info['symbol']}: {e}")
                crypto_rate = {'ETH': 2600.0, 'BTC': 42000.0, 'USDT': 1.0, 'USDC': 1.0, 'BNB': 300.0, 'MATIC': 0.8, 'TRX': 0.1}.get(asset_info['symbol'], 1.0)
            
            payment_amount = amount / crypto_rate
        
        try:
            donor_name = await db.get_user_by_name_pattern(message.from_user.id)
            
            donation_id = await db.create_donation(
                streamer_id=streamer_info["id"],
                asset_id=asset_id,
                donor_name=donor_name,
                amount=amount,
                message=donation_message,
                payment_url="",
                nonce=""
            )
            
            payment_data = grpc_client.create_payment_link(
                streamer_wallet=streamer_info["wallet_address"],
                amount=payment_amount,
                asset_symbol=asset_info['symbol'],
                network=asset_info['network'],
                donation_id=str(donation_id),
                donor_name=donor_name,
                message=donation_message
            )
            
            await db.update_donation_payment_info(
                donation_id,
                payment_data['payment_url'],
                payment_data['nonce']
            )
            
            expires_datetime = datetime.datetime.fromtimestamp(payment_data['expires_at'])
            expires_str = expires_datetime.strftime('%H:%M')
            
            await message.answer(
                f"💰 <b>Донат создан!</b>\n\n"
                f"👤 <b>Стример:</b> {streamer_info['name']}\n"
                f"💰 <b>Сумма:</b> {display_amount}\n"
                f"🔗 <b>Актив:</b> {asset_info['symbol']} ({asset_info['network'].upper()})\n"
                f"💬 <b>Сообщение:</b> {donation_message or 'Нет сообщения'}\n\n"
                f"⏰ <b>Оплатить до:</b> {expires_str}\n"
                f"🆔 <b>ID доната:</b> {donation_id}\n\n"
                f"🔗 <b>Ссылка для оплаты:</b>\n{payment_data['payment_url']}\n\n"
                f"⚠️ <i>Платеж будет автоматически отменен через 15 минут</i>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📱 Показать QR код", callback_data=f"show_qr_{donation_id}")],
                    [InlineKeyboardButton(text="🔍 Проверить статус", callback_data=f"check_payment_{donation_id}")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ]),
                parse_mode="HTML"
            )
            
        except Exception as e:
            logger.error(f"Ошибка при создании платежа: {e}")
            await message.answer(
                f"❌ Ошибка при создании платежа: {str(e)}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ])
            )
        
        await state.clear()

    @dp.callback_query(lambda c: c.data == "received_donations")
    async def cb_received_donations(callback: CallbackQuery):
        """Обработчик полученных донатов для стримеров"""
        streamer = await db.get_streamer(callback.from_user.id, include_inactive=False)
        
        if not streamer:
            await callback.message.edit_text(
                "❌ Вы не являетесь активным стримером.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад", callback_data="main_menu")]
                ])
            )
            await callback.answer()
            return
        
        stats = await db.get_received_donations_stats(streamer['id'])
        
        text = f"📊 <b>Статистика полученных донатов</b>\n\n"
        text += f"💰 <b>За всё время:</b>\n"
        text += f"   • Донатов: {stats['total']['count']}\n"
        text += f"   • Сумма: {stats['total']['amount']:.2f} (крипто)\n\n"
        text += f"📅 <b>За последний месяц:</b>\n"
        text += f"   • Донатов: {stats['month']['count']}\n"
        text += f"   • Сумма: {stats['month']['amount']:.2f} (крипто)\n\n"
        text += f"⏰ <b>За последнюю неделю:</b>\n"
        text += f"   • Донатов: {stats['week']['count']}\n"
        text += f"   • Сумма: {stats['week']['amount']:.2f} (крипто)\n\n"
        text += f"<i>💡 Суммы указаны в криптовалютах без конвертации</i>"
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="main_menu")]
            ])
        )
        await callback.answer()

    @dp.callback_query(lambda c: c.data == "sent_donations" or c.data.startswith("sent_donations_page_"))
    async def cb_sent_donations(callback: CallbackQuery):
        """Обработчик отправленных донатов с пагинацией"""
        if callback.data == "sent_donations":
            page = 0
        else:
            page = int(callback.data.split("_")[-1])
        
        offset = page * 5
        
        donor_name = await db.get_user_by_name_pattern(callback.from_user.id)
        
        data = await db.get_sent_donations_by_user(donor_name, limit=5, offset=offset)
        
        text = f"📤 <b>Ваши отправленные донаты</b>\n\n"
        text += f"💸 <b>Всего потрачено:</b> ~{data['total_amount_usd']:.2f} USD\n"
        text += f"🎯 <b>Всего донатов:</b> {data['total_count']}\n\n"
        
        if data['donations']:
            text += f"📋 <b>Страница {page + 1}:</b>\n\n"
            
            for i, donation in enumerate(data['donations'], 1):
                status_emoji = "✅" if donation['status'] == 'confirmed' else "⏳" if donation['status'] == 'pending' else "❌"
                
                text += f"{status_emoji} <b>Донат {offset + i}:</b>\n"
                text += f"   👤 Стример: {donation['streamer_name']}\n"
                text += f"   💰 Сумма: {donation['amount']} {donation['asset_symbol']} ({donation['asset_network'].upper()})\n"
                
                if donation['message']:
                    message = donation['message'][:50] + "..." if len(donation['message']) > 50 else donation['message']
                    text += f"   💬 Сообщение: {message}\n"
                
                text += f"   📅 Дата: {donation['created_at'].strftime('%d.%m.%Y %H:%M')}\n"
                
                if donation['confirmed_at']:
                    text += f"   ✅ Подтвержден: {donation['confirmed_at'].strftime('%d.%m.%Y %H:%M')}\n"
                
                text += "\n"
        else:
            text += "📭 У вас пока нет отправленных донатов."
        
        buttons = []
        nav_buttons = []
        
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"sent_donations_page_{page - 1}"))
        
        if data['has_more']:
            nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"sent_donations_page_{page + 1}"))
        
        if nav_buttons:
            buttons.append(nav_buttons)
        
        buttons.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")])
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
        await callback.answer()

    @dp.callback_query(lambda c: c.data == "stop_being_streamer")
    async def cb_stop_being_streamer(callback: CallbackQuery):
        """Handler for stopping being a streamer - shows warning"""
        streamer = await db.get_streamer(callback.from_user.id, include_inactive=False)
        
        if not streamer:
            await callback.message.edit_text(
                "❌ Вы не являетесь активным стримером.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад", callback_data="main_menu")]
                ])
            )
            await callback.answer()
            return
        
        text = "⚠️ <b>ВНИМАНИЕ! Подтвердите деактивацию аккаунта стримера</b>\n\n"
        text += "🔴 <b>Если вы продолжите:</b>\n"
        text += "• Вся история ваших полученных донатов будет удалена\n"
        text += "• Вы не сможете получать новые донаты через наш сервис\n"
        text += "• Ваш профиль стримера станет неактивным\n\n"
        text += "💡 <b>Вы всегда сможете снова зарегистрироваться как стример</b>\n\n"
        text += "Вы уверены, что хотите перестать быть стримером?"
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да, удалить", callback_data="confirm_stop_streamer"),
                    InlineKeyboardButton(text="❌ Нет, отмена", callback_data="cancel_stop_streamer")
                ]
            ])
        )
        await callback.answer()

    @dp.callback_query(lambda c: c.data == "confirm_stop_streamer")
    async def cb_confirm_stop_streamer(callback: CallbackQuery):
        """Confirmation of deactivation of a streamer"""
        streamer = await db.get_streamer(callback.from_user.id, include_inactive=False)
        
        if not streamer:
            await callback.message.edit_text(
                "❌ Вы не являетесь активным стримером.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад", callback_data="main_menu")]
                ])
            )
            await callback.answer()
            return
        
        success = await db.remove_streamer(callback.from_user.id)
        
        if success:
            text = "✅ <b>Ваш аккаунт стримера успешно деактивирован</b>\n\n"
            text += "🔴 <b>Что произошло:</b>\n"
            text += "• Ваш профиль стримера деактивирован\n"
            text += "• История полученных донатов удалена из системы\n"
            text += "• Вы больше не можете получать донаты\n\n"
            text += "💙 <b>Спасибо за использование нашего сервиса!</b>\n"
            text += "Вы всегда можете вернуться и снова стать стримером."
        else:
            text = "❌ <b>Ошибка при деактивации аккаунта стримера</b>\n\n"
            text += "Произошла техническая ошибка. Попробуйте еще раз или обратитесь к администратору."
        
        markup = await create_main_menu(callback.from_user.id)
        await callback.message.edit_text(text, reply_markup=markup)
        await callback.answer()

    @dp.callback_query(lambda c: c.data == "cancel_stop_streamer")
    async def cb_cancel_stop_streamer(callback: CallbackQuery):
        """Cancel deactivation of a streamer"""
        text = "✅ <b>Деактивация отменена</b>\n\n"
        text += "Ваш аккаунт стримера остается активным.\n"
        text += "Вы можете продолжать получать донаты через наш сервис! 💙"
        
        markup = await create_main_menu(callback.from_user.id)
        await callback.message.edit_text(text, reply_markup=markup)
        await callback.answer()

    @dp.message(Command("status"))
    async def cmd_status(message: types.Message):
        await message.answer("Для проверки статуса платежа используйте команду /check_payment <payment_url>")

    @dp.message(Command("check_payment"))
    async def cmd_check_payment(message: types.Message):
        try:
            parts = message.text.split(maxsplit=1)
            if len(parts) < 2:
                await message.answer("Использование: /check_payment <payment_url>")
                return
            
            payment_url = parts[1]
            
            status_info = grpc_client.check_transaction_status(payment_url)
            
            donation = await db.get_donation_by_payment_url(payment_url)
            if donation and status_info["confirmed"] and donation["status"] != "confirmed":
                await db.update_donation_status(
                    donation["id"], 
                    "confirmed", 
                    status_info.get("transaction_hash")
                )
                status_text = "✅ Подтверждён"
            elif donation and donation["status"] == "confirmed":
                status_text = "✅ Подтверждён"
            else:
                status_text = "⏳ Ожидает подтверждения"
            
            if donation:
                await message.answer(
                    f"Статус доната для {donation['streamer_name']}:\n"
                    f"Сумма: {donation['amount']} {donation['asset_symbol']} ({donation['asset_network'].upper()})\n"
                    f"Статус: {status_text}\n"
                    f"Хэш транзакции: {status_info.get('transaction_hash', 'Нет')}"
                )
            else:
                await message.answer("Донат с указанной ссылкой не найден.")
                
        except Exception as e:
            await message.answer(f"❌ Ошибка при проверке статуса: {str(e)}")

    @dp.callback_query(lambda c: c.data == "reactivate_streamer")
    async def cb_reactivate_streamer(callback: CallbackQuery, state: FSMContext):
        """Reactivation of an existing streamer"""
        existing_streamer = await db.get_streamer(callback.from_user.id, include_inactive=True)
        
        if existing_streamer and not existing_streamer.get('is_active', False):
            streamer_id = await db.add_streamer(
                telegram_id=callback.from_user.id,
                wallet_address=existing_streamer['wallet_address'],
                name=existing_streamer['name'],
                username=callback.from_user.username
            )
            
            await callback.message.edit_text(
                f"✅ Ваш аккаунт стримера успешно реактивирован!\n"
                f"Имя: {existing_streamer['name']}\n"
                f"Кошелёк: {existing_streamer['wallet_address'][:6]}...{existing_streamer['wallet_address'][-4:]}\n"
                f"ID стримера: {streamer_id}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
                ])
            )
        else:
            await callback.message.edit_text(
                "❌ Ошибка: неактивный стример не найден.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад", callback_data="main_menu")]
                ])
            )
        
        await callback.answer()

    @dp.callback_query(lambda c: c.data == "new_streamer_registration")
    async def cb_new_streamer_registration(callback: CallbackQuery, state: FSMContext):
        """New streamer registration"""
        await callback.message.edit_text(
            "Введите ваше новое имя стримера:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="main_menu")]
            ])
        )
        await state.set_state(StreamerRegistration.waiting_for_name)
        await callback.answer()

    @dp.message(StreamerRegistration.waiting_for_name)
    async def process_new_streamer_name(message: types.Message, state: FSMContext):
        name = message.text.strip()
        if len(name) < 2:
            await message.answer("❌ Имя должно содержать минимум 2 символа.")
            return
        
        await state.update_data(name=name)
        await message.answer("Введите адрес вашего кошелька (например, 0x...):")
        await state.set_state(StreamerRegistration.waiting_for_wallet)

    @dp.message(StreamerRegistration.waiting_for_wallet)
    async def process_new_streamer_wallet(message: types.Message, state: FSMContext):
        wallet = message.text.strip()
        if not (wallet.startswith('0x') and len(wallet) == 42):
            await message.answer("❌ Введите корректный адрес кошелька (должен начинаться с 0x и содержать 42 символа).")
            return
        
        data = await state.get_data()
        name = data['name']
        
        streamer_id = await db.add_streamer(
            telegram_id=message.from_user.id,
            wallet_address=wallet,
            name=name,
            username=message.from_user.username
        )
        
        await message.answer(
            f"✅ Вы успешно зарегистрированы как стример!\n"
            f"Имя: {name}\n"
            f"Кошелёк: {wallet[:6]}...{wallet[-4:]}\n"
            f"ID стримера: {streamer_id}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
            ])
        )
        await state.clear()

    @dp.callback_query(lambda c: c.data == "my_donations")
    async def cb_my_donations(callback: CallbackQuery):
        """Handler for 'My Donations' button - shows sent donations"""
        page = 0
        offset = page * 5
        
        donor_name = await db.get_user_by_name_pattern(callback.from_user.id)
        
        data = await db.get_sent_donations_by_user(donor_name, limit=5, offset=offset)
        
        text = f"📤 <b>Ваши отправленные донаты</b>\n\n"
        text += f"💸 <b>Всего потрачено:</b> ~{data['total_amount_usd']:.2f} USD\n"
        text += f"🎯 <b>Всего донатов:</b> {data['total_count']}\n\n"
        
        if data['donations']:
            text += f"📋 <b>Страница {page + 1}:</b>\n\n"
            
            for i, donation in enumerate(data['donations'], 1):
                status_emoji = "✅" if donation['status'] == 'confirmed' else "⏳" if donation['status'] == 'pending' else "❌"
                
                text += f"{status_emoji} <b>Донат {offset + i}:</b>\n"
                text += f"   👤 Стример: {donation['streamer_name']}\n"
                text += f"   💰 Сумма: {donation['amount']} {donation['asset_symbol']} ({donation['asset_network'].upper()})\n"
                
                if donation['message']:
                    message = donation['message'][:50] + "..." if len(donation['message']) > 50 else donation['message']
                    text += f"   💬 Сообщение: {message}\n"
                
                text += f"   📅 Дата: {donation['created_at'].strftime('%d.%m.%Y %H:%M')}\n"
                
                if donation['confirmed_at']:
                    text += f"   ✅ Подтвержден: {donation['confirmed_at'].strftime('%d.%m.%Y %H:%M')}\n"
                
                text += "\n"
        else:
            text += "📭 У вас пока нет отправленных донатов."
        
        buttons = []
        nav_buttons = []
        
        if data['has_more']:
            nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"sent_donations_page_{page + 1}"))
        
        if nav_buttons:
            buttons.append(nav_buttons)
        
        buttons.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")])
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
        await callback.answer()

    @dp.callback_query(lambda c: c.data == "streamer_donations")
    async def cb_streamer_donations(callback: CallbackQuery):
        """Handler for 'Received Donations' button - shows received donations with conversion"""
        streamer = await db.get_streamer(callback.from_user.id, include_inactive=False)
        
        if not streamer:
            await callback.message.edit_text(
                "❌ Вы не являетесь активным стримером.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад", callback_data="main_menu")]
                ])
            )
            await callback.answer()
            return
        
        stats = await db.get_received_donations_stats(streamer['id'])
        
        total_amount_converted, currency_symbol = await get_user_currency_amount(
            callback.from_user.id, Decimal(str(stats['total']['amount']))
        )
        month_amount_converted, _ = await get_user_currency_amount(
            callback.from_user.id, Decimal(str(stats['month']['amount']))
        )
        week_amount_converted, _ = await get_user_currency_amount(
            callback.from_user.id, Decimal(str(stats['week']['amount']))
        )
        
        text = f"📊 <b>Статистика полученных донатов</b>\n\n"
        text += f"💰 <b>За всё время:</b>\n"
        text += f"   • Донатов: {stats['total']['count']}\n"
        text += f"   • Сумма: {total_amount_converted:.2f} {currency_symbol}\n\n"
        text += f"📅 <b>За последний месяц:</b>\n"
        text += f"   • Донатов: {stats['month']['count']}\n"
        text += f"   • Сумма: {month_amount_converted:.2f} {currency_symbol}\n\n"
        text += f"⏰ <b>За последнюю неделю:</b>\n"
        text += f"   • Донатов: {stats['week']['count']}\n"
        text += f"   • Сумма: {week_amount_converted:.2f} {currency_symbol}\n\n"
        text += f"<i>💡 Суммы конвертированы в вашу валюту из USD</i>"
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="main_menu")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.callback_query(lambda c: c.data == "help")
    async def cb_help(callback: CallbackQuery):
        """Обработчик кнопки помощи"""
        help_text = (
            "ℹ️ <b>Справка по боту</b>\n\n"
            "🎁 <b>Отправить донат</b> - отправить пожертвование стримеру\n"
            "📊 <b>Мои донаты</b> - просмотр ваших отправленных донатов\n"
            "📈 <b>Стать стримером</b> - регистрация как стример для получения донатов\n"
            "💰 <b>Полученные донаты</b> - статистика полученных донатов (только для стримеров)\n"
            "❌ <b>Перестать быть стримером</b> - деактивация аккаунта стримера\n"
            "⚙️ <b>Настройки</b> - изменение валюты отображения и других параметров\n\n"
            "💡 <b>Команды:</b>\n"
            "/start - перезапуск бота\n"
            "/settings - настройки\n"
            "/check_payment <b>ссылка</b> - проверка статуса платежа\n\n"
            "💰 <b>Процесс создания доната:</b>\n"
            "1. Выберите стримера\n"
            "2. Выберите криптовалюту (USDT, ETH, etc.)\n"
            "3. Выберите сеть (Ethereum, BSC, etc.)\n"
            "4. Выберите валюту для ввода суммы:\n"
            "   • 💰 В криптовалюте (например, USDT)\n"
            "   • 🌍 В вашей фиатной валюте (USD, RUB, EUR)\n"
            "5. Введите сумму и сообщение\n\n"
            "🌍 <b>Поддерживаемые валюты:</b>\n"
            "🇺🇸 USD (доллар США)\n"
            "🇷🇺 RUB (российский рубль)\n"
            "🇪🇺 EUR (евро)\n\n"
            "🔗 <b>Поддерживаемые сети:</b>\n"
            "Ethereum, BSC, Polygon, Tron\n\n"
            "💱 <b>Валютная система:</b>\n"
            "• Все суммы автоматически конвертируются в вашу валюту для отображения\n"
            "• При создании доната можете выбрать валюту ввода\n"
            "• Фиатные валюты автоматически конвертируются в криптовалюту\n"
            "• Курсы обновляются в реальном времени\n"
            "• Изменить валюту отображения можно в настройках"
        )
        
        await callback.message.edit_text(
            help_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.callback_query(lambda c: c.data.startswith("check_payment_"))
    async def cb_check_payment(callback: CallbackQuery):
        """Handler for checking payment status through callback button"""
        try:
            donation_id = int(callback.data.split("_")[-1])
            
            donation = await db.get_donation_by_id(donation_id)
            
            if not donation:
                await callback.answer("❌ Донат не найден", show_alert=True)
                return
            
            status_info = grpc_client.check_transaction_status(donation['payment_url'])
            
            if status_info["confirmed"] and donation["status"] != "confirmed":
                await db.update_donation_status(
                    donation["id"], 
                    "confirmed", 
                    status_info.get("transaction_hash")
                )
                status_text = "✅ Подтверждён"
            elif donation["status"] == "confirmed":
                status_text = "✅ Подтверждён"
            else:
                status_text = "⏳ Ожидает подтверждения"
            
            await callback.message.edit_text(
                f"🔍 <b>Проверка статуса платежа</b>\n\n"
                f"👤 <b>Стример:</b> {donation['streamer_name']}\n"
                f"💰 <b>Сумма:</b> {donation['amount']} {donation['asset_symbol']} ({donation['asset_network'].upper()})\n"
                f"📅 <b>Дата:</b> {donation['created_at'].strftime('%d.%m.%Y %H:%M')}\n"
                f"🏷️ <b>Статус:</b> {status_text}\n"
                f"🔗 <b>Хэш транзакции:</b> {status_info.get('transaction_hash', 'Нет')}\n\n"
                f"💬 <b>Сообщение:</b> {donation.get('message', 'Нет сообщения')}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Обновить статус", callback_data=f"check_payment_{donation_id}")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ]),
                parse_mode="HTML"
            )
            
        except Exception as e:
            await callback.answer(f"❌ Ошибка при проверке статуса: {str(e)}", show_alert=True)
        
        await callback.answer()

    @dp.callback_query(lambda c: c.data.startswith("show_qr_"))
    async def cb_show_qr(callback: CallbackQuery):
        """Handler for showing QR code for payment"""
        try:
            donation_id = int(callback.data.split("_")[-1])
            
            donation = await db.get_donation_by_id(donation_id)
            
            if not donation:
                await callback.answer("❌ Донат не найден", show_alert=True)
                return
            
            qr_response = grpc_client.get_payment_qr_code(donation['payment_url'])
            
            if qr_response and qr_response.qr_code_image:
                qr_file = BufferedInputFile(
                    qr_response.qr_code_image, 
                    filename=f"payment_qr_{donation_id}.png"
                )
                
                await callback.message.answer_photo(
                    photo=qr_file,
                    caption=f"📱 <b>QR код для оплаты</b>\n\n"
                            f"👤 <b>Стример:</b> {donation['streamer_name']}\n"
                            f"💰 <b>Сумма:</b> {donation['amount']} {donation['asset_symbol']}\n"
                            f"🔗 <b>Сеть:</b> {donation['asset_network'].upper()}\n\n"
                            f"📱 <i>Отсканируйте QR код кошельком для оплаты</i>",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔍 Проверить статус", callback_data=f"check_payment_{donation_id}")],
                        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                    ])
                )
            else:
                await callback.answer("❌ Ошибка получения QR кода", show_alert=True)
            
        except Exception as e:
            await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
        
        await callback.answer()

    return bot, dp


async def shutdown_handler():
    db = await get_database()
    await db.disconnect() 