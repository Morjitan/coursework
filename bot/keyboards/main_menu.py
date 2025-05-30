from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


async def get_main_menu_keyboard(db, telegram_id: int) -> InlineKeyboardMarkup:
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


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Returns keyboard with back to main menu button"""
    keyboard = [
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard) 