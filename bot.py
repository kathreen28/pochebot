# PocheBot: Финальный бот-помощник для семьи
# Возможности:
# - Установка напоминаний (в т.ч. голосом)
# - Удаление и изменение напоминаний через кнопки
# - Повторяющиеся напоминания
# - Утреннее сообщение с погодой, курсами, цитатой
# - Сохранение/загрузка из файла

import asyncio, os, json, pytz, dateparser, aiohttp, re
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv
from deep_translator import GoogleTranslator

# === Загрузка окружения ===
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID", 0))
DEFAULT_TZ = "Asia/Vladivostok"
DATA_FILE = "reminders.json"

bot = Bot(token=TOKEN)
dp = Dispatcher()
reminders = []
user_timezones = {}
pending_updates = {}

# === Чтение сохранённых напоминаний ===
def load_reminders():
    global reminders
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            reminders.extend(json.load(f))

def save_reminders():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(reminders, f, ensure_ascii=False, indent=2, default=str)

# === Кнопки выбора часового пояса и меню ===
timezone_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🇷🇺 Владивосток", callback_data="tz_Asia/Vladivostok")],
    [InlineKeyboardButton(text="🇷🇺 Москва", callback_data="tz_Europe/Moscow")],
    [InlineKeyboardButton(text="🇨🇳 Китай", callback_data="tz_Asia/Shanghai")],
    [InlineKeyboardButton(text="🇦🇪 Дубай", callback_data="tz_Asia/Dubai")],
    [InlineKeyboardButton(text="🇹🇭 Таиланд", callback_data="tz_Asia/Bangkok")],
])

menu_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📋 Мои напоминания", callback_data="myreminders")]
])

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Я семейный бот-напоминалка.\n\n"
        "📌 Возможности:\n"
        "• Установка и просмотр напоминаний\n"
        "• Удаление / изменение\n"
        "• Повторяемые напоминания\n"
        "• Утреннее сообщение (погода, курс, цитата)\n"
        "• Работаю даже с голосовыми! 🎙️\n\n"
        "⚙️ Установить часовой пояс: /timezone\n"
        "📋 Или воспользуйтесь кнопкой ниже.",
        reply_markup=menu_keyboard
    )

@dp.callback_query(lambda c: c.data == "myreminders")
async def cb_my_reminders(callback: types.CallbackQuery):
    uid = callback.from_user.id
    user_r = [r for r in reminders if r['user_id'] == uid]
    if not user_r:
        await callback.message.edit_text("📋 У вас пока нет активных напоминаний.")
        return

    for r in user_r:
        dt = datetime.fromisoformat(r['time']).strftime('%d.%m.%Y %H:%M')
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Удалить", callback_data=f"del_{r['id']}")],
            [InlineKeyboardButton(text="✏ Изменить", callback_data=f"edit_{r['id']}")],
        ])
        await callback.message.answer(f"🗓 {dt}\n🔔 {r['text']}", reply_markup=kb)

@dp.message(Command("timezone"))
async def cmd_timezone(message: Message):
    await message.answer("🌍 Выберите ваш часовой пояс:", reply_markup=timezone_keyboard)

@dp.callback_query(lambda c: c.data.startswith("tz_"))
async def set_timezone(callback: types.CallbackQuery):
    tz_name = callback.data[3:]
    user_timezones[callback.from_user.id] = tz_name
    await callback.message.edit_text(f"✅ Часовой пояс установлен: {tz_name}")

# === Установка напоминаний с извлечением даты ===
def extract_datetime(text):
    # Пробуем последовательно обрезать слова с конца
    for i in range(len(text.split()), 1, -1):
        try_part = " ".join(text.split()[:i])
        parsed = dateparser.parse(try_part, languages=["ru"])
        if parsed:
            return parsed, " ".join(text.split()[i:])
    return None, text

@dp.message(F.voice)
async def handle_voice(message: Message):
    await message.answer("🎙️ Голосовое сообщение получено. Распознавание пока не реализовано 🙈")

@dp.message()
async def handle_text(message: Message):
    uid = message.from_user.id
    tz_name = user_timezones.get(uid, DEFAULT_TZ)
    parsed, note = extract_datetime(message.text)
    if parsed:
        if parsed.time() == datetime.min.time():
            parsed = parsed.replace(hour=9, minute=0)
        local = pytz.timezone(tz_name).localize(parsed)
        reminder = {
            "id": f"{uid}_{datetime.now().timestamp()}",
            "chat_id": message.chat.id,
            "user_id": uid,
            "text": note if note else message.text,
            "time": local.isoformat()
        }
        reminders.append(reminder)
        save_reminders()
        await message.answer(f"✅ Напоминание на {local.strftime('%Y-%m-%d %H:%M')} ({tz_name})")
    else:
        await message.answer("Не удалось распознать дату. Пример: 'завтра в 10:00'")

@dp.message(Command("мои_напоминания"))
async def show_reminders(message: Message):
    uid = message.from_user.id
    user_r = [r for r in reminders if r['user_id'] == uid]
    if not user_r:
        return await message.answer("У вас нет активных напоминаний.")
    for r in user_r:
        dt = datetime.fromisoformat(r['time']).strftime('%d.%m.%Y %H:%M')
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Удалить", callback_data=f"del_{r['id']}")],
            [InlineKeyboardButton(text="✏ Изменить", callback_data=f"edit_{r['id']}")],
        ])
        await message.answer(f"🗓 {dt}\n" + f"🔔 {r['text']}", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("del_"))
async def delete_reminder(callback: types.CallbackQuery):
    rid = callback.data[4:]
    global reminders
    reminders = [r for r in reminders if r['id'] != rid]
    save_reminders()
    await callback.message.edit_text("✅ Напоминание удалено")

@dp.callback_query(lambda c: c.data.startswith("edit_"))
async def ask_edit(callback: types.CallbackQuery):
    rid = callback.data[5:]
    pending_updates[callback.from_user.id] = rid
    await callback.message.answer("✏ Напиши новую дату/время для напоминания")

@dp.message(F.text.regexp("\\d+.*") & (lambda m: m.from_user.id in pending_updates))
async def save_edit(message: Message):
    rid = pending_updates.pop(message.from_user.id)
    for r in reminders:
        if r['id'] == rid:
            parsed = dateparser.parse(message.text, languages=["ru"])
            if parsed:
                tz = pytz.timezone(user_timezones.get(r['user_id'], DEFAULT_TZ))
                r['time'] = tz.localize(parsed).isoformat()
                save_reminders()
                return await message.answer("✅ Напоминание обновлено")
    await message.answer("❌ Не удалось обновить напоминание")

async def morning_message():
    try:
        now = datetime.now(pytz.timezone(DEFAULT_TZ)).strftime("%A, %d %B")
        async with aiohttp.ClientSession() as session:
            weather = await (await session.get("https://wttr.in/Khabarovsk?format=%t, %C")).text()
            cur = await (await session.get("https://www.cbr-xml-daily.ru/daily_json.js")).json()
            quote = await (await session.get("https://zenquotes.io/api/today")).json()
            q_text = quote[0]['q']
            q_ru = GoogleTranslator(source='en', target='ru').translate(q_text)
        msg = f"👋 Доброе утро, Почелинцевы!\n\n📅 {now}\n🌦 {weather}\n\n💱 Курсы:\n- USD: {cur['Valute']['USD']['Value']:.2f} ₽\n- EUR: {cur['Valute']['EUR']['Value']:.2f} ₽\n- CNY: {cur['Valute']['CNY']['Value']:.2f} ₽\n\n💬 Цитата дня:\n{q_text}\n📝 {q_ru}"
        if CHAT_ID:
            await bot.send_message(CHAT_ID, msg)
    except Exception as e:
        print("Утро ошибка:", e)

async def reminder_loop():
    while True:
        now = datetime.utcnow().replace(tzinfo=pytz.utc)
        for r in reminders[:]:
            r_dt = datetime.fromisoformat(r['time'])
            if now >= r_dt.astimezone(pytz.utc):
                await bot.send_message(r['chat_id'], f"🔔 Напоминание: {r['text']}")
                reminders.remove(r)
                save_reminders()
        await asyncio.sleep(60)

async def schedule_morning():
    while True:
        now = datetime.now(pytz.timezone(DEFAULT_TZ))
        next_run = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run += timedelta(days=1)
        await asyncio.sleep((next_run - now).total_seconds())
        await morning_message()

async def main():
    load_reminders()
    asyncio.create_task(reminder_loop())
    asyncio.create_task(schedule_morning())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
