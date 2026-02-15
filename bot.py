import os
import asyncio
from fastapi import FastAPI
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import Column, BigInteger, Integer, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. НАСТРОЙКИ
TOKEN = "8377110375:AAGvsfsE3GXbDqQG_IS1Kmb8BL91GPDzO-Y"
DB_URL = os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql+asyncpg://", 1)

# 2. БАЗА ДАННЫХ
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    user_id = Column(BigInteger, primary_key=True)
    balance = Column(Integer, default=0)
    ref_count = Column(Integer, default=0)
    tap_power = Column(Integer, default=1)

engine = create_async_engine(DB_URL, pool_pre_ping=True)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# 3. ИНИЦИАЛИЗАЦИЯ
bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# --- КЛАВИАТУРЫ ---
def main_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 ТАПАТЬ", callback_data="tap")
    builder.button(text="🛒 Магазин", callback_data="shop")
    builder.button(text="🏆 ТОП", callback_data="top")
    builder.button(text="👥 Друзья", callback_data="refs")
    builder.adjust(1, 2, 1)
    return builder.as_markup()

def shop_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="⚡ Мультитап — 500 🪙", callback_data="buy_multi")
    builder.button(text="⭐ Купить 1000 🪙 (XTR)", callback_data="donate_stars")
    builder.button(text="🔙 Назад", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()

# --- ХЕНДЛЕРЫ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    async with async_session() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            user = User(user_id=message.from_user.id)
            session.add(user)
            await session.commit()
    await message.answer("🎮 Добро пожаловать в FenixTap!", reply_markup=main_kb())

@dp.callback_query(F.data == "tap")
async def handle_tap(callback: types.CallbackQuery):
    async with async_session() as session:
        user = await session.get(User, callback.from_user.id)
        user.balance += user.tap_power
        await session.commit()
        await callback.answer(f"Баланс: {user.balance} (+{user.tap_power}) 🪙")

# МАГАЗИН И ДОНАТ
@dp.callback_query(F.data == "shop")
async def handle_shop(callback: types.CallbackQuery):
    await callback.message.edit_text("🛒 Магазин: прокачка за монеты или Донат за Звёзды ⭐", reply_markup=shop_kb())

@dp.callback_query(F.data == "donate_stars")
async def process_donate(callback: types.CallbackQuery):
    # Отправляем счет на 50 Telegram Stars (XTR)
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="1000 игровых монет",
        description="Покупка валюты для FenixTap",
        payload="buy_1000_coins",
        provider_token="", # Для Stars оставляем пустым
        currency="XTR",
        prices=[types.LabeledPrice(label="Цена", amount=50)] # 50 звёзд
    )
    await callback.answer()

# Проверка платежа (pre_checkout)
@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

# Успешная оплата
@dp.message(F.successful_payment)
async def success_payment(message: types.Message):
    async with async_session() as session:
        user = await session.get(User, message.from_user.id)
        user.balance += 1000
        await session.commit()
    await message.answer(f"✅ Оплата прошла успешно! Вам начислено 1000 🪙")

# РЕЙТИНГ И РЕФЕРАЛЫ (остаются как были)
@dp.callback_query(F.data == "top")
async def handle_top(callback: types.CallbackQuery):
    async with async_session() as session:
        res = await session.execute(select(User).order_by(User.balance.desc()).limit(10))
        top_users = res.scalars().all()
        text = "🏆 ТОП-10 ИГРОКОВ:\n\n" + "\n".join([f"{i+1}. ID:{u.user_id} — {u.balance}" for i, u in enumerate(top_users)])
        await callback.message.answer(text)
    await callback.answer()

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text("🎮 Главное меню:", reply_markup=main_kb())

# ЗАПУСК
@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(dp.start_polling(bot))

@app.get("/")
async def root(): return {"status": "ok"}
