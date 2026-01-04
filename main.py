from aiogram.types import FSInputFile
import re
import requests
import string
import random
import logging
import asyncio
import os
import sqlite3
from datetime import datetime
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import types, Dispatcher, Bot, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import StateFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

import kb
import config
import states

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота
bot = Bot(token=config.TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())

# Константы
COEFFICIENTS = {
    'победа 1': 3, 'победа 2': 3, 'п1': 3, 'п2': 3, 'ничья': 5,
    'нечет': 1.8, 'фут гол': 1.45, 'фут мимо': 1.8,
    'баскет гол': 1.8, 'баскет мимо': 1.3,
    'больше': 1.8, 'меньше': 1.8, 'чет': 1.8,
    'дартс белое': 1.8, 'дартс красное': 1.8, 'дартс мимо': 2.5, 'дартс центр': 2.5,
    'камень': 1.8, 'ножницы': 1.8, 'бумага': 1.8,
    'сектор 1': 2, 'сектор 2': 2, 'сектор 3': 2,
    'плинко': 1.85, 'пвп': 1.8,
    '2б': 1.8, '2м': 1.8, '2 больше': 1.8, '2 меньше': 1.8,
    'орёл': 1.95, 'решка': 1.95,
    'число 1': 4, 'число 2': 4, 'число 3': 4,
    'число 4': 4, 'число 5': 4, 'число 6': 4,
    'луна': 1.8, 'солнце': 1.8,
    'краш': 1  # Базовый коэффициент для краша (будет меняться)
}

DICE_CONFIG = {
    'нечет': ("🎲", [1, 3, 5]),
    'фут гол': ("⚽️", [3, 4, 5]),
    'фут мимо': ("⚽️", [1, 2, 6]),
    'баскет гол': ("🏀", [4, 5, 6]),
    'баскет мимо': ("🏀", [1, 2, 3]),
    'больше': ("🎲", [4, 5, 6]),
    'меньше': ("🎲", [1, 2, 3]),
    'чет': ("🎲", [2, 4, 6]),
    'дартс белое': ("🎯", [3, 5]),
    'дартс красное': ("🎯", [2, 4]),
    'дартс мимо': ("🎯", [1]),
    'дартс центр': ("🎯", [6]),
    'сектор 1': ("🎲", [1, 2]),
    'сектор 2': ("🎲", [3, 4]),
    'сектор 3': ("🎲", [5, 6]),
    'плинко': ("🎲", [4, 5, 6]),
    'бумага': ("✋", ['👊']),
    'камень': ("👊", ['✌️']),
    'ножницы': ("✌️", ['✋']),
    'победа 1': ("🎲", [1]), 'победа 2': ("🎲", [1]),
    'п1': ("🎲", [1]), 'п2': ("🎲", [1]),
    'ничья': ("🎲", [1]), 'пвп': ("🎲", [1]),
    '2б': ("🎲", [1]), '2м': ("🎲", [1]),
    '2 больше': ("🎲", [1]), '2 меньше': ("🎲", [1]),
    'орёл': ("🪙", [1]), 'решка': ("🪙", [2]),
    'число 1': ("🎲", [1]),
    'число 2': ("🎲", [2]),
    'число 3': ("🎲", [3]),
    'число 4': ("🎲", [4]),
    'число 5': ("🎲", [5]),
    'число 6': ("🎲", [6]),
    'луна': (["🌚", "🌝"], ['🌚']),
    'солнце': (["🌚", "🌝"], ['🌝']),
    'краш': ("🚀", [])  # Символ ракеты для краш-игры
}

# Словарь для активных краш-игр
ACTIVE_CRASH_GAMES = {}

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def random_quote() -> str:
    quotes = [
        'Хорошему игроку всегда везёт!',
        'В казино выигрывает только тот, кто владеет этим казино.',
        'В чужой игре всегда свободны роли пешек.',
        'Азартные игры - это кратчайший путь от бедности к деньгам и обратно.',
        'Азарт - это состояние, в которое мы входим, выходя из себя.',
    ]
    return random.choice(quotes)

def is_valid_url(url: str) -> bool:
    """Проверяет валидность URL для Telegram кнопок"""
    if not url or not isinstance(url, str):
        return False
    return url.startswith(('https://', 'http://', 'tg://'))

def generate_random_code(length: int) -> str:
    """Генерация рандомного кода"""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def calculate_winrate(winning_bets: int, total_bets: int) -> float:
    """Калькуляция винрейта"""
    if total_bets == 0:
        return 0
    return (winning_bets / total_bets) * 100

def days_text(days: int) -> str:
    """Генерация текста дней"""
    if days % 10 == 1 and days % 100 != 11:
        return f"{days} день"
    elif 2 <= days % 10 <= 4 and (days % 100 < 10 or days % 100 >= 20):
        return f"{days} дня"
    return f"{days} дней"

def get_user_mention(user) -> str:
    """Создание упоминания пользователя"""
    name = user.first_name or user.username or str(user.id)
    return f'<a href="tg://user?id={user.id}">{name}</a>'

def make_keyboard(*buttons) -> InlineKeyboardMarkup:
    """Хелпер для создания простой клавиатуры"""
    builder = InlineKeyboardBuilder()
    for btn in buttons:
        builder.row(btn)
    return builder.as_markup()

async def safe_answer(call, text: str = None, show_alert: bool = False):
    """Безопасный ответ на callback (игнорирует timeout ошибки)"""
    try:
        if text:
            await call.answer(text, show_alert=show_alert)
        else:
            await call.answer()
    except Exception as e:
        pass

# ==================== CRYPTOPAY API (POST ЗАПРОСЫ) ====================

def cryptopay_request(method: str, data: dict = None) -> dict:
    """Универсальная функция для запросов к CryptoPay API"""
    try:
        headers = {"Crypto-Pay-API-Token": config.CRYPTOPAY_TOKEN}
        url = f"https://pay.crypt.bot/api/{method}"
        if data:
            r = requests.post(url, json=data, headers=headers, timeout=10)
        else:
            r = requests.post(url, headers=headers, timeout=10)
        return r.json()
    except Exception as e:
        logging.error(f"CryptoPay API error ({method}): {e}")
        return {"ok": False, "error": str(e)}

def create_invoice(amount: float):
    """Создание счета для пополнения"""
    data = {"asset": "USDT", "amount": float(amount)}
    r = cryptopay_request("createInvoice", data)
    if r.get('ok') and r.get('result'):
        return r['result']['bot_invoice_url']
    logging.error(f"create_invoice error: {r}")
    return None

def get_cb_balance() -> float:
    """Получение баланса казны"""
    r = cryptopay_request("getBalance")
    if r.get('ok') and r.get('result'):
        for currency in r['result']:
            if currency['currency_code'] == 'USDT':
                return float(currency['available'])
    return 0.0

async def convert(amount_usd: float) -> float:
    """Конвертация USD -> RUB"""
    r = cryptopay_request("getExchangeRates")
    if r.get('ok') and r.get('result'):
        for data in r['result']:
            if data['source'] == 'USDT' and data['target'] == 'RUB':
                return float(amount_usd) * float(data['rate'])
    return float(amount_usd) * 90  # fallback курс

async def transfer(amount: float, us_id: int) -> None:
    """Трансфер средств пользователю"""
    bal = get_cb_balance()
    keyb = make_keyboard(InlineKeyboardButton(text="💼 Перейти к пользователю", url=f"tg://user?id={us_id}"))
    
    if bal < amount:
        try:
            await bot.send_message(us_id, f"<b>[🔔] Вам пришло системное уведомление:</b>\n\n<b><blockquote>Ваша выплата ⌊ {amount}$ ⌉ будет зачислена вручную <a href='{config.OWNER_LINK}'>администратором</a>!</blockquote></b>", reply_markup=keyb)
        except:
            pass
        try:
            await bot.send_message(config.LOGS_ID, f"<b>[🔔] Мало суммы в казне для выплаты!</b>\n\n<b><blockquote>Пользователь: {us_id}\nСумма: {amount}$</blockquote></b>", reply_markup=keyb)
        except:
            pass
        return
    
    try:
        spend_id = generate_random_code(10)
        data = {"asset": "USDT", "amount": float(amount), "user_id": us_id, "spend_id": spend_id}
        cryptopay_request("transfer", data)
        await bot.send_message(config.LOGS_ID, f"<b>[🧾] Перевод!</b>\n\n<b>[💠] Сумма: {amount} USDT</b>\n<b>[🚀] Пользователю: {us_id}</b>", reply_markup=keyb)
    except Exception as e:
        logging.error(f"transfer error: {e}")

async def create_check(amount: float, userid: int):
    """Создание чека"""
    bal = get_cb_balance()
    keyb = make_keyboard(InlineKeyboardButton(text="💼 Перейти к пользователю", url=f"tg://user?id={userid}"))
    
    if bal < amount:
        try:
            await bot.send_message(userid, f"<b>[🔔] Вам пришло системное уведомление:</b>\n\n<b><blockquote>Ваша выплата ⌊ {amount}$ ⌉ будет зачислена вручную <a href='{config.OWNER_LINK}'>администратором</a>!</blockquote></b>", reply_markup=keyb)
        except:
            pass
        try:
            await bot.send_message(config.LOGS_ID, f"<b>[🔔] Мало суммы в казне для выплаты!</b>\n\n<b><blockquote>Пользователь: {userid}\nСумма: {amount}$</blockquote></b>", reply_markup=keyb)
        except:
            pass
        return None
    
    data = {"asset": "USDT", "amount": float(amount), "pin_to_user_id": userid}
    r = cryptopay_request("createCheck", data)
    if r.get('ok') and r.get('result'):
        try:
            await bot.send_message(config.LOGS_ID, f"<b>[🧾] Создан чек!</b>\n\n<b>[💠] Сумма: {amount} USDT</b>\n<b>[🚀] Прикрепен за юзером: {userid}</b>", reply_markup=keyb)
        except:
            pass
        return r["result"]["bot_check_url"]
    logging.error(f"create_check error: {r}")
    return None

# ==================== ФУНКЦИИ ДЛЯ КРАШ-ИГРЫ ====================

def generate_crash_point() -> float:
    """Генерация точки краша с повышенной вероятностью срыва на низких коэффициентах"""
    # Создаем вероятность срыва: 80% на 1.3-2.0x, 20% на 2.0-2.3x
    if random.random() < 0.8:  # 80% вероятность срыва на низких коэффициентах
        # Из этих 80%: 60% на 1.3-1.5x, 40% на 1.5-2.0x
        if random.random() < 0.6:
            return random.uniform(1.3, 1.5)  # 48% всех игр
        else:
            return random.uniform(1.5, 2.0)  # 32% всех игр
    else:  # 20% вероятность дойти до высоких коэффициентов
        return random.uniform(2.3,)  # 20% всех игр

async def start_crash_game(user_id: int, amount: float, channel_msg_id: int, username: str):
    """Запуск новой краш-игры"""
    try:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🚀 Начать игру", callback_data=f"crash_start:{amount}:{channel_msg_id}"))
        
        msg = await bot.send_message(
            user_id,
            f"<b>🎮 Игра КРАШ</b>\n\n"
            f"<blockquote>📊 Ваша ставка: <code>{amount:.2f}$</code>\n"
            f"🚀 Ракета готова к запуску!\n"
            f"⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️\n"
            f"📈 Коэффициент: <code>1.00x</code></blockquote>\n\n"
            f"<i>Нажмите 'Начать игру' для запуска ракеты!</i>",
            reply_markup=builder.as_markup()
        )
        
        return msg.message_id
    except Exception as e:
        logging.error(f"Error starting crash game: {e}")
        return None

async def update_crash_game(user_id: int, message_id: int, amount: float, channel_msg_id: int):
    """Обновление краш-игры (полет ракеты)"""
    try:
        # Генерируем конечный коэффициент с новой логикой
        crash_point = generate_crash_point()
        current_multiplier = 1.0
        step = 0.01  # Уменьшаем шаг для более плавного роста
        
        # Запускаем задачу игры
        task = asyncio.create_task(crash_game_loop(user_id, message_id, amount, channel_msg_id, current_multiplier, crash_point, step))
        ACTIVE_CRASH_GAMES[user_id] = {
            'message_id': message_id,
            'multiplier': current_multiplier,
            'task': task,
            'channel_msg_id': channel_msg_id,
            'amount': amount,
            'crashed': False,
            'cashout_requested': False  # Флаг запроса на вывод
        }
        
    except Exception as e:
        logging.error(f"Error updating crash game: {e}")

async def crash_game_loop(user_id: int, message_id: int, amount: float, channel_msg_id: int, 
                          current_multiplier: float, crash_point: float, step: float):
    """Основной цикл краш-игры"""
    try:
        while (current_multiplier < min(crash_point, 2.3) and 
               user_id in ACTIVE_CRASH_GAMES and
               not ACTIVE_CRASH_GAMES[user_id].get('cashout_requested', False)):
            
            await asyncio.sleep(0.3)  # Уменьшаем время ожидания для более быстрой игры
            
            current_multiplier += step
            current_multiplier = round(current_multiplier, 2)
            
            # Если игрок уже запросил вывод - выходим из цикла
            if user_id in ACTIVE_CRASH_GAMES and ACTIVE_CRASH_GAMES[user_id].get('cashout_requested', False):
                break
            
            # Обновляем прогресс-бар
            progress_bars = min(int((current_multiplier - 1) / 0.1), 10)
            progress_display = "✅" * progress_bars + "⬜️" * (10 - progress_bars)
            
            builder = InlineKeyboardBuilder()
            builder.row(InlineKeyboardButton(
                text=f"💥 Забрать {current_multiplier:.2f}x", 
                callback_data=f"crash_cashout:{current_multiplier}:{amount}:{channel_msg_id}"
            ))
            
            try:
                await bot.edit_message_text(
                    f"<b>🎮 Игра КРАШ</b>\n\n"
                    f"<blockquote>📊 Ваша ставка: <code>{amount:.2f}$</code>\n"
                    f"🚀 Ракета в полете!\n"
                    f"{progress_display}\n"
                    f"📈 Коэффициент: <code>{current_multiplier:.2f}x</code></blockquote>\n\n"
                    f"<i>Нажмите 'Забрать' чтобы зафиксировать выигрыш!</i>",
                    user_id,
                    message_id,
                    reply_markup=builder.as_markup()
                )
                
                if user_id in ACTIVE_CRASH_GAMES:
                    ACTIVE_CRASH_GAMES[user_id]['multiplier'] = current_multiplier
                    
            except Exception as e:
                logging.error(f"Error editing crash message: {e}")
                break
        
        # Проверяем, был ли запрос на вывод
        if user_id in ACTIVE_CRASH_GAMES:
            if ACTIVE_CRASH_GAMES[user_id].get('cashout_requested', False):
                # Игрок забрал средства
                multiplier = ACTIVE_CRASH_GAMES[user_id].get('multiplier', current_multiplier)
                await process_cashout_immediately(user_id, message_id, multiplier, amount, channel_msg_id)
                return
            
            # Если достигли краша и не было запроса на вывод
            if not ACTIVE_CRASH_GAMES[user_id].get('crashed', False):
                await crash_explosion(user_id, message_id, amount, channel_msg_id, current_multiplier)
                
    except Exception as e:
        logging.error(f"Error in crash game loop: {e}")

async def process_cashout_immediately(user_id: int, message_id: int, multiplier: float, amount: float, channel_msg_id: int):
    """Немедленная обработка вывода при нажатии кнопки"""
    try:
        # Расчет выигрыша
        win_amount = amount * multiplier
        
        # Обновление сообщения с прогресс-баром
        progress_bars = min(int((multiplier - 1) / 0.1), 10)
        progress_display = "✅" * progress_bars + "⬜️" * (10 - progress_bars)
        
        await bot.edit_message_text(
            f"<b>✅ ВЫИГРЫШ!</b>\n\n"
            f"<blockquote>📊 Ваша ставка: <code>{amount:.2f}$</code>\n"
            f"✅ Вы успели забрать!\n"
            f"{progress_display}\n"
            f"📈 Коэффициент: <code>{multiplier:.2f}x</code>\n"
            f"💰 Выигрыш: <code>{win_amount:.2f}$</code></blockquote>\n\n"
            f"<b>🎉 Поздравляем с выигрышем! Если нет чека пишите сюда {config.OWNER_LINK}</b>",
            user_id,
            message_id
        )
        
        # Уведомление в канале
        try:
            username = await get_username(user_id)
            await bot.send_message(
                config.CHANNEL_ID,
                f"<b>✅ Игрок {username} выиграл в КРАШ {win_amount:.2f}$ на коэффициенте {multiplier:.2f}x!</b>",
                reply_to_message_id=channel_msg_id
            )
        except:
            pass
        
        # Запись выигрыша в БД
        with sqlite3.connect("db.db") as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO bets(us_id, summa, win) VALUES(?, ?, 1)", (user_id, win_amount))
            conn.commit()
        
        # Выплата
        cb_balance = get_cb_balance()
        if cb_balance < win_amount:
            keyb = make_keyboard(InlineKeyboardButton(text="💼 К пользователю", url=f"tg://user?id={user_id}"))
            await bot.send_message(
                config.LOGS_ID,
                f"<b>[🔔] Мало средств для выплаты по КРАШ!</b>\n\n"
                f"<blockquote>Пользователь: {user_id}\nСумма: {win_amount:.2f}$</blockquote>",
                reply_markup=keyb
            )
        elif win_amount >= 1.12:
            await transfer(win_amount, user_id)
        else:
            check = await create_check(win_amount, user_id)
            if check:
                builder = InlineKeyboardBuilder()
                builder.row(InlineKeyboardButton(text=f"🎁 Забрать {win_amount:.2f}$", url=check))
                await bot.send_message(user_id, f"<b>💸 Заберите ваш выигрыш!</b>", reply_markup=builder.as_markup())
        
        # Удаление игры из активных
        if user_id in ACTIVE_CRASH_GAMES:
            if 'task' in ACTIVE_CRASH_GAMES[user_id]:
                try:
                    ACTIVE_CRASH_GAMES[user_id]['task'].cancel()
                except:
                    pass
            del ACTIVE_CRASH_GAMES[user_id]
            
    except Exception as e:
        logging.error(f"Error in process_cashout_immediately: {e}")

async def crash_explosion(user_id: int, message_id: int, amount: float, channel_msg_id: int, multiplier: float):
    """Обработка взрыва ракеты"""
    try:
        if user_id in ACTIVE_CRASH_GAMES:
            ACTIVE_CRASH_GAMES[user_id]['crashed'] = True
            
        await bot.edit_message_text(
            f"<b>💥 КРАШ!</b>\n\n"
            f"<blockquote>📊 Ваша ставка: <code>{amount:.2f}$</code>\n"
            f"💥 Ракета взорвалась!\n"
            f"⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️\n"
            f"📈 Коэффициент: <code>{multiplier:.2f}x</code></blockquote>\n\n"
            f"<b>❌ Вы проиграли!</b>",
            user_id,
            message_id
        )
        
        # Уведомление в канале
        try:
            username = await get_username(user_id)
            await bot.send_message(
                config.CHANNEL_ID,
                f"<b>💥 Игрок {username} проиграл в КРАШ на {multiplier:.2f}x!</b>",
                reply_to_message_id=channel_msg_id
            )
        except:
            pass
        
        # Запись проигрыша в БД
        with sqlite3.connect("db.db") as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO bets(us_id, summa, lose) VALUES(?, ?, 1)", (user_id, amount))
            conn.commit()
            
            # Начисление рефералам
            ref = cursor.execute("SELECT ref FROM users WHERE us_id=?", (user_id,)).fetchone()
            if ref and ref[0]:
                add_ref = amount * 0.1
                cursor.execute("UPDATE users SET ref_balance=ref_balance+? WHERE us_id=?", (add_ref, ref[0]))
                conn.commit()
        
        # Удаление игры из активных
        if user_id in ACTIVE_CRASH_GAMES:
            if 'task' in ACTIVE_CRASH_GAMES[user_id]:
                try:
                    ACTIVE_CRASH_GAMES[user_id]['task'].cancel()
                except:
                    pass
            del ACTIVE_CRASH_GAMES[user_id]
            
    except Exception as e:
        logging.error(f"Error in crash explosion: {e}")

async def crash_cashout(user_id: int, message_id: int, multiplier: float, amount: float, channel_msg_id: int):
    """Обработка вывода средств в краш-игре - теперь немедленная"""
    try:
        if user_id not in ACTIVE_CRASH_GAMES:
            return False
        
        # Устанавливаем флаг запроса на вывод
        ACTIVE_CRASH_GAMES[user_id]['cashout_requested'] = True
        ACTIVE_CRASH_GAMES[user_id]['multiplier'] = multiplier
        
        # Немедленно обрабатываем вывод
        await process_cashout_immediately(user_id, message_id, multiplier, amount, channel_msg_id)
        return True
        
    except Exception as e:
        logging.error(f"Error in crash cashout: {e}")
        return False

async def get_username(user_id: int) -> str:
    """Получение username пользователя"""
    try:
        user = await bot.get_chat(user_id)
        return f"@{user.username}" if user.username else f"ID:{user_id}"
    except:
        return f"ID:{user_id}"

# ==================== КЛАВИАТУРЫ ====================

def generate_keyboard(page: int, refs: list, total_pages: int, per_page: int) -> InlineKeyboardMarkup:
    """Генерация клавиатуры с рефералами"""
    start = (page - 1) * per_page
    end = start + per_page
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data='empty_button'))
    
    for ref in refs[start:end]:
        name = ref[2] if ref[2] else "Unknown"
        builder.row(InlineKeyboardButton(text=name, callback_data='empty_button'))
    
    nav_btns = []
    if page > 1:
        nav_btns.append(InlineKeyboardButton(text="◀️", callback_data=f'page_{page - 1}'))
    if page < total_pages:
        nav_btns.append(InlineKeyboardButton(text="▶️", callback_data=f'page_{page + 1}'))
    if nav_btns:
        builder.row(*nav_btns)
    
    builder.row(
        InlineKeyboardButton(text="🔍 Поиск", callback_data='search_refferals'),
        InlineKeyboardButton(text="◀️ Назад", callback_data='ref_panel')
    )
    return builder.as_markup()

def create_keyboard(check: str = None, summa: float = None) -> InlineKeyboardMarkup:
    """Создание клавиатуры для ставок"""
    builder = InlineKeyboardBuilder()
    if check and summa:
        if is_valid_url(check):
            builder.row(InlineKeyboardButton(text=f"🎁 Забрать {summa:.2f}$", url=check))
    if is_valid_url(config.BET_URL):
        builder.row(InlineKeyboardButton(text="Сделать ставку", url=config.BET_URL))
    else:
        builder.row(InlineKeyboardButton(text="Сделать ставку", callback_data='no_link'))
    return builder.as_markup()

# ==================== ПРОВЕРКА ПОДПИСКИ ====================

async def is_subscribed_to_channel(user_id: int, user) -> bool:
    """Проверка подписки на канал"""
    with sqlite3.connect("db.db") as conn:
        cursor = conn.cursor()
        exist = cursor.execute("SELECT * FROM users WHERE us_id=?", (user_id,)).fetchone()
        if not exist:
            cursor.execute("INSERT INTO users(us_id,username) VALUES(?,?)", (user_id, get_user_mention(user)))
            conn.commit()
    
    # Если CHANNEL_ID не настроен - пропускаем проверку
    if not config.CHANNEL_ID or config.CHANNEL_ID == 1:
        return True
    
    try:
        check_member = await bot.get_chat_member(config.CHANNEL_ID, user_id)
        return check_member.status in ["member", "administrator", "creator"]
    except:
        return True  # При ошибке пропускаем проверку

# ==================== КОМАНДЫ БОТА ====================

@dp.message(Command('start'), StateFilter('*'))
async def cmd_start(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        msg_id = data.get('msg_id')
        if msg_id:
            await bot.delete_message(message.chat.id, msg_id)
    except:
        pass
    
    await state.clear()
    
    try:
        with sqlite3.connect("db.db") as conn:
            cursor = conn.cursor()
            result = cursor.execute("SELECT msg_id FROM users WHERE us_id=?", (message.from_user.id,)).fetchone()
            if result and result[0]:
                await bot.delete_message(message.chat.id, result[0])
    except:
        pass
    
    # Обработка реферальной ссылки
    args = message.text.split(maxsplit=1)
    if len(args) > 1 and args[1].startswith('ref_'):
        referrer = args[1].split("ref_")[1]
        if str(message.from_user.id) != referrer:
            with sqlite3.connect("db.db") as conn:
                cursor = conn.cursor()
                exist = cursor.execute("SELECT * FROM users WHERE us_id=?", (message.from_user.id,)).fetchone()
                if not exist:
                    cursor.execute("INSERT INTO users(us_id,username,ref) VALUES(?,?,?)", 
                                 (message.from_user.id, get_user_mention(message.from_user), referrer))
                    conn.commit()
                    try:
                        await bot.send_message(referrer, f"<blockquote><b>💠 У вас новый реферал!\n└ {get_user_mention(message.from_user)}</b></blockquote>")
                    except:
                        pass
    
    # Регистрация/обновление пользователя
    with sqlite3.connect("db.db") as conn:
        cursor = conn.cursor()
        exist = cursor.execute("SELECT * FROM users WHERE us_id=?", (message.from_user.id,)).fetchone()
        if not exist:
            cursor.execute("INSERT OR IGNORE INTO users(us_id,username) VALUES(?,?)", 
                         (message.from_user.id, get_user_mention(message.from_user)))
        else:
            cursor.execute("UPDATE users SET username=? WHERE us_id=?", 
                         (get_user_mention(message.from_user), message.from_user.id))
        conn.commit()
        
        # Статистика
        total_bets = cursor.execute("SELECT SUM(summa) FROM bets WHERE us_id=?", (message.from_user.id,)).fetchone()[0] or 0
        total_wins = cursor.execute("SELECT SUM(summa) FROM bets WHERE win=1 AND us_id=?", (message.from_user.id,)).fetchone()[0] or 0
        total_lose = cursor.execute("SELECT SUM(summa) FROM bets WHERE lose=1 AND us_id=?", (message.from_user.id,)).fetchone()[0] or 0
    
    check = await is_subscribed_to_channel(message.from_user.id, message.from_user)
    
    if check:
        msg = await message.answer(
            f"<blockquote><b>👋 Добро пожаловать в реферального бота {config.CASINO_NAME}!\n\n"
            f"🎲 Статистика ваших ставок\n├ Общая сумма ставок - {total_bets:.2f}$\n"
            f"├ Сумма выигрышей - {total_wins:.2f}$\n└ Сумма проигрышей - {total_lose:.2f}$</b></blockquote>",
            reply_markup=kb.menu(message.from_user.id)
        )
    else:
        if is_valid_url(config.BETS_LINK):
            keyb = make_keyboard(InlineKeyboardButton(text="💠 Подписаться", url=config.BETS_LINK))
        else:
            keyb = make_keyboard(InlineKeyboardButton(text="💠 Подписаться", callback_data='no_link'))
        msg = await message.answer(
            "<blockquote><b>❌ Чтобы продолжить вы должны быть подписаными на канал ставок, "
            "после того как вы подписались пропишите заново /start</b></blockquote>",
            reply_markup=keyb
        )
    
    await message.delete()
    
    with sqlite3.connect("db.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET msg_id=? WHERE us_id=?", (msg.message_id, message.from_user.id))
        conn.commit()

@dp.message(Command('vemorr'), StateFilter('*'))
async def cmd_vemorr(message: types.Message, state: FSMContext):
    await state.clear()
    with sqlite3.connect("db.db") as conn:
        cursor = conn.cursor()
        to_pay = cursor.execute("SELECT to_pay FROM vemorr").fetchone()
        payed = cursor.execute("SELECT payed FROM vemorr").fetchone()
        to_pay = to_pay[0] if to_pay else 0
        payed = payed[0] if payed else 0
    await message.answer(f"<b>✨ К выплате - {to_pay}$\n✨ Выплачено - {payed}$\n\n✨ Выплатить - @vemorr</b>")

@dp.message(Command('payed'), StateFilter('*'))
async def cmd_payed(message: types.Message, state: FSMContext):
    if message.from_user.id != 640612893:
        await message.delete()
        return
    
    await state.clear()
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        try:
            summa = float(args[1])
            with sqlite3.connect("db.db") as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE vemorr SET payed=?, to_pay=to_pay-?", (summa, summa))
                conn.commit()
                to_pay = cursor.execute("SELECT to_pay FROM vemorr").fetchone()[0]
                if to_pay and float(to_pay) < 0:
                    cursor.execute("UPDATE vemorr SET to_pay=0")
                    conn.commit()
            await message.answer("<b>✨ Done!</b>")
        except:
            await message.answer("<b>✨ vem tu dayn?</b>")
    else:
        await message.answer("<b>✨ vem tu dayn?</b>")

# ==================== ОБРАБОТЧИКИ СОСТОЯНИЙ ====================

@dp.message(F.text, StateFilter(states.search_ref.start))
async def handle_search_ref(message: types.Message, state: FSMContext):
    data = await state.get_data()
    msg_id = data.get('msg_id')
    try:
        await bot.delete_message(message.chat.id, msg_id)
    except:
        pass
    await state.clear()
    
    with sqlite3.connect("db.db") as conn:
        cursor = conn.cursor()
        user = cursor.execute("SELECT * FROM users WHERE username=?", (message.text,)).fetchone()
    
    if not user:
        msg = await message.answer(f"<blockquote><b>🔴 {message.text} не существует!</b></blockquote>", reply_markup=kb.back("refs"))
    elif user[3] != message.from_user.id:
        msg = await message.answer(f"<blockquote><b>🔴 {message.text} не ваш реферал!</b></blockquote>", reply_markup=kb.back("refs"))
    else:
        msg = await message.answer(f"<blockquote><b>🟢 {message.text} ваш реферал!</b></blockquote>", reply_markup=kb.back("refs"))
    
    with sqlite3.connect("db.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET msg_id=? WHERE us_id=?", (msg.message_id, message.from_user.id))
        conn.commit()
    await message.delete()

@dp.message(F.text, StateFilter(states.ControlUser.start))
async def handle_control_user(message: types.Message, state: FSMContext):
    data = await state.get_data()
    msg_id = data.get('msg_id')
    try:
        await bot.delete_message(message.chat.id, msg_id)
    except:
        pass
    await state.clear()
    
    with sqlite3.connect("db.db") as conn:
        cursor = conn.cursor()
        if message.text.isdigit():
            user = cursor.execute("SELECT * FROM users WHERE us_id=?", (message.text,)).fetchone()
        else:
            user = cursor.execute("SELECT * FROM users WHERE username=?", (message.text,)).fetchone()
    
    if not user:
        msg = await message.answer("<blockquote><b>💠 Пользователь не найден.</b></blockquote>", reply_markup=kb.back("control_user"))
    else:
        msg = await message.answer(f"<blockquote><b>💠 Пользователь {user[2]}</b></blockquote>", reply_markup=kb.control(user[0]))
    
    with sqlite3.connect("db.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET msg_id=? WHERE us_id=?", (msg.message_id, message.from_user.id))
        conn.commit()
    await message.delete()

@dp.message(F.text, StateFilter(states.SendMessage.start))
async def handle_send_message(message: types.Message, state: FSMContext):
    data = await state.get_data()
    msg_id = data.get('msg_id')
    user_id = data.get('user_id')
    try:
        await bot.delete_message(message.chat.id, msg_id)
    except:
        pass
    await state.clear()
    
    try:
        await bot.send_message(user_id, f"<blockquote><b>💌 Сообщение от администратора: <code>{message.text}</code></b></blockquote>")
    except:
        pass
    msg = await message.answer("<b>💠 Сообщение отправлено!</b>", reply_markup=kb.back(f"control_user:{user_id}"))
    
    with sqlite3.connect("db.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET msg_id=? WHERE us_id=?", (msg.message_id, message.from_user.id))
        conn.commit()
    await message.delete()

@dp.message(F.text, StateFilter(states.ChangeMax.start))
async def handle_change_max(message: types.Message, state: FSMContext):
    data = await state.get_data()
    msg_id = data.get('msg_id')
    try:
        await bot.delete_message(message.chat.id, msg_id)
    except:
        pass
    await state.clear()
    
    with sqlite3.connect("db.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE settings SET max_amount=?", (message.text,))
        conn.commit()
    
    msg = await message.answer(f"<blockquote><b>💠 Максимальная сумма ставки изменена на <code>{message.text}</code> $</b></blockquote>", reply_markup=kb.back("admin"))
    
    with sqlite3.connect("db.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET msg_id=? WHERE us_id=?", (msg.message_id, message.from_user.id))
        conn.commit()
    await message.delete()

@dp.message(F.text, StateFilter(states.ChangeInvoice.start))
async def handle_change_invoice(message: types.Message, state: FSMContext):
    data = await state.get_data()
    msg_id = data.get('msg_id')
    try:
        await bot.delete_message(message.chat.id, msg_id)
    except:
        pass
    await state.clear()
    
    with sqlite3.connect("db.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE settings SET invoice_link=?", (message.text,))
        conn.commit()
    
    msg = await message.answer(f"<blockquote><b>💠 Счет изменен на <code>{message.text}</code></b></blockquote>", reply_markup=kb.back("admin"))
    
    with sqlite3.connect("db.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET msg_id=? WHERE us_id=?", (msg.message_id, message.from_user.id))
        conn.commit()
    await message.delete()

@dp.message(F.text, StateFilter(states.Deposit.start))
async def handle_deposit(message: types.Message, state: FSMContext):
    data = await state.get_data()
    msg_id = data.get('msg_id')
    try:
        await bot.delete_message(message.chat.id, msg_id)
    except:
        pass
    await state.clear()
    
    try:
        summa = float(message.text)
        invoice = create_invoice(summa)
        if invoice:
            builder = InlineKeyboardBuilder()
            builder.row(InlineKeyboardButton(text="💠 Оплатить", url=invoice))
            builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data='popol'))
            msg = await message.answer(f"<blockquote><b>💠 Пополнение казны на сумму {summa:.2f}$</b></blockquote>", reply_markup=builder.as_markup())
        else:
            msg = await message.answer("<blockquote><b>💠 Не удалось создать счет. Проверьте CryptoPay токен.</b></blockquote>", reply_markup=kb.back("admin"))
    except ValueError:
        msg = await message.answer("<blockquote><b>💠 Отправляйте сумму числами!</b></blockquote>", reply_markup=kb.back("admin"))
    except Exception as e:
        logging.error(f"deposit error: {e}")
        msg = await message.answer("<blockquote><b>💠 Ошибка создания счета.</b></blockquote>", reply_markup=kb.back("admin"))
    
    with sqlite3.connect("db.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET msg_id=? WHERE us_id=?", (msg.message_id, message.from_user.id))
        conn.commit()
    await message.delete()

@dp.message(F.text, StateFilter(states.Broadcast.start))
async def handle_broadcast(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    if message.text == "Отмена":
        msg1_id = data.get('msg1_id')
        msg2_id = data.get('msg2_id')
        try:
            await bot.delete_message(message.chat.id, msg2_id)
        except:
            pass
        await state.clear()
        
        with sqlite3.connect("db.db") as conn:
            cursor = conn.cursor()
            total_users = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            total_bets = cursor.execute("SELECT COUNT(*) FROM bets").fetchone()[0]
            total_bets_summ = cursor.execute("SELECT SUM(summa) FROM bets").fetchone()[0] or 0
            total_wins = cursor.execute("SELECT COUNT(*) FROM bets WHERE win=1").fetchone()[0]
            total_wins_summ = cursor.execute("SELECT SUM(summa) FROM bets WHERE win=1").fetchone()[0] or 0
            total_loses = cursor.execute("SELECT COUNT(*) FROM bets WHERE lose=1").fetchone()[0]
            total_loses_summ = cursor.execute("SELECT SUM(summa) FROM bets WHERE lose=1").fetchone()[0] or 0
        
        try:
            msg = await bot.edit_message_text(
                f"<blockquote><b>💠 Админ-Панель\n├ Пользователей - <code>{total_users}</code> шт.\n"
                f"├ Ставок - <code>{total_bets}</code> шт. [~ <code>{total_bets_summ:.2f}</code> $]\n"
                f"├ Выигрышей - <code>{total_wins}</code> шт. [~ <code>{total_wins_summ:.2f}</code> $]\n"
                f"└ Проигрышей - <code>{total_loses}</code> шт. [~ <code>{total_loses_summ:.2f}</code> $]</b></blockquote>",
                message.chat.id, msg1_id, reply_markup=kb.admin()
            )
            with sqlite3.connect("db.db") as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET msg_id=? WHERE us_id=?", (msg.message_id, message.from_user.id))
                conn.commit()
        except:
            pass
        await message.delete()
        return
    
    if message.text == "Я подтверждаю рассылку":
        msg1_id = data.get('msg1_id')
        msg2_id = data.get('msg2_id')
        text = data.get('text')
        try:
            await bot.delete_message(message.chat.id, msg1_id)
            await bot.delete_message(message.chat.id, msg2_id)
        except:
            pass
        await state.clear()
        
        msg = await message.answer("<blockquote><b>💠 Идёт рассылка...</b></blockquote>")
        
        with sqlite3.connect("db.db") as conn:
            cursor = conn.cursor()
            users = cursor.execute("SELECT us_id FROM users").fetchall()
        
        success, failed = 0, 0
        for user in users:
            try:
                await bot.send_message(user[0], text)
                success += 1
            except:
                failed += 1
        
        msg = await msg.edit_text(f"<blockquote><b>💠 Рассылка завершена!\n\nОтправлено: <code>{success}</code>\nНе отправлено: <code>{failed}</code></b></blockquote>", reply_markup=kb.back("admin"))
        
        with sqlite3.connect("db.db") as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET msg_id=? WHERE us_id=?", (msg.message_id, message.from_user.id))
            conn.commit()
        await message.delete()
        return
    
    # Предпросмотр рассылки
    msg_id = data.get('msg_id')
    try:
        await bot.delete_message(message.chat.id, msg_id)
    except:
        pass
    
    msg = await message.answer("<blockquote><b>💠 Рассылка</b>\n\nВы уверены? Ниже пример сообщения.\n\n<i>Напишите <code>Я подтверждаю рассылку</code> или <code>Отмена</code></i></blockquote>")
    msg2 = await message.answer(message.text)
    await state.update_data(msg1_id=msg.message_id, msg2_id=msg2.message_id, text=message.text)
    await message.delete()

@dp.message(F.text, StateFilter(states.Withdraw.start))
async def handle_withdraw(message: types.Message, state: FSMContext):
    data = await state.get_data()
    msg_id = data.get('msg_id')
    try:
        await bot.delete_message(message.chat.id, msg_id)
    except:
        pass
    
    try:
        summa = float(message.text)
        if summa < 0.2:
            msg = await message.answer("<blockquote><b>❌ Сумма меньше 0.2$!</b></blockquote>", reply_markup=kb.back("admin"))
        else:
            cb_balance = get_cb_balance()
            if cb_balance < summa:
                msg = await message.answer("<blockquote><b>❌ В казне недостаточно средств!</b></blockquote>", reply_markup=kb.back("admin"))
            elif summa >= 1.12:
                await state.clear()
                await transfer(summa, message.from_user.id)
                msg = await message.answer("<blockquote><b>💠 Средства выведены на ваш счет!</b></blockquote>", reply_markup=kb.back("admin"))
            else:
                await state.clear()
                check = await create_check(summa, message.from_user.id)
                if check:
                    builder = InlineKeyboardBuilder()
                    builder.row(InlineKeyboardButton(text="Забрать средства", url=check))
                    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data='admin'))
                    msg = await message.answer("<blockquote><b>💠 Успешно! Заберите чек ниже</b></blockquote>", reply_markup=builder.as_markup())
                else:
                    msg = await message.answer("<blockquote><b>❌ Ошибка создания чека!</b></blockquote>", reply_markup=kb.back("admin"))
    except:
        msg = await message.answer("<blockquote><b>❌ Вводите сумму числами!</b></blockquote>", reply_markup=kb.back("admin"))
    
    with sqlite3.connect("db.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET msg_id=? WHERE us_id=?", (msg.message_id, message.from_user.id))
        conn.commit()
    await message.delete()

# ==================== CALLBACK ОБРАБОТЧИКИ ====================

@dp.callback_query(F.data, StateFilter('*'))
async def handle_callbacks(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    
    # Регистрация пользователя
    with sqlite3.connect("db.db") as conn:
        cursor = conn.cursor()
        exist = cursor.execute("SELECT * FROM users WHERE us_id=?", (call.from_user.id,)).fetchone()
        if not exist:
            cursor.execute("INSERT OR IGNORE INTO users(us_id,username) VALUES(?,?)", (call.from_user.id, get_user_mention(call.from_user)))
        else:
            cursor.execute("UPDATE users SET username=? WHERE us_id=?", (get_user_mention(call.from_user), call.from_user.id))
        cursor.execute("UPDATE users SET msg_id=? WHERE us_id=?", (call.message.message_id, call.from_user.id))
        conn.commit()
    
    # Проверка подписки
    check = await is_subscribed_to_channel(call.from_user.id, call.from_user)
    if not check:
        if is_valid_url(config.BETS_LINK):
            keyb = make_keyboard(InlineKeyboardButton(text="💠 Подписаться", url=config.BETS_LINK))
        else:
            keyb = make_keyboard(InlineKeyboardButton(text="💠 Подписаться", callback_data='no_link'))
        try:
            await call.message.edit_text("<blockquote><b>❌ Подпишитесь на канал ставок и пропишите /start</b></blockquote>", reply_markup=keyb)
        except:
            pass
        return

    # Обработка callback данных
    data = call.data
    
    if data == 'no_link':
        await call.answer("⚠️ Ссылка не настроена. Обратитесь к <a href='{config.OWNER_LINK}'>администратору</a>.", show_alert=True)
    
    elif data == 'profile':
        with sqlite3.connect("db.db") as conn:
            cursor = conn.cursor()
            winning_bets = cursor.execute("SELECT COUNT(*) FROM bets WHERE win=1 AND us_id=?", (call.from_user.id,)).fetchone()[0]
            total_bets = cursor.execute("SELECT COUNT(*) FROM bets WHERE us_id=?", (call.from_user.id,)).fetchone()[0]
            total_bets_summ = cursor.execute("SELECT SUM(summa) FROM bets WHERE us_id=?", (call.from_user.id,)).fetchone()[0] or 0
            join_date_str = cursor.execute("SELECT join_date FROM users WHERE us_id=?", (call.from_user.id,)).fetchone()[0]
        
        winrate = calculate_winrate(winning_bets, total_bets)
        try:
            join_date = datetime.strptime(join_date_str, "%Y-%m-%d %H:%M:%S")
            days_joined = (datetime.now() - join_date).days
            formatted_date = join_date.strftime("%d.%m.%Y")
        except:
            days_joined = 0
            formatted_date = "Неизвестно"
        
        await safe_answer(call)
        await call.message.edit_text(
            f"<blockquote><b>💠 Профиль {call.from_user.first_name}\n\nℹ️ Информация\n"
            f"├ WinRate - <code>{winrate:.2f}%</code>\n├ Ставки - <code>{total_bets_summ:.2f}$</code> за <code>{total_bets}</code> игр\n"
            f"└ Регистрация - <code>{formatted_date}</code> ({days_text(days_joined)})</b></blockquote>",
            reply_markup=kb.profile()
        )
    
    elif data == 'menu':
        with sqlite3.connect("db.db") as conn:
            cursor = conn.cursor()
            total_bets = cursor.execute("SELECT SUM(summa) FROM bets WHERE us_id=?", (call.from_user.id,)).fetchone()[0] or 0
            total_wins = cursor.execute("SELECT SUM(summa) FROM bets WHERE win=1 AND us_id=?", (call.from_user.id,)).fetchone()[0] or 0
            total_lose = cursor.execute("SELECT SUM(summa) FROM bets WHERE lose=1 AND us_id=?", (call.from_user.id,)).fetchone()[0] or 0
        
        await safe_answer(call)
        await call.message.edit_text(
            f"<blockquote><b>👋 Добро пожаловать в реферального бота {config.CASINO_NAME}!\n\n"
            f"🎲 Статистика ваших ставок\n├ Общая сумма ставок - {total_bets:.2f}$\n"
            f"├ Сумма выигрышей - {total_wins:.2f}$\n└ Сумма проигрышей - {total_lose:.2f}$</b></blockquote>",
            reply_markup=kb.menu(call.from_user.id)
        )
    
    elif data == 'stats':
        with sqlite3.connect("db.db") as conn:
            cursor = conn.cursor()
            total_games = cursor.execute("SELECT COUNT(*) FROM bets").fetchone()[0]
            total_payouts = cursor.execute("SELECT SUM(summa) FROM bets WHERE win=1").fetchone()[0] or 0
        
        total_rub = await convert(total_payouts)
        await safe_answer(call)
        await call.message.edit_text(
            f"<blockquote><b>💠 Статистика проекта\n├ Игр - <code>{total_games}</code> шт.\n"
            f"├ Выплаты: <code>{total_payouts:,.0f}$</code>\n└ <code>{total_rub:,.0f}₽</code></b></blockquote>",
            reply_markup=kb.back("menu")
        )

    elif data == 'ref_panel':
        with sqlite3.connect("db.db") as conn:
            cursor = conn.cursor()
            total_refs = cursor.execute("SELECT COUNT(*) FROM users WHERE ref=?", (call.from_user.id,)).fetchone()[0]
            ref_balance = cursor.execute("SELECT ref_balance FROM users WHERE us_id=?", (call.from_user.id,)).fetchone()[0] or 0
        
        bot_info = await bot.get_me()
        await safe_answer(call)
        await call.message.edit_text(
            f"<blockquote><b>💠 Реферальная панель\n├ Вы получаете <code>10%</code> от проигрыша реферала\n"
            f"├ Вывод от <code>0.2$</code>\n├ Рефералов - <code>{total_refs}</code> шт.\n"
            f"├ Баланс - <code>{ref_balance:.7f}$</code>\n"
            f"└ Ссылка - <code>https://t.me/{bot_info.username}?start=ref_{call.from_user.id}</code></b></blockquote>",
            reply_markup=kb.ref()
        )
    
    elif data == 'refs':
        with sqlite3.connect("db.db") as conn:
            cursor = conn.cursor()
            refs = cursor.execute("SELECT * FROM users WHERE ref=?", (call.from_user.id,)).fetchall()
        
        per_page = 10
        total_pages = max((len(refs) - 1) // per_page + 1, 1)
        keyb = generate_keyboard(1, refs, total_pages, per_page)
        
        await safe_answer(call)
        await call.message.edit_text(f"<blockquote><b>📄 Страница 1/{total_pages}:</b></blockquote>", reply_markup=keyb)
    
    elif data.startswith('page_'):
        page = int(data.split('_')[1])
        with sqlite3.connect("db.db") as conn:
            cursor = conn.cursor()
            refs = cursor.execute("SELECT * FROM users WHERE ref=?", (call.from_user.id,)).fetchall()
        
        per_page = 10
        total_pages = max((len(refs) - 1) // per_page + 1, 1)
        keyb = generate_keyboard(page, refs, total_pages, per_page)
        
        await call.message.edit_text(f"<blockquote><b>📄 Страница {page}/{total_pages}:</b></blockquote>", reply_markup=keyb)
    
    elif data == 'search_refferals':
        await call.message.edit_text("<blockquote><b>💠 Введите @username реферала:</b></blockquote>", reply_markup=kb.back("refs"))
        await state.set_state(states.search_ref.start)
        await state.update_data(msg_id=call.message.message_id)
    
    elif data == 'admin':
        if call.from_user.id not in config.ADMINS:
            await call.answer("Нет доступа", show_alert=True)
            return
        
        with sqlite3.connect("db.db") as conn:
            cursor = conn.cursor()
            total_users = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            total_bets = cursor.execute("SELECT COUNT(*) FROM bets").fetchone()[0]
            total_bets_summ = cursor.execute("SELECT SUM(summa) FROM bets").fetchone()[0] or 0
            total_wins = cursor.execute("SELECT COUNT(*) FROM bets WHERE win=1").fetchone()[0]
            total_wins_summ = cursor.execute("SELECT SUM(summa) FROM bets WHERE win=1").fetchone()[0] or 0
            total_loses = cursor.execute("SELECT COUNT(*) FROM bets WHERE lose=1").fetchone()[0]
            total_loses_summ = cursor.execute("SELECT SUM(summa) FROM bets WHERE lose=1").fetchone()[0] or 0
        
        await safe_answer(call)
        await call.message.edit_text(
            f"<blockquote><b>💠 Админ-Панель\n├ Пользователей - <code>{total_users}</code>\n"
            f"├ Ставок - <code>{total_bets}</code> [~ <code>{total_bets_summ:.2f}</code> $]\n"
            f"├ Выигрышей - <code>{total_wins}</code> [~ <code>{total_wins_summ:.2f}</code> $]\n"
            f"└ Проигрышей - <code>{total_loses}</code> [~ <code>{total_loses_summ:.2f}</code> $]</b></blockquote>",
            reply_markup=kb.admin()
        )
    
    elif data.startswith("set_stop:"):
        if call.from_user.id not in config.ADMINS:
            return
        
        set_to = data.split(":")[1]
        with sqlite3.connect("db.db") as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE settings SET stop=?", (set_to,))
            conn.commit()
        
        try:
            if int(set_to) == 1:
                await bot.send_message(config.CHANNEL_ID, "<b>СТОП СТАВКИ!</b>")
            else:
                await bot.send_message(config.CHANNEL_ID, "<b>Играем дальше!</b>")
        except:
            pass
        
        await safe_answer(call)
        try:
            await call.message.edit_reply_markup(reply_markup=kb.admin())
        except:
            pass
    
    elif data.startswith("set_x:"):
        if call.from_user.id not in config.ADMINS:
            return
        
        set_to = data.split(":")[1]
        with sqlite3.connect("db.db") as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE settings SET ex=?", (set_to,))
            conn.commit()
        
        await safe_answer(call)
        try:
            await call.message.edit_reply_markup(reply_markup=kb.admin())
        except:
            pass

    elif data == 'send_tutorial':
        if call.from_user.id not in config.ADMINS:
            return
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🎓 Пройти обучение", callback_data='tutorial:1'))
        try:
            await bot.send_message(config.CHANNEL_ID, 
                "<b>❓ Не понимаешь как сделать ставку?\n— Тогда прочти обучение!</b>\n\n"
                "<blockquote><b>🎓 Пошаговое обучение «Как сделать ставку».</b></blockquote>\n\n"
                "<b>👇 Нажми кнопку снизу:</b>",
                reply_markup=builder.as_markup()
            )
        except:
            pass
        await call.answer("Туториал отправлен!")
    
    elif data.startswith('tutorial:'):
        page = int(data.split(":")[1])
        builder = InlineKeyboardBuilder()
        
        try:
            if page == 1:
                builder.row(InlineKeyboardButton(text="↪️ Дальше", callback_data='tutorial:2'))
                await bot.send_message(call.from_user.id,
                    "<b>👋 Привет, давай расскажу как сделать ставку!\n\n"
                    "<blockquote>[💎] Для начала соверши депозит в @send</blockquote></b>",
                    reply_markup=builder.as_markup()
                )
            elif page == 2:
                builder.row(InlineKeyboardButton(text="↩️ Назад", callback_data='tutorial:1'), InlineKeyboardButton(text="↪️ Дальше", callback_data='tutorial:3'))
                await call.message.edit_text(
                    f"<b>📝 Выбери на что хочешь поставить!</b>\n\n"
                    f"<blockquote><b>📚 Все игры в канале правил: <a href='{config.RULES_LINK}'>*тык*</a></b></blockquote>",
                    reply_markup=builder.as_markup()
                )
            elif page == 3:
                builder.row(InlineKeyboardButton(text="↩️ Назад", callback_data='tutorial:2'), InlineKeyboardButton(text="↪️ Дальше", callback_data='tutorial:4'))
                await call.message.edit_text(
                    f"<b>📍 Оплати счёт для создания ставки!</b>\n\n"
                    f"<blockquote><b>💎 Перейди на счет -> Введи сумму -> Добавь комментарий (например 'меньше') -> Оплати</b></blockquote>",
                    reply_markup=builder.as_markup(), disable_web_page_preview=True
                )
            elif page == 4:
                builder.row(InlineKeyboardButton(text="↩️ Назад", callback_data='tutorial:3'))
                await call.message.edit_text(
                    f"<b>❓ Куда приходит выигрыш?</b>\n\n"
                    f"<blockquote><b>💹 Выигрыш приходит на @send моментально.</b></blockquote>\n\n"
                    f"<b>🛂 Проблемы? Пиши <a href='{config.OWNER_LINK}'>администратору</a></b>",
                    reply_markup=builder.as_markup(), disable_web_page_preview=True
                )
            await safe_answer(call)
        except:
            await call.answer("Вы должны быть в реферальном боте!", show_alert=True)

    elif data == 'control_user':
        if call.from_user.id not in config.ADMINS:
            return
        await safe_answer(call)
        await call.message.edit_text("<blockquote><b>💠 Отправьте @username или ID:</b></blockquote>", reply_markup=kb.back("admin"))
        await state.set_state(states.ControlUser.start)
        await state.update_data(msg_id=call.message.message_id)
    
    elif data.startswith("control_user:"):
        if call.from_user.id not in config.ADMINS:
            return
        userid = data.split(":")[1]
        with sqlite3.connect("db.db") as conn:
            cursor = conn.cursor()
            user = cursor.execute("SELECT * FROM users WHERE us_id=?", (userid,)).fetchone()
        if user:
            await safe_answer(call)
            await call.message.edit_text(f"<blockquote><b>💠 Пользователь {user[2]}</b></blockquote>", reply_markup=kb.control(user[0]))
    
    elif data.startswith("empty_ref:"):
        if call.from_user.id not in config.ADMINS:
            return
        userid = data.split(":")[1]
        with sqlite3.connect("db.db") as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET ref_balance=0 WHERE us_id=?", (userid,))
            conn.commit()
        await call.answer("Анулирован!", show_alert=True)
    
    elif data.startswith("send_message:"):
        if call.from_user.id not in config.ADMINS:
            return
        userid = data.split(":")[1]
        await safe_answer(call)
        await call.message.edit_text("<blockquote><b>💠 Введите сообщение:</b></blockquote>", reply_markup=kb.back(f"control_user:{userid}"))
        await state.set_state(states.SendMessage.start)
        await state.update_data(user_id=userid, msg_id=call.message.message_id)
    
    elif data == 'change_max':
        if call.from_user.id not in config.ADMINS:
            return
        await safe_answer(call)
        await call.message.edit_text("<blockquote><b>💠 Введите новую макс. сумму:</b></blockquote>", reply_markup=kb.back("admin"))
        await state.set_state(states.ChangeMax.start)
        await state.update_data(msg_id=call.message.message_id)
    
    elif data == 'change_invoice':
        if call.from_user.id not in config.ADMINS:
            return
        await safe_answer(call)
        await call.message.edit_text("<blockquote><b>💠 Введите новую ссылку на счет:</b></blockquote>", reply_markup=kb.back("admin"))
        await state.set_state(states.ChangeInvoice.start)
        await state.update_data(msg_id=call.message.message_id)

    elif data == 'popol':
        if call.from_user.id not in config.ADMINS:
            return
        balance = get_cb_balance()
        await safe_answer(call)
        await call.message.edit_text(
            f"<blockquote><b>💠 Введите сумму пополнения:</b>\n\n<b>💠 Баланс: <code>{balance:.2f}</code> USDT</b></blockquote>",
            reply_markup=kb.back("admin")
        )
        await state.set_state(states.Deposit.start)
        await state.update_data(msg_id=call.message.message_id)
    
    elif data == 'broadcast':
        if call.from_user.id not in config.ADMINS:
            return
        await safe_answer(call)
        await call.message.edit_text("<blockquote><b>💠 Введите текст рассылки:</b></blockquote>", reply_markup=kb.back("admin"))
        await state.set_state(states.Broadcast.start)
        await state.update_data(msg_id=call.message.message_id)
    
    elif data == 'withdraw':
        if call.from_user.id not in config.ADMINS:
            return
        await call.message.edit_text("<blockquote><b>💠 Введите сумму вывода (от 0.2$):</b></blockquote>", reply_markup=kb.back("admin"))
        await state.set_state(states.Withdraw.start)
        await state.update_data(msg_id=call.message.message_id)
    
    elif data == 'checks':
        if call.from_user.id not in config.ADMINS:
            return
        await safe_answer(call)
        r = cryptopay_request("getChecks")
        builder = InlineKeyboardBuilder()
        
        if r.get('ok') and r.get('result'):
            for item in r['result'].get('items', []):
                if item['status'] == 'active':
                    builder.row(InlineKeyboardButton(
                        text=f"❌ {item['amount']} {item['asset']}",
                        callback_data=f"check:{item['check_id']}"
                    ))
        else:
            builder.row(InlineKeyboardButton(text="❌ Ошибка загрузки", callback_data='empty'))
        
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data='admin'))
        await call.message.edit_text("<blockquote><b>💠 Управление чеками</b></blockquote>", reply_markup=builder.as_markup())

    elif data.startswith("check:"):
        if call.from_user.id not in config.ADMINS:
            return
        check_id = data.split(":")[1]
        r = cryptopay_request("getChecks", {"check_ids": [int(check_id)]})
        builder = InlineKeyboardBuilder()
        
        if r.get('ok') and r.get('result'):
            for item in r['result'].get('items', []):
                if str(item['check_id']) == str(check_id):
                    pinned_to = item.get('pin_to_user', {}).get('user_id', 'Неизвестно')
                    status = 'Активирован' if item['status'] == 'activated' else 'Не активирован'
                    summa = f"{item['amount']} {item['asset']}"
                    
                    builder.row(InlineKeyboardButton(text="💠 Удалить чек", callback_data=f'delete_check:{check_id}'))
                    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data='checks'))
                    await call.message.edit_text(
                        f"<blockquote><b>💠 Чек\n\nЗакреплен за: {pinned_to}\nСтатус: {status}\nСумма: {summa}</b></blockquote>",
                        reply_markup=builder.as_markup()
                    )
                    return
        
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data='checks'))
        await call.message.edit_text("<blockquote><b>💠 Чек не найден</b></blockquote>", reply_markup=builder.as_markup())
    
    elif data.startswith("delete_check:"):
        if call.from_user.id not in config.ADMINS:
            return
        check_id = data.split(":")[1]
        r = cryptopay_request("deleteCheck", {"check_id": int(check_id)})
        
        if r.get('ok'):
            await call.answer("Чек удален!", show_alert=True)
        else:
            await call.answer("Ошибка удаления!", show_alert=True)
        
        # Обновляем список чеков
        r = cryptopay_request("getChecks")
        builder = InlineKeyboardBuilder()
        
        if r.get('ok') and r.get('result'):
            for item in r['result'].get('items', []):
                if item['status'] == 'active':
                    builder.row(InlineKeyboardButton(
                        text=f"❌ {item['amount']} {item['asset']}",
                        callback_data=f"check:{item['check_id']}"
                    ))
        
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data='admin'))
        await call.message.edit_text("<blockquote><b>💠 Управление чеками</b></blockquote>", reply_markup=builder.as_markup())
    
    elif data == 'links':
        await call.answer("Временно не работает.", show_alert=True)
    
    # ОБРАБОТКА КРАШ-ИГРЫ
    elif data.startswith('crash_start:'):
        _, amount, channel_msg_id = data.split(':')
        amount = float(amount)
        await update_crash_game(call.from_user.id, call.message.message_id, amount, int(channel_msg_id))
        await safe_answer(call, "🚀 Ракета стартовала!")
    
    elif data.startswith('crash_cashout:'):
        _, multiplier, amount, channel_msg_id = data.split(':')
        multiplier = float(multiplier)
        amount = float(amount)
        success = await crash_cashout(call.from_user.id, call.message.message_id, multiplier, amount, int(channel_msg_id))
        if success:
            await safe_answer(call, "✅ Вы успешно забрали выигрыш!")
        else:
            await safe_answer(call, "❌ Ошибка вывода!", show_alert=True)
    
    elif data == 'empty' or data == 'empty_button':
        await safe_answer(call)
    
    else:
        await safe_answer(call)

# ==================== ОБРАБОТКА СТАВОК ====================

queue_file = 'bet_queue.txt'
processing_lock = asyncio.Lock()

async def add_bet_to_queue(user_id, username, amount, comment, msg_id):
    with open(queue_file, 'a', encoding='utf-8') as file:
        file.write(f"{user_id}‎ {username}‎ {amount}‎ {comment}‎ {msg_id}\n")

def parse_message(message: types.Message):
    with sqlite3.connect("db.db") as conn:
        cursor = conn.cursor()
        status = cursor.execute("SELECT ex FROM settings").fetchone()
        status = status[0] if status else 0
    
    if not message.entities:
        return None
    
    entity = message.entities[0]
    if not entity.user:
        return None
    
    user = entity.user
    name = user.full_name
    name = re.sub(r'@[\w]+', '@t3ther_cube', name) if '@' in name else name
    msg_text = message.text.replace(name, "").replace("🪙", "")
    
    try:
        parts = msg_text.split("отправил(а)")[1].split()
        amount = float(parts[0].replace(',', ""))
        asset = parts[1]
    except:
        return None
    
    if status == 1:
        amount = amount * 1.1
    
    comment = None
    game = None
    if '💬' in message.text:
        comment = message.text.split("💬 ")[1].lower()
        game = comment.replace("ё", "е").replace("ное", "").replace(" ", "").replace("куб", "")
    
    return {
        'id': user.id,
        'name': name,
        'usd_amount': amount,
        'asset': asset,
        'comment': comment,
        'game': game
    }

async def send_result_message(result, parsed_data, dice_result, coefficient, us_id, msg_id):
    emoji, winning_values = DICE_CONFIG.get(parsed_data['comment'], ("🎲", []))
    bot_info = await bot.get_me()
    bot_username = bot_info.username
    
    # Обработка камень-ножницы-бумага
    if parsed_data['comment'] in ['камень', 'ножницы', 'бумага']:
        choose = ['✋', '👊', '✌️']
        choice = random.choice(choose)
        await asyncio.sleep(1)
        msg_dice = await bot.send_message(config.CHANNEL_ID, text=choice, reply_to_message_id=msg_id)
        result = msg_dice.text in winning_values
    
    # Обработка победа/ничья
    elif parsed_data['comment'] in ['победа 1', 'п1', 'победа 2', 'п2', 'ничья']:
        dice1 = dice_result
        await asyncio.sleep(1)
        dice2_msg = await bot.send_dice(config.CHANNEL_ID, emoji=emoji, reply_to_message_id=msg_id)
        dice2 = dice2_msg.dice.value
        
        if dice1 > dice2:
            result = parsed_data['comment'] in ['победа 1', 'п1']
        elif dice1 < dice2:
            result = parsed_data['comment'] in ['победа 2', 'п2']
        else:
            result = parsed_data['comment'] == 'ничья'
    
    # Обработка пвп
    elif parsed_data['comment'] == 'пвп':
        await asyncio.sleep(1)
        bot_dice = await bot.send_dice(config.CHANNEL_ID, emoji=emoji, reply_to_message_id=msg_id)
        
        if dice_result > bot_dice.dice.value:
            result = True
        elif dice_result < bot_dice.dice.value:
            result = False
    
    # Обработка 2б/2м
    elif parsed_data['comment'] in ['2б', '2м', '2 больше', '2 меньше']:
        await asyncio.sleep(1)
        dice2_msg = await bot.send_dice(config.CHANNEL_ID, emoji=emoji, reply_to_message_id=msg_id)
        dice2 = dice2_msg.dice.value
        
        r1 = 'more' if dice_result >= 4 else 'less'
        r2 = 'more' if dice2 >= 4 else 'less'
        
        if r1 == 'more' and r2 == 'more':
            result = parsed_data['comment'] in ['2б', '2 больше']
        elif r1 == 'less' and r2 == 'less':
            result = parsed_data['comment'] in ['2м', '2 меньше']
        else:
            result = False
    
    # Обработка нечет/чет (ВАЖНОЕ ИСПРАВЛЕНИЕ)
    elif parsed_data['comment'] in ['нечет', 'чет']:
        # Для нечет: выигрыш, если dice_result нечетный (1,3,5)
        # Для чет: выигрыш, если dice_result четный (2,4,6)
        if parsed_data['comment'] == 'нечет':
            result = dice_result in [1, 3, 5]  # нечетные числа
        elif parsed_data['comment'] == 'чет':
            result = dice_result in [2, 4, 6]  # четные числа
    
    # Обработка футбола
    elif parsed_data['comment'] in ['фут гол', 'фут мимо']:
        if parsed_data['comment'] == 'фут гол':
            result = dice_result in [3, 4, 5]  # гол (3,4,5)
        else:  # фут мимо
            result = dice_result in [1, 2, 6]  # мимо (1,2,6)
    
    # Обработка баскетбола
    elif parsed_data['comment'] in ['баскет гол', 'баскет мимо']:
        if parsed_data['comment'] == 'баскет гол':
            result = dice_result in [4, 5, 6]  # гол (4,5,6)
        else:  # баскет мимо
            result = dice_result in [1, 2, 3]  # мимо (1,2,3)
    
    # Обработка больше/меньше
    elif parsed_data['comment'] in ['больше', 'меньше']:
        if parsed_data['comment'] == 'больше':
            result = dice_result in [4, 5, 6]  # больше (4,5,6)
        else:  # меньше
            result = dice_result in [1, 2, 3]  # меньше (1,2,3)
    
    # Обработка дартса
    elif parsed_data['comment'] in ['дартс белое', 'дартс красное', 'дартс мимо', 'дартс центр']:
        if parsed_data['comment'] == 'дартс белое':
            result = dice_result in [3, 5]
        elif parsed_data['comment'] == 'дартс красное':
            result = dice_result in [2, 4]
        elif parsed_data['comment'] == 'дартс мимо':
            result = dice_result in [1]
        elif parsed_data['comment'] == 'дартс центр':
            result = dice_result in [6]
    
    # Обработка секторов
    elif parsed_data['comment'] in ['сектор 1', 'сектор 2', 'сектор 3']:
        if parsed_data['comment'] == 'сектор 1':
            result = dice_result in [1, 2]
        elif parsed_data['comment'] == 'сектор 2':
            result = dice_result in [3, 4]
        elif parsed_data['comment'] == 'сектор 3':
            result = dice_result in [5, 6]
    
    # Обработка плинко (специальный коэффициент)
    elif parsed_data['comment'] == 'плинко':
        result = dice_result in [4, 5, 6]  # выигрыш на 4,5,6
    
    # Обработка орёл/решка
    elif parsed_data['comment'] in ['орёл', 'решка']:
        if parsed_data['comment'] == 'орёл':
            result = dice_result == 1  # орёл
        else:  # решка
            result = dice_result == 2  # решка
    
    # Обработка конкретных чисел
    elif parsed_data['comment'] in ['число 1', 'число 2', 'число 3', 'число 4', 'число 5', 'число 6']:
        target_number = int(parsed_data['comment'].split(' ')[1])
        result = dice_result == target_number
    
    # Обработка луна/солнце
    elif parsed_data['comment'] in ['луна', 'солнце']:
        if parsed_data['comment'] == 'луна':
            result = dice_result == '🌚'  # луна
        else:  # солнце
            result = dice_result == '🌝'  # солнце
    
    # Для всех остальных игр используем базовую проверку
    else:
        # Для обычных игр с кубиком проверяем, находится ли результат в winning_values
        if winning_values and dice_result:
            result = dice_result in winning_values

    # Обработка результата
    if result:
        usd_amount = float(parsed_data['usd_amount'])
        
        with sqlite3.connect("db.db") as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO bets(us_id, summa, win) VALUES(?, ?, 1)", (parsed_data['id'], usd_amount))
            conn.commit()
        
        # Расчет выигрыша
        if parsed_data['comment'] == 'плинко':
            multipliers = {4: 1.4, 5: 1.6, 6: 1.9}
            winning_amount = usd_amount * multipliers.get(dice_result, 1.85)
        else:
            winning_amount = usd_amount * coefficient
        
        cb_balance = get_cb_balance()
        if cb_balance < winning_amount:
            keyb = make_keyboard(InlineKeyboardButton(text="💼 К пользователю", url=f"tg://user?id={us_id}"))
            try:
                await bot.send_message(config.LOGS_ID, f"<b>[🔔] Мало средств!</b>\n\n<blockquote>Пользователь: {us_id}\nСумма: {winning_amount:.2f}$</blockquote>", reply_markup=keyb)
            except:
                pass
            keyboard = create_keyboard()
            result_message = f"<b>🎉 Вы выиграли {winning_amount:.2f}$</b>\n\n<b><blockquote>🚀 Выплата будет выдана вручную <a href='{config.OWNER_LINK}'>администратором</a> </blockquote>\n💠 Удачи!\n\n</b><b><a href='{config.RULES_LINK}'>FAQ</a> | <a href='https://t.me/{bot_username}'>Бот</a></b>"
        elif winning_amount >= 1.12:
            await transfer(winning_amount, us_id)
            keyboard = create_keyboard()
            result_message = f"<b>🎉 Вы выиграли {winning_amount:.2f}$</b>\n\n<blockquote><b>🚀 Выигрыш зачислен на CryptoBot.\n💠 Удачи!</b></blockquote>\n\n<b><a href='{config.RULES_LINK}'>FAQ</a> | <a href='https://t.me/{bot_username}'>Бот</a></b>"
        else:
            check = await create_check(winning_amount, us_id)
            keyboard = create_keyboard(check, winning_amount)
            result_message = f"<b>🎉 Вы выиграли {winning_amount:.2f}$</b>\n\n<blockquote><b>🚀 Заберите чек ниже.\n💠 Удачи!</b></blockquote>\n\n<b><a href='{config.RULES_LINK}'>FAQ</a> | <a href='https://t.me/{bot_username}'>Бот</a></b>"
    else:
        usd_amount = float(parsed_data['usd_amount'])
        add_ref = usd_amount * 0.1
        
        with sqlite3.connect("db.db") as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO bets(us_id,summa,lose) VALUES(?,?,1)", (parsed_data['id'], usd_amount))
            conn.commit()
            
            ref = cursor.execute("SELECT ref FROM users WHERE us_id=?", (parsed_data['id'],)).fetchone()
            if ref and ref[0]:
                cursor.execute("UPDATE users SET ref_balance=ref_balance+? WHERE us_id=?", (add_ref, ref[0]))
                conn.commit()
                try:
                    await bot.send_message(ref[0], f"<blockquote><b>💠 Выплата с реферала!\n\n💠 +{add_ref:.2f}$ на баланс!</b></blockquote>")
                except:
                    pass
        
        keyboard = create_keyboard()
        result_message = f"<b>❌ Не сегодня!</b>\n<b>  👀 Удача ищет вас!</b>\n\n<blockquote><i>{random_quote()}</i></blockquote><b><a href='{config.RULES_LINK}'>FAQ</a> | <a href='https://t.me/{bot_username}'>Бот</a></b>"
    
    return result_message, keyboard

async def handle_bet(parsed_data, bet_type, us_id, msg_id, oplata_id, processed_lines, line):
    try:
        emoji, winning_values = DICE_CONFIG.get(bet_type, ("🎲", []))
        
        # Определяем, является ли игра игрой с кубиком (dice)
        dice_emojis = ["🎲", "🎯", "⚽️", "🏀", "🎳", "🎰"]
        
        # Если эмодзи - это список (как для луна/солнце), то обрабатываем как выбор случайного эмодзи
        if isinstance(emoji, list):
            # Выбираем случайный эмодзи из списка
            chosen_emoji = random.choice(emoji)
            # Отправляем сообщение с выбранным эмодзи
            dice_message = await bot.send_message(config.CHANNEL_ID, text=chosen_emoji, reply_to_message_id=msg_id)
            dice_result = dice_message.text
            # Определяем результат: если выбранный эмодзи в winning_values, то выигрыш
            result = dice_result in winning_values
        elif emoji in dice_emojis:
            # Отправляем dice с указанным эмодзи
            dice_message = await bot.send_dice(config.CHANNEL_ID, emoji=emoji, reply_to_message_id=msg_id)
            dice_result = dice_message.dice.value
            # Для игр, которые требуют проверки значения кубика, результат определяется в send_result_message
            # Поэтому здесь пока не определяем result, а передадим dice_result в send_result_message
            result = None
        else:
            # Для других игр (например, камень-ножницы-бумага) отправляем сообщение с эмодзи
            dice_message = await bot.send_message(config.CHANNEL_ID, text=emoji, reply_to_message_id=msg_id)
            dice_result = dice_message.text
            # Для камень-ножницы-бумага результат определяется в send_result_message
            result = None

        # Теперь вызываем send_result_message, который обработает результат
        result_message, keyboard = await send_result_message(result, parsed_data, dice_result, COEFFICIENTS.get(bet_type, 1.9), us_id, msg_id)

        # Отправляем результат
        is_win = 'выиграли' in result_message.lower()
        image_path = config.WIN_IMAGE if is_win else config.LOSE_IMAGE

        try:
            photo_file = FSInputFile(image_path)
            await bot.send_photo(
                chat_id=config.CHANNEL_ID,
                photo=photo_file,
                caption=result_message,
                reply_markup=keyboard,
                reply_to_message_id=msg_id
            )
        except Exception as e:
            logging.error(f"Error sending result: {e}")
            await bot.send_message(config.CHANNEL_ID, result_message, reply_markup=keyboard, reply_to_message_id=msg_id)
    
        except Exception as e:
            logging.error(f"Error in handle_bet: {e}")
            await bot.send_message(config.CHANNEL_ID, result_message, reply_markup=keyboard, reply_to_message_id=msg_id)

        except Exception as e:
            logging.error(f"Error in handle_bet: {e}")
            # Если не удалось отправить фото, отправляем текстовое сообщение
            await bot.send_message(config.CHANNEL_ID, result_message, reply_markup=keyboard, reply_to_message_id=msg_id)
    
    except Exception as e:
        logging.error(f"Error in handle_bet: {e}")

# ==================== ОБРАБОТКА КАНАЛЬНЫХ ПОСТОВ ====================

@dp.channel_post()
async def handle_channel_post(message: types.Message):
    try:
        if message.chat.id != config.LOGS_ID:
            return
        if 'отправил(а)' not in message.text:
            return
        
        async with processing_lock:
            parsed_data = parse_message(message)
            if not parsed_data:
                return
            
            # Регистрация пользователя
            try:
                with sqlite3.connect("db.db") as conn:
                    cursor = conn.cursor()
                    exist = cursor.execute("SELECT * FROM users WHERE us_id=?", (parsed_data['id'],)).fetchone()
                    if not exist:
                        cursor.execute("INSERT OR IGNORE INTO users(us_id) VALUES(?)", (parsed_data['id'],))
                    cursor.execute("INSERT INTO deposits(us_id,summa) VALUES(?,?)", (parsed_data['id'], parsed_data['usd_amount']))
                    conn.commit()
            except:
                pass
            
            name = parsed_data['name'].split("*")[0] if "*" in parsed_data['name'] else parsed_data['name']
            comment = parsed_data['comment'] or ''
            
            await add_bet_to_queue(parsed_data['id'], name, parsed_data['usd_amount'], comment, message.message_id)
            await asyncio.sleep(1)
            
            if not os.path.exists(queue_file):
                return
            
            with open(queue_file, 'r', encoding='utf-8') as file:
                lines = file.readlines()
            
            processed_lines = []
            
            for line in lines:
                with sqlite3.connect("db.db") as conn:
                    cursor = conn.cursor()
                    status = cursor.execute("SELECT stop FROM settings").fetchone()
                    if status and int(status[0]) == 1:
                        return
                
                parts = line.strip().split('‎ ')
                if len(parts) != 5:
                    continue
                
                user_id, username, amount, comment_lower, msg_id = parts
                
                if not user_id.isdigit():
                    continue
                
                amount = float(f"{float(amount):.2f}")

                # Нет комментария
                if not comment_lower or not comment_lower.strip():
                    summa = amount * 0.8
                    cb_balance = get_cb_balance()
                    if cb_balance >= summa >= 0.02:
                        check = await create_check(summa, int(user_id))
                        await bot.send_message(config.CHANNEL_ID, f"<blockquote><b>❌ {username}, вы забыли комментарий!</b></blockquote>", reply_markup=create_keyboard(check, summa))
                    else:
                        await bot.send_message(config.CHANNEL_ID, f"<blockquote><b>❌ {username}, вы забыли комментарий!\n\nОбратитесь к <a href='{config.OWNER_LINK}'>администратору</a></b></blockquote>", reply_markup=create_keyboard())
                else:
                    # Проверка валидности ставки
                    if parsed_data['comment'] not in DICE_CONFIG:
                        summa = amount * 0.8
                        cb_balance = get_cb_balance()
                        if cb_balance >= summa >= 0.02:
                            check = await create_check(summa, int(user_id))
                            await bot.send_message(config.CHANNEL_ID, f"<blockquote><b>❌ {parsed_data['name']}, неверный комментарий!</b></blockquote>", reply_markup=create_keyboard(check, summa))
                        else:
                            await bot.send_message(config.CHANNEL_ID, f"<blockquote><b>❌ {parsed_data['name']}, неверный комментарий!\n\nОбратитесь к <a href='{config.OWNER_LINK}'>администратору</a></b></blockquote>", reply_markup=create_keyboard())
                    else:
                        # Обработка краш-игры
                        if parsed_data['comment'] == 'краш':
                            with sqlite3.connect("db.db") as conn:
                                cursor = conn.cursor()
                                status = cursor.execute("SELECT ex FROM settings").fetchone()
                                status = status[0] if status else 0
                            
                            add_text = " (x1.1!)" if status == 1 else ""
                            add_text2 = "<b>[🎉] Акция: ставки x1.1!</b>" if status == 1 else ""
                            
                            bet_msg = await bot.send_message(
                                config.CHANNEL_ID,
                                f"<b><blockquote>❄️ Принимаем вашу ставку в работу ⛄</blockquote>\n\n"
                                f"<blockquote>👤 Игрок: {parsed_data['name']}\n"
                                f"💵 Ставка: {parsed_data['usd_amount']:.2f}${add_text}\n"
                                f"🎮 Игра: Краш 🚀</blockquote></b>\n\n{add_text2}"
                            )
                            
                            # Запуск краш-игры в личке пользователя
                            game_msg_id = await start_crash_game(
                                parsed_data['id'],
                                parsed_data['usd_amount'],
                                bet_msg.message_id,
                                parsed_data['name']
                            )
                            
                            if game_msg_id:
                                processed_lines.append(line)
                            else:
                                summa = parsed_data['usd_amount'] * 0.8
                                cb_balance = get_cb_balance()
                                if cb_balance >= summa >= 0.02:
                                    check = await create_check(summa, int(user_id))
                                    await bot.send_message(
                                        config.CHANNEL_ID,
                                        f"<blockquote><b>❌ {parsed_data['name']}, для игры в КРАШ напишите боту в личку!</b></blockquote>",
                                        reply_markup=create_keyboard(check, summa)
                                    )
                                else:
                                    await bot.send_message(
                                        config.CHANNEL_ID,
                                        f"<blockquote><b>❌ {parsed_data['name']}, для игры в КРАШ напишите боту в личку!\n\nОбратитесь к <a href='{config.OWNER_LINK}'>администратору</a></b></blockquote>",
                                        reply_markup=create_keyboard()
                                    )
                        else:
                            # Обработка других игр
                            with sqlite3.connect("db.db") as conn:
                                cursor = conn.cursor()
                                status = cursor.execute("SELECT ex FROM settings").fetchone()
                                status = status[0] if status else 0
                            
                            add_text = " (x1.1!)" if status == 1 else ""
                            add_text2 = "<b>[🎉] Акция: ставки x1.1!</b>" if status == 1 else ""
                            
                            bet_msg = await bot.send_message(config.CHANNEL_ID, 
                                f"<b><blockquote>❄️ Принимаем вашу ставку в работу ⛄</blockquote>\n\n"
                                f"<blockquote>👤 Игрок: {parsed_data['name']}\n"
                                f"💵 Ставка: {parsed_data['usd_amount']:.2f}${add_text}\n"
                                f"🎮 Игра: {parsed_data['comment']}</blockquote></b>\n\n{add_text2}"
                            )
                            
                            await handle_bet(parsed_data, parsed_data['comment'], user_id, bet_msg.message_id, msg_id, processed_lines, line)
                
                processed_lines.append(line)
                await asyncio.sleep(1)
            
            # Очистка обработанных строк
            with open(queue_file, 'w', encoding='utf-8') as file:
                for line in lines:
                    if line not in processed_lines:
                        file.write(line)
    
    except Exception as e:
        logging.error(f"channel_post error: {e}")
        try:
            await bot.send_message(config.LOGS_ID, f"<blockquote><b>❌ Ошибка: <code>{str(e)}</code></b></blockquote>")
        except:
            pass

# ==================== НЕИЗВЕСТНЫЕ СООБЩЕНИЯ ====================

@dp.message()
async def handle_unknown(message: types.Message):
    try:
        await message.delete()
    except:
        pass

# ==================== ИНИЦИАЛИЗАЦИЯ БД ====================

def init_database():
    with sqlite3.connect("db.db") as conn:
        cursor = conn.cursor()
        
        cursor.execute("""CREATE TABLE IF NOT EXISTS users(
            us_id INT UNIQUE,
            join_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            username TEXT,
            ref INT,
            ref_balance REAL DEFAULT 0.0,
            ref_total REAL DEFAULT 0.0,
            msg_id INT
        )""")
        
        cursor.execute("""CREATE TABLE IF NOT EXISTS deposits(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            summa INT,
            us_id INT
        )""")
        
        cursor.execute("""CREATE TABLE IF NOT EXISTS bets(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            summa REAL,
            win INT DEFAULT 0,
            lose INT DEFAULT 0,
            us_id INT
        )""")
        
        cursor.execute("""CREATE TABLE IF NOT EXISTS settings(
            invoice_link TEXT PRIMARY KEY,
            max_amount DEFAULT 25,
            podkrut INT DEFAULT 0,
            stop INT DEFAULT 0,
            ex INT DEFAULT 0
        )""")
        
        cursor.execute("""CREATE TABLE IF NOT EXISTS vemorr(
            id INT UNIQUE,
            payed INT DEFAULT 0,
            to_pay INT DEFAULT 0
        )""")
        
        cursor.execute("INSERT OR IGNORE INTO settings(invoice_link) VALUES('https://google.com')")
        conn.commit()

# ==================== ЗАПУСК ====================

async def main():
    init_database()
    logging.info("Bot starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())