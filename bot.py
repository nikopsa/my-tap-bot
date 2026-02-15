import os
import asyncio
import time
from fastapi import FastAPI
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import Column, BigInteger, Integer, String, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# --- 1. КОНФИГУРАЦИЯ ---
TOKEN = "8377110375:AAGHQZZi-AP4cWMT_CsvsdO93fMcSaZz_jw"
ADMIN_ID = 1292046104 
CHANNEL_ID = -1002476535560 

# ЛИГИ
LEVELS = {
    1: {"name": "Бронзовая Лига", "limit": 0, "img": "https://img.freepik.com"},
    2: {"name": "Серебряная Лига", "limit": 5000, "img": "https://img.freepik.com"},
    3: {"name": "Золотая Лига", "limit": 25000, "img": "https://img.freepik.com"},
    4: {"name": "Лига Феникса", "limit": 100000, "img": "https://img.freepik.com"}
}

# --- 2. БАЗА ДАННЫХ (С АВТО-ФИКСОМ) ---
DB_URL = os.getenv("DATABASE_URL", "").strip().replace(" ", "").replace("@://", "@")
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DB_URL, pool_pre_ping=True) if DB_URL else None
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession) if engine else None
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

# --- 3. ИНИЦИАЛИЗАЦИЯ ---
bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

def main_kb(energy, balance):
    lvl, data = get_user_lvl(balance)
    next_lvl = LEVELS.get(lvl + 1)
    builder = InlineKeyboardBuilder()
    builder.button(text=f"🔥 ТАПАТЬ ({energy} 🔋)", callback_data="tap")
    prog = f"📊 До {next_lvl['name']}: {next_lvl['limit'] - balance}" if next_lvl else "⭐ МАКС. ЛИГА"
    builder.button(text=prog, callback_data="stats")
    builder.button(text="🏆 ТОП-10", callback_data="top")
    builder.button(text="💳 ВЫВОД", callback_data="withdraw")
    builder.adjust(1, 1, 2)
    return builder.as_markup()

def get_user_lvl(balance):
    for lvl, data in sorted(LEVELS.items(), reverse=True):
        if balance >= data["limit"]: return lvl, data
    return 1, LEVELS[1]

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    async with async_session() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            user = User(user_id=message.from_user.id, username=message.from_user.username, last_tap_time=int(time.time()))
            session.add(user)
            await session.commit()
    _, data = get_user_lvl(user.balance)
    await message.answer_photo(data["img"], f"🎮 *FenixTap:* Твой новый старт!\nЭнергия: 2500 🔋", reply_markup=main_kb(user.energy, user.balance), parse_mode="Markdown")

@dp.callback_query(F.data == "tap")
async def handle_tap(callback: types.CallbackQuery):
    async with async_session() as session:
        user = await session.get(User, callback.from_user.id)
        now = int(time.time())
        regen = (now - user.last_tap_time) // 2
        if regen > 0: user.energy = min(user.max_energy, user.energy + regen)
        
        if user.energy >= 1:
            old_lvl, _ = get_user_lvl(user.balance)
            user.balance += user.tap_power 
            user.energy -= 1
            user.last_tap_time = now
            new_lvl, new_data = get_user_lvl(user.balance)
            await session.commit()
            
            if new_lvl > old_lvl:
                await callback.message.edit_media(types.InputMediaPhoto(media=new_data["img"], caption=f"🚀 ЛИГА: {new_data['name']}!"), reply_markup=main_kb(user.energy, user.balance))
            await callback.answer(f"Баланс: {user.balance} | 🔋 {user.energy}")
        else:
            await callback.answer("🪫 Мало энергии!", show_alert=True)

@dp.callback_query(F.data == "top")
async def handle_top(callback: types.CallbackQuery):
    async with async_session() as session:
        res = await session.execute(select(User).order_by(User.balance.desc()).limit(10))
        users = res.scalars().all()
        text = "🏆 *ТОП-10:* \n\n" + "\n".join([f"{i+1}. @{u.username or u.user_id} — {u.balance}" for i, u in enumerate(users)])
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

# --- 4. ЗАПУСК ---
@app.on_event("startup")
async def on_startup():
    if engine:
        async with engine.begin() as conn:
            # Сносим старую таблицу один раз для фикса столбцов
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        # Убиваем вебхук НОВЫМ токеном
        await bot.delete_webhook(drop_pending_updates=True)
        asyncio.create_task(dp.start_polling(bot))
        print("🚀 БОТ ЗАПУЩЕН НА НОВОМ ТОКЕНЕ!")

@app.get("/")
async def root(): return {"status": "alive"}
