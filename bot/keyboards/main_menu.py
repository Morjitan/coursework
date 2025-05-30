from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Returns main menu keyboard"""
    keyboard = [
        [
            InlineKeyboardButton(text="🎁 Отправить донат", callback_data="donate"),
            InlineKeyboardButton(text="📊 Мои донаты", callback_data="my_donations")
        ],
        [
            InlineKeyboardButton(text="📈 Стать стримером", callback_data="become_streamer"),
            InlineKeyboardButton(text="💰 Донаты стримера", callback_data="streamer_donations")
        ],
        [
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings_menu"),
            InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Returns keyboard with back to main menu button"""
    keyboard = [
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard) 