import os
import asyncio
import time
from fastapi import FastAPI
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import Column, BigInteger, Integer, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# --- КОНФИГ ---
TOKEN = "8377110375:AAGvsfsE3GXbDqQG_IS1Kmb8BL91GPDzO-Y"
ADMIN_ID = 8377110375 
DB_URL = os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql+asyncpg://", 1)

# ЛИГИ И КОНТЕНТ
LEVELS = {
    1: {"name": "Бронзовая Лига", "limit": 0, "img": "https://img.freepik.com"},
    2: {"name": "Серебряная Лига", "limit": 5000, "img": "https://img.freepik.com"},
    3: {"name": "Золотая Лига", "limit": 25000, "img": "https://img.freepik.com"},
    4: {"name": "Лига Феникса", "limit": 100000, "img": "https://img.freepik.com"}
}

# --- БАЗА ДАННЫХ ---
Base = declarative_base()
class User(Base):
    __tablename__ = 'users'
    user_id = Column(BigInteger, primary_key=True)
    username = Column(types.String, nullable=True) # Добавили имя для рейтинга
    balance = Column(Integer, default=0)
    tap_power = Column(Integer, default=1)
    energy = Column(Integer, default=100)
    max_energy = Column(Integer, default=100)
    last_tap_time = Column(BigInteger, default=0)

engine = create_async_engine(DB_URL, pool_pre_ping=True)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# --- ЛОГИКА ---
def get_user_lvl(balance):
    for lvl, data in sorted(LEVELS.items(), reverse=True):
        if balance >= data["limit"]: return lvl, data
    return 1, LEVELS[1]

def main_kb(energy, balance):
    lvl, data = get_user_lvl(balance)
    builder = InlineKeyboardBuilder()
    builder.button(text=f"🔥 ТАПАТЬ ({energy}🔋)", callback_data="tap")
    builder.button(text="🏆 ЛИДЕРЫ", callback_data="top_global")
    builder.button(text="🛒 Магазин", callback_data="shop")
    builder.button(text="👥 Друзья", callback_data="refs")
    builder.button(text="💳 ВЫВОД", callback_data="withdraw")
    builder.adjust(1, 1, 2, 1)
    return builder.as_markup()

# --- ХЕНДЛЕРЫ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    async with async_session() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            user = User(
                user_id=message.from_user.id, 
                username=message.from_user.username or message.from_user.first_name,
                last_tap_time=int(time.time())
            )
            session.add(user)
            await session.commit()
    
    lvl, data = get_user_lvl(user.balance)
    await message.answer_photo(
        data["img"],
        caption=f"🔥 *FENIXTAP ИДЕТ НА ВЗЛЕТ!*\\n\nТвоя лига: {data['name']}\\nТвой баланс: {user.balance} 🪙",
        reply_markup=main_kb(100, user.balance),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "top_global")
async def handle_top(callback: types.CallbackQuery):
    async with async_session() as session:
        # Берем ТОП-10 по балансу
        result = await session.execute(select(User).order_by(User.balance.desc()).limit(10))
        top_users = result.scalars().all()
        
        text = "🏆 *ТОП-10 ФЕНИКСОВ МИРА:*\\n\\n"
        for i, u in enumerate(top_users):
            medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "🔹"
            name = f"@{u.username}" if u.username else f"ID:{u.user_id}"
            text += f"{medal} {i+1}. {name} — *{u.balance}* 🪙\\n"
        
        await callback.message.answer(text, parse_mode="Markdown")
        await callback.answer()

@dp.callback_query(F.data == "tap")
async def handle_tap(callback: types.CallbackQuery):
    async with async_session() as session:
        user = await session.get(User, callback.from_user.id)
        now = int(time.time())
        regen = (now - user.last_tap_time) // 2
        if regen > 0:
            user.energy = min(user.max_energy, user.energy + regen)
        
        if user.energy >= 1:
            old_lvl, _ = get_user_lvl(user.balance)
            user.balance += user.tap_power
            user.energy -= 1
            user.last_tap_time = now
            new_lvl, new_data = get_user_lvl(user.balance)
            
            await session.commit()
            
            if new_lvl > old_lvl:
                await callback.message.edit_media(
                    types.InputMediaPhoto(media=new_data["img"], caption=f"🚀 ТЫ ПЕРЕШЕЛ В: {new_data['name']}!"),
                    reply_markup=main_kb(user.energy, user.balance)
                )
            
            await callback.answer(f" Баланс: {user.balance} | 🔋 Энергия: {user.energy}")
        else:
            await callback.answer("🪫 Энергия на нуле! Загляни позже.", show_alert=True)

# Обычные кнопки магазина и возврата назад
@dp.callback_query(F.data == "shop")
async def shop(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="⚡ Мультитап +1 (500 🪙)", callback_data="buy_p")
    builder.button(text="🔋 Батарея +50 (1000 🪙)", callback_data="buy_e")
    builder.button(text="🔙 Назад", callback_data="back")
    await callback.message.edit_caption(caption="🛒 *МАГАЗИН*", reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "back")
async def back(callback: types.CallbackQuery):
    async with async_session() as session:
        user = await session.get(User, callback.from_user.id)
    _, data = get_user_lvl(user.balance)
    await callback.message.edit_media(
        types.InputMediaPhoto(media=data["img"], caption=f"🎮 Лига: {data['name']}"),
        reply_markup=main_kb(user.energy, user.balance)
    )

@dp.callback_query(F.data == "withdraw")
async def withdraw(callback: types.CallbackQuery):
    await callback.answer("⏳ Листинг на биржах скоро! Копи монеты.", show_alert=True)

# --- ЗАПУСК ---
@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(dp.start_polling(bot))

@app.get("/")
async def root(): return {"status": "FenixTap Global Engine Ready"}
