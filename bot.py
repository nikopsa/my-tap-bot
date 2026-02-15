import os, asyncio, time
from fastapi import FastAPI
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import Column, BigInteger, Integer, String, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# --- 1. КОНФИГ ---
TOKEN = "8377110375:AAGHQZZi-AP4cWMT_CsvsdO93fMcSaZz_jw"
ADMIN_ID = 1292046104 

LEVELS = {
    1: {"name": "Бронза", "limit": 0, "img": "https://img.freepik.com"},
    2: {"name": "Серебро", "limit": 5000, "img": "https://img.freepik.com"},
    3: {"name": "Золото", "limit": 25000, "img": "https://img.freepik.com"},
    4: {"name": "Феникс", "limit": 100000, "img": "https://img.freepik.com"}
}

# --- 2. БАЗА ---
DB_URL = os.getenv("DATABASE_URL", "").strip().replace(" ", "").replace("@://", "@")
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DB_URL, pool_pre_ping=True)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    user_id = Column(BigInteger, primary_key=True)
    username = Column(String, nullable=True)
    balance = Column(Integer, default=0)
    tap_power = Column(Integer, default=1)
    energy = Column(Integer, default=2500)
    max_energy = Column(Integer, default=2500)
    last_tap_time = Column(BigInteger, default=0)

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# --- 3. КНОПКИ ---
def main_kb(energy, balance):
    builder = InlineKeyboardBuilder()
    builder.button(text=f"🔥 ТАП ({energy}🔋)", callback_data="tap")
    builder.button(text="🏆 ТОП", callback_data="top")
    builder.button(text="🛒 МАГАЗИН", callback_data="shop")
    builder.adjust(1, 2)
    return builder.as_markup()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    async with async_session() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            user = User(user_id=message.from_user.id, username=message.from_user.username)
            session.add(user); await session.commit()
    await message.answer_photo(LEVELS[1]["img"], "🎮 FenixTap: Погнали!", reply_markup=main_kb(user.energy, user.balance))

@dp.callback_query(F.data == "tap")
async def handle_tap(callback: types.CallbackQuery):
    async with async_session() as session:
        user = await session.get(User, callback.from_user.id)
        if user.energy >= 1:
            user.balance += user.tap_power; user.energy -= 1
            await session.commit()
            await callback.answer(f"🪙 {user.balance} | 🔋 {user.energy}")
        else:
            await callback.answer("🪫 Нет энергии!", show_alert=True)

# --- 4. ЖЕСТКИЙ СТАРТ ---
@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 1. Удаляем вебхук
    await bot.delete_webhook(drop_pending_updates=True)
    # 2. Пауза, чтобы старый процесс на Render успел сдохнуть
    await asyncio.sleep(2) 
    # 3. Запускаем опрос
    asyncio.create_task(dp.start_polling(bot, handle_as_tasks=False))
    print("🚀 БОТ ЗАПУЩЕН БЕЗ КОНФЛИКТОВ!")

@app.get("/")
async def root(): return {"status": "alive"}
