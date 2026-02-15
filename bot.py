import os
import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Твой токен
TOKEN = "8377110375:AAG3GmbEpQGyIcfzyOByu6qPUPVbxhYpPSg"

# Фикс URL базы для Render
DB_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DB_URL)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # Тут можно добавить логику регистрации в БД
    await message.answer(
        f"Привет, {message.from_user.first_name}! Это твоя тапалка.",
        reply_markup=get_tap_kb()
    )

# Обработка тапа (клики)
@dp.callback_query(F.data == "tap")
async def handle_tap(callback: types.Callback_query):
    # В идеале здесь должен быть запрос к БД для +1 монеты
    # Для примера просто отвечаем пользователю:
    await callback.answer("Баланс: +1 монета!", show_alert=False)
    
    # Обновляем сообщение (можно выводить текущий баланс)
    await callback.message.edit_text(
        "Продолжай тапать! Твой прогресс сохранен.",
        reply_markup=get_tap_kb()
    )

# ... остальной код с FastAPI для Render ...
