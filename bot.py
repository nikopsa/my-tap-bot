import os
import asyncio
from fastapi import FastAPI
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# 1. ТВОЙ ТОКЕН
TOKEN = "8377110375:AAG3GmbEpQGyIcfzyOByu6qPUPVbxhYpPSg"

# 2. ИСПРАВЛЕНИЕ URL БАЗЫ (Fix ArgumentError)
DB_URL = os.getenv("DATABASE_URL")
if DB_URL:
    if DB_URL.startswith("postgres://"):
        DB_URL = DB_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    elif "postgresql://" in DB_URL and "asyncpg" not in DB_URL:
        DB_URL = DB_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    DB_URL = "postgresql+asyncpg://user:pass@localhost/db"

# 3. НАСТРОЙКА ДВИЖКА
engine = create_async_engine(DB_URL, pool_pre_ping=True)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# 4. ЛОГИКА ТАПАЛКИ
def get_tap_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 ТАПНУТЬ! 💰", callback_data="tap")
    return builder.as_markup()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        f"Привет, {message.from_user.first_name}! Ты в игре. Нажимай на кнопку, чтобы собирать монеты!",
        reply_markup=get_tap_kb()
    )

@dp.callback_query(F.data == "tap")
async def handle_tap(callback: types.Callback_query):
    # Тут будет +1 к балансу в будущем
    await callback.answer("Баланс: +1 монета!", show_alert=False)

# 5. ЗАПУСК ДЛЯ RENDER
@app.on_event("startup")
async def on_startup():
    asyncio.create_task(dp.start_polling(bot))

@app.get("/")
async def health_check():
    return {"status": "running", "bot": "FenixTap_bot"}
