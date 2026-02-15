import os, asyncio, time
from fastapi import FastAPI
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import Column, BigInteger, Integer, String, select, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# --- 1. КОНФИГУРАЦИЯ ---
TOKEN = "8377110375:AAGHQZZi-AP4cWMT_CsvsdO93fMcSaZz_jw"
ADMIN_ID = 1292046104 

LEVELS = {
    1: {"name": "Бронза", "limit": 0, "img": "https://img.freepik.com"},
    2: {"name": "Серебро", "limit": 5000, "img": "https://img.freepik.com"},
    3: {"name": "Золото", "limit": 25000, "img": "https://img.freepik.com"},
    4: {"name": "Феникс", "limit": 100000, "img": "https://img.freepik.com"}
}

# --- 2. БАЗА ДАННЫХ ---
raw_url = os.getenv("DATABASE_URL", "").strip().replace(" ", "").replace("@://", "@")
if raw_url.startswith("postgres://"):
    raw_url = raw_url.replace("postgres://", "postgresql+asyncpg://", 1)

engine = create_async_engine(raw_url, pool_pre_ping=True) if raw_url else None
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

# --- 3. ВСПОМОГАТЕЛЬНАЯ ЛОГИКА ---
def get_user_lvl(balance):
    for lvl, data in sorted(LEVELS.items(), reverse=True):
        if balance >= data["limit"]: return lvl, data
    return 1, LEVELS[1]

def main_kb(energy, balance):
    lvl, _ = get_user_lvl(balance)
    builder = InlineKeyboardBuilder()
    builder.button(text=f"🔥 ТАПАТЬ ({energy} 🔋)", callback_data="tap")
    builder.button(text="🏆 ТОП", callback_data="top")
    builder.button(text="🛒 МАГАЗИН", callback_data="shop")
    builder.adjust(1, 2)
    return builder.as_markup()

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# --- 4. ХЕНДЛЕРЫ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if not async_session: return
    async with async_session() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            user = User(user_id=message.from_user.id, username=message.from_user.username, last_tap_time=int(time.time()))
            session.add(user); await session.commit()
    _, data = get_user_lvl(user.balance)
    await message.answer_photo(data["img"], f"🎮 *FenixTap:* Энергия 2500! Жми!", reply_markup=main_kb(user.energy, user.balance), parse_mode="Markdown")

@dp.callback_query(F.data == "tap")
async def handle_tap(callback: types.CallbackQuery):
    if not async_session: return
    async with async_session() as session:
        user = await session.get(User, callback.from_user.id)
        if user.energy >= 1:
            user.balance += user.tap_power; user.energy -= 1
            await session.commit()
            await callback.answer(f"🪙 {user.balance} | 🔋 {user.energy}")
        else:
            await callback.answer("🪫 Мало энергии!", show_alert=True)

@dp.message(Command("set_balance"))
async def set_balance(message: types.Message, command: CommandObject):
    if message.from_user.id == ADMIN_ID and command.args:
        try:
            val = int(command.args)
            async with async_session() as session:
                await session.execute(update(User).where(User.user_id == message.from_user.id).values(balance=val))
                await session.commit()
            await message.answer(f"✅ Баланс установлен: {val}")
        except: await message.answer("❌ Введи число!")

# --- 5. ЗАПУСК ---
@app.on_event("startup")
async def on_startup():
    if engine:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await bot.delete_webhook(drop_pending_updates=True)
        await asyncio.sleep(1)
        asyncio.create_task(dp.start_polling(bot))
        print("🚀 ЧИСТЫЙ ЗАПУСК ВЫПОЛНЕН!")

@app.get("/")
async def root(): return {"status": "all_clear"}
