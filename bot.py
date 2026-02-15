import os, asyncio, time
from fastapi import FastAPI
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import Column, BigInteger, Integer, String, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# --- 1. CONFIG (SECURE) ---
TOKEN = "8377110375:AAGHQZZi-AP4cWMT_CsvsdO93fMcSaZz_jw"
ADMIN_ID = 1292046104 

LEVELS = {
    1: {"name": "Бронза", "limit": 0, "img": "https://img.freepik.com"},
    2: {"name": "Серебро", "limit": 5000, "img": "https://img.freepik.com"},
    3: {"name": "Золото", "limit": 25000, "img": "https://img.freepik.com"},
    4: {"name": "Феникс", "limit": 100000, "img": "https://img.freepik.com"}
}

# --- 2. DATABASE ENGINE (HARDENED) ---
DB_URL = os.getenv("DATABASE_URL", "").strip().replace(" ", "").replace("@://", "@")
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DB_URL, pool_pre_ping=True, pool_recycle=3600)
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
    last_bonus_time = Column(BigInteger, default=0)

# --- 3. CORE LOGIC ---
def get_user_lvl(balance):
    for lvl, data in sorted(LEVELS.items(), reverse=True):
        if balance >= data["limit"]: return lvl, data
    return 1, LEVELS[1]

def main_kb(energy, balance):
    builder = InlineKeyboardBuilder()
    builder.button(text=f"🔥 ТАП ({energy}🔋)", callback_data="tap")
    builder.button(text="🎁 БОНУС 1000", callback_data="daily_bonus")
    builder.button(text="🛒 МАГАЗИН", callback_data="shop")
    builder.button(text="🏆 ТОП-10", callback_data="top")
    builder.adjust(1, 1, 2)
    return builder.as_markup()

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    async with async_session() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            user = User(user_id=message.from_user.id, username=message.from_user.username)
            session.add(user); await session.commit()
    _, data = get_user_lvl(user.balance)
    await message.answer_photo(data["img"], f"🎮 *FenixTap Protec:* Система защиты активна.\n\nЭнергия: {user.energy}/2500 🔋", reply_markup=main_kb(user.energy, user.balance), parse_mode="Markdown")

@dp.callback_query(F.data == "tap")
async def handle_tap(callback: types.CallbackQuery):
    async with async_session() as session:
        user = await session.get(User, callback.from_user.id)
        now = int(time.time())
        
        # Анти-чит: проверка интервала (не чаще 10 тапов в секунду для человека)
        if now == user.last_tap_time and user.energy % 10 == 0:
             return await callback.answer("⚠️ Слишком быстро!", show_alert=False)

        # Реген
        regen = (now - user.last_tap_time) // 2
        if regen > 0: user.energy = min(user.max_energy, user.energy + regen)
        
        if user.energy >= 1:
            user.balance += user.tap_power; user.energy -= 1; user.last_tap_time = now
            await session.commit(); await callback.answer(f"🪙 {user.balance} | 🔋 {user.energy}")
        else:
            await callback.answer("🪫 Нет энергии!", show_alert=True)

@dp.callback_query(F.data == "top")
async def handle_top(callback: types.CallbackQuery):
    async with async_session() as session:
        res = await session.execute(select(User).order_by(User.balance.desc()).limit(10))
        users = res.scalars().all()
        text = "🏆 *ЛИДЕРЫ:* \n\n" + "\n".join([f"{i+1}. @{u.username or u.user_id} — {u.balance}" for i, u in enumerate(users)])
    await callback.message.answer(text, parse_mode="Markdown"); await callback.answer()

# --- 4. STARTUP ---
@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(dp.start_polling(bot))
    print("🛡️ СИСТЕМА ЗАЩИЩЕНА. БОТ В СЕТИ.")

@app.get("/")
async def root(): return {"status": "shield_active"}
