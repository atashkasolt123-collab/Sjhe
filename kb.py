from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import BETS_LINK, ADMINS, OWNER_LINK
import sqlite3


conn = sqlite3.connect("db.db")
cursor = conn.cursor()

def is_valid_url(url):
    """Проверяет валидность URL для Telegram кнопок"""
    if not url or not isinstance(url, str):
        return False
    return url.startswith('https://') or url.startswith('http://') or url.startswith('tg://')

def menu(userid):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💠 Профиль", callback_data='profile'),
        InlineKeyboardButton(text="Статистика 💠", callback_data='stats')
    )
    if is_valid_url(BETS_LINK):
        builder.row(InlineKeyboardButton(text="🎲 Сделать ставку 🎲", url=BETS_LINK))
    else:
        builder.row(InlineKeyboardButton(text="🎲 Сделать ставку 🎲", callback_data='no_link'))
    if userid in ADMINS:
        builder.row(InlineKeyboardButton(text="💫 Админ-Панель 💫", callback_data='admin'))
    return builder.as_markup()

def profile():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💠 Реф. Панель", callback_data='ref_panel'),
        InlineKeyboardButton(text="Кэшбек система 💠", callback_data='cashback')
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data='menu'))
    return builder.as_markup()

def back(call):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=call))
    return builder.as_markup()

def ref():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💠 Рефералы", callback_data='refs'),
        InlineKeyboardButton(text="Ссылки 💠", callback_data='links')
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data='profile'))
    return builder.as_markup()

def cashback():
    builder = InlineKeyboardBuilder()
    if is_valid_url(OWNER_LINK):
        builder.row(InlineKeyboardButton(text="💠 Вывести", url=OWNER_LINK))
    else:
        builder.row(InlineKeyboardButton(text="💠 Вывести", callback_data='no_link'))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data='profile'))
    return builder.as_markup()

def admin():
    status = cursor.execute("SELECT stop FROM settings").fetchone()[0]

    if status == 1:
        status = '🟢'
        call = '0'
    else:
        status = '🔴'
        call = '1'

    status1 = cursor.execute("SELECT ex FROM settings").fetchone()[0]

    if status1 == 1:
        status1 = '🟢'
        call1 = '0'
    else:
        status1 = '🔴'
        call1 = '1'

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💠 Рассылка", callback_data='broadcast'),
        InlineKeyboardButton(text="💠 Попол. Казну", callback_data='popol')
    )
    builder.row(
        InlineKeyboardButton(text="💠 Изм. Счёт", callback_data='change_invoice'),
        InlineKeyboardButton(text="💠 Упр. Пользователем", callback_data='control_user')
    )
    builder.row(
        InlineKeyboardButton(text="💠 Изм. Макс. Сумму", callback_data='change_max'),
        InlineKeyboardButton(text="💠 Вывод казны", callback_data='withdraw')
    )
    builder.row(
        InlineKeyboardButton(text="💠 Упр. Чеками", callback_data='checks'),
        InlineKeyboardButton(text=f"{status} Стоп ставки", callback_data=f'set_stop:{call}')
    )
    builder.row(
        InlineKeyboardButton(text="💠 Отправить туториал", callback_data='send_tutorial'),
        InlineKeyboardButton(text=f"{status1} 1.1x", callback_data=f'set_x:{call1}')
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data='menu'))
    return builder.as_markup()

def control(userid):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💠 Отправить сообщение", callback_data=f'send_message:{userid}'))
    builder.row(InlineKeyboardButton(text="💠 Анулировать реф-баланс", callback_data=f'empty_ref:{userid}'))
    builder.row(InlineKeyboardButton(text="💠 Анулировать кэшбек-счет", callback_data=f'empty_cashback:{userid}'))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data='control_user'))
    return builder.as_markup()
