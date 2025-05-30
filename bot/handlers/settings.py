import logging
from decimal import Decimal
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command

from database import get_database
from database.repositories import UserRepository, CurrencyRepository

logger = logging.getLogger(__name__)

router = Router()

AVAILABLE_CURRENCIES = [
    {'code': 'USD', 'name': 'US Dollar', 'symbol': '$', 'flag': '🇺🇸'},
    {'code': 'RUB', 'name': 'Russian Ruble', 'symbol': '₽', 'flag': '🇷🇺'},
    {'code': 'EUR', 'name': 'Euro', 'symbol': '€', 'flag': '🇪🇺'},
]


def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Creates settings keyboard"""
    keyboard = [
        [InlineKeyboardButton(text="💱 Валюта отображения", callback_data="settings_currency")],
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_currency_selection_keyboard() -> InlineKeyboardMarkup:
    """Creates keyboard for currency selection"""
    keyboard = []
    
    for i in range(0, len(AVAILABLE_CURRENCIES), 2):
        row = []
        for j in range(2):
            if i + j < len(AVAILABLE_CURRENCIES):
                currency = AVAILABLE_CURRENCIES[i + j]
                text = f"{currency['flag']} {currency['code']} {currency['symbol']}"
                callback_data = f"set_currency_{currency['code']}"
                row.append(InlineKeyboardButton(text=text, callback_data=callback_data))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton(text="🔙 Назад к настройкам", callback_data="back_to_settings")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.message(Command("settings"))
async def settings_command(message: Message):
    """Handler for /settings command"""
    try:
        db = await get_database()
        await db.connect()
        
        try:
            async with db.get_session() as session:
                user_repo = UserRepository(session)
                
                user = await user_repo.get_or_create_user(
                    telegram_id=message.from_user.id,
                    username=message.from_user.username,
                    first_name=message.from_user.first_name,
                    last_name=message.from_user.last_name
                )
                await session.commit()
                
                current_currency = user.preferred_currency
                currency_info = next(
                    (c for c in AVAILABLE_CURRENCIES if c['code'] == current_currency), 
                    AVAILABLE_CURRENCIES[0]  # Fallback на USD
                )
                
                text = (
                    "⚙️ <b>Настройки</b>\n\n"
                    f"👤 <b>Пользователь:</b> {user.display_name}\n"
                    f"💱 <b>Валюта отображения:</b> {currency_info['flag']} {currency_info['name']} ({currency_info['symbol']})\n\n"
                    "Выберите что хотите изменить:"
                )
                
                await message.answer(
                    text,
                    reply_markup=get_settings_keyboard(),
                    parse_mode="HTML"
                )
                
        finally:
            await db.disconnect()
            
    except Exception as e:
        logger.error(f"Ошибка в settings_command: {e}")
        await message.answer("❌ Произошла ошибка при загрузке настроек")


@router.callback_query(F.data == "settings_currency")
async def currency_settings_callback(callback: CallbackQuery):
    """Handler for currency settings"""
    try:
        db = await get_database()
        await db.connect()
        
        try:
            async with db.get_session() as session:
                user_repo = UserRepository(session)
                user = await user_repo.get_by_telegram_id(callback.from_user.id)
                
                if not user:
                    await callback.answer("❌ Пользователь не найден")
                    return
                
                current_currency = user.preferred_currency
                currency_info = next(
                    (c for c in AVAILABLE_CURRENCIES if c['code'] == current_currency), 
                    AVAILABLE_CURRENCIES[0]
                )
                
                text = (
                    "💱 <b>Выбор валюты отображения</b>\n\n"
                    f"<b>Текущая валюта:</b> {currency_info['flag']} {currency_info['name']} ({currency_info['symbol']})\n\n"
                    "Эта валюта используется для:\n"
                    "• Отображения полученных донатов\n"
                    "• Отображения отправленных донатов\n" 
                    "• Ввода сумм при отправке пожертвований\n\n"
                    "Выберите новую валюту:"
                )
                
                await callback.message.edit_text(
                    text,
                    reply_markup=get_currency_selection_keyboard(),
                    parse_mode="HTML"
                )
                
        finally:
            await db.disconnect()
            
    except Exception as e:
        logger.error(f"Ошибка в currency_settings_callback: {e}")
        await callback.answer("❌ Произошла ошибка")


@router.callback_query(F.data.startswith("set_currency_"))
async def set_currency_callback(callback: CallbackQuery):
    """Handler for setting currency"""
    try:
        currency_code = callback.data.split("_")[-1]
        
        currency_info = next(
            (c for c in AVAILABLE_CURRENCIES if c['code'] == currency_code), 
            None
        )
        
        if not currency_info:
            await callback.answer("❌ Неизвестная валюта")
            return
        
        db = await get_database()
        await db.connect()
        
        try:
            async with db.get_session() as session:
                user_repo = UserRepository(session)
                
                updated_user = await user_repo.set_preferred_currency(
                    callback.from_user.id, 
                    currency_code
                )
                
                if updated_user:
                    await session.commit()
                    
                    text = (
                        f"✅ <b>Валюта изменена!</b>\n\n"
                        f"Теперь все суммы будут отображаться в валюте:\n"
                        f"{currency_info['flag']} <b>{currency_info['name']}</b> ({currency_info['symbol']})\n\n"
                        "Изменения применятся ко всем разделам бота."
                    )
                    
                    await callback.message.edit_text(
                        text,
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔙 Назад к настройкам", callback_data="back_to_settings")],
                            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
                        ]),
                        parse_mode="HTML"
                    )
                    
                    await callback.answer(f"Валюта изменена на {currency_info['symbol']}")
                else:
                    await callback.answer("❌ Не удалось обновить валюту")
                    
        finally:
            await db.disconnect()
            
    except Exception as e:
        logger.error(f"Ошибка в set_currency_callback: {e}")
        await callback.answer("❌ Произошла ошибка при сохранении")


@router.callback_query(F.data == "back_to_settings")
async def back_to_settings_callback(callback: CallbackQuery):
    """Returns to main settings"""
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
        logger.error(f"Ошибка в back_to_settings_callback: {e}")
        await callback.answer("❌ Произошла ошибка при загрузке настроек")


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu_callback(callback: CallbackQuery):
    """Returns to main menu"""
    from bot.keyboards.main_menu import get_main_menu_keyboard
    
    try:
        db = await get_database()
        await db.connect()
        
        try:
            async with db.get_session() as session:
                user_repo = UserRepository(session)
                user = await user_repo.get_by_telegram_id(callback.from_user.id)
                
                welcome_text = (
                    f"🏠 <b>Главное меню</b>\n\n"
                    f"Добро пожаловать, {user.display_name if user else 'Пользователь'}!\n"
                    "Выберите действие:"
                )
                
                await callback.message.edit_text(
                    welcome_text,
                    reply_markup=get_main_menu_keyboard(),
                    parse_mode="HTML"
                )
                
        finally:
            await db.disconnect()
            
    except Exception as e:
        logger.error(f"Ошибка в back_to_menu_callback: {e}")
        await callback.answer("❌ Ошибка возврата в меню")


async def get_user_currency_amount(telegram_id: int, amount_usd: Decimal) -> tuple[Decimal, str]:
    """
    Converts amount from USD to user's currency
    
    Returns:
        tuple: (converted_amount, currency_symbol)
    """
    try:
        db = await get_database()
        await db.connect()
        
        try:
            async with db.get_session() as session:
                user_repo = UserRepository(session)
                currency_repo = CurrencyRepository(session)
                
                user_currency = await user_repo.get_preferred_currency(telegram_id)
                
                if user_currency == 'USD':
                    return amount_usd, '$'
                
                converted = await currency_repo.convert_amount(amount_usd, 'USD', user_currency)
                
                if converted:
                    currency_info = next(
                        (c for c in AVAILABLE_CURRENCIES if c['code'] == user_currency),
                        {'symbol': user_currency}
                    )
                    return converted, currency_info['symbol']
                else:
                    return amount_usd, '$'
                    
        finally:
            await db.disconnect()
            
    except Exception as e:
        logger.error(f"Ошибка конвертации валюты для пользователя {telegram_id}: {e}")
        return amount_usd, '$'


async def convert_user_currency_to_usd(telegram_id: int, amount: Decimal) -> Decimal:
    """
    Converts amount from user's currency to USD
    
    Returns:
        Decimal: amount in USD
    """
    try:
        db = await get_database()
        await db.connect()
        
        try:
            async with db.get_session() as session:
                user_repo = UserRepository(session)
                currency_repo = CurrencyRepository(session)
                
                user_currency = await user_repo.get_preferred_currency(telegram_id)
                
                if user_currency == 'USD':
                    return amount

                converted = await currency_repo.convert_amount(amount, user_currency, 'USD')
                
                return converted if converted else amount
                    
        finally:
            await db.disconnect()
            
    except Exception as e:
        logger.error(f"Ошибка конвертации из валюты пользователя {telegram_id} в USD: {e}")
        return amount