import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import re
import os

TOKEN = os.getenv("BOT_TOKEN")
# CHAT_ID = os.getenv("CHAT_ID", "PASTE_CHAT_ID_HERE")
CHAT_ID = None

bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()
reminder_list = []
reminder_jobs = {}

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я бот-напоминалка.\n"
                         "📌 Примеры команд:\n"
                         "/напомни 10 мая в 10:00 оплатить ипотеку\n"
                         "/еженедельно понедельник в 08:30 выбрасывать мусор\n"
                         "/ежемесячно 15 в 12:00 проверить отчеты\n"
                         "/список — посмотреть все активные напоминания\n"
                         "/удалить 2 — удалить напоминание под номером 2")

@dp.message(Command("список"))
async def cmd_list(message: types.Message):
    if not reminder_list:
        await message.answer("Нет активных напоминаний.")
        return
    reply = "📋 Активные напоминания:\n"
    for idx, r in enumerate(reminder_list, start=1):
        reply += f"{idx}. {r}\n"
    await message.answer(reply)

@dp.message(Command("удалить"))
async def delete_reminder(message: types.Message):
    match = re.match(r"/удалить (\d+)", message.text)
    if not match:
        await message.answer("Используй формат: /удалить 1")
        return
    idx = int(match.group(1)) - 1
    if 0 <= idx < len(reminder_list):
        desc = reminder_list.pop(idx)
        job_id = f"reminder_{idx}"
        job = reminder_jobs.pop(job_id, None)
        if job:
            job.remove()
        await message.answer(f"🗑 Напоминание удалено: {desc}")
    else:
        await message.answer("Неверный номер напоминания.")

@dp.message(Command("напомни"))
async def set_reminder(message: types.Message):
    match = re.match(r"/напомни (\d{1,2}) (\w+) в (\d{1,2}:\d{2}) (.+)", message.text, re.IGNORECASE)
    if not match:
        await message.answer("Формат: /напомни 10 мая в 10:00 оплатить ипотеку")
        return

    day, month_str, time_str, task = match.groups()
    months = {
        "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
        "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12
    }
    month = months.get(month_str.lower())
    if not month:
        await message.answer("Неверный месяц.")
        return

    try:
        remind_time = datetime(datetime.now().year, month, int(day), *map(int, time_str.split(":")))
    except Exception:
        await message.answer("Ошибка в дате.")
        return

    description = f"{remind_time.strftime('%d.%m %H:%M')} — {task}"
    reminder_list.append(description)

    job = scheduler.add_job(
        send_reminder,
        trigger=DateTrigger(run_date=remind_time),
        args=[task]
    )
    reminder_jobs[f"reminder_{len(reminder_list)-1}"] = job
    await message.answer(f"✅ Напоминание установлено: {description}")

@dp.message(Command("еженедельно"))
async def weekly_reminder(message: types.Message):
    match = re.match(r"/еженедельно (\w+) в (\d{1,2}:\d{2}) (.+)", message.text, re.IGNORECASE)
    if not match:
        await message.answer("Формат: /еженедельно понедельник в 08:30 выбрасывать мусор")
        return

    weekday_str, time_str, task = match.groups()
    weekdays = {
        "понедельник": "mon", "вторник": "tue", "среда": "wed",
        "четверг": "thu", "пятница": "fri", "суббота": "sat", "воскресенье": "sun"
    }
    weekday = weekdays.get(weekday_str.lower())
    if not weekday:
        await message.answer("Неверный день недели.")
        return

    hour, minute = map(int, time_str.split(":"))
    description = f"Еженедельно ({weekday_str.title()} в {time_str}) — {task}"
    reminder_list.append(description)

    job = scheduler.add_job(
        send_reminder,
        trigger=CronTrigger(day_of_week=weekday, hour=hour, minute=minute),
        args=[f"(еженедельно) {task}"]
    )
    reminder_jobs[f"reminder_{len(reminder_list)-1}"] = job
    await message.answer(f"✅ Еженедельное напоминание установлено: {description}")

@dp.message(Command("ежемесячно"))
async def monthly_reminder(message: types.Message):
    match = re.match(r"/ежемесячно (\d{1,2}) в (\d{1,2}:\d{2}) (.+)", message.text, re.IGNORECASE)
    if not match:
        await message.answer("Формат: /ежемесячно 15 в 12:00 проверить отчеты")
        return

    day, time_str, task = match.groups()
    hour, minute = map(int, time_str.split(":"))
    description = f"Ежемесячно (день {day} в {time_str}) — {task}"
    reminder_list.append(description)

    job = scheduler.add_job(
        send_reminder,
        trigger=CronTrigger(day=day, hour=hour, minute=minute),
        args=[f"(ежемесячно) {task}"]
    )
    reminder_jobs[f"reminder_{len(reminder_list)-1}"] = job
    await message.answer(f"✅ Ежемесячное напоминание установлено: {description}")

async def send_reminder(task):
    await bot.send_message(CHAT_ID, f"🔔 Напоминание: {task}")

@dp.message()
async def get_chat_id(message: types.Message):
    await message.answer(f"ID этого чата: `{message.chat.id}`", parse_mode="Markdown")

@dp.startup()
async def on_startup(dispatcher: Dispatcher):
    scheduler.start()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
