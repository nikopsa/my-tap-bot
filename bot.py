import os
import asyncio
from fastapi import FastAPI
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import Column, BigInteger, Integer, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# --- НАСТРОЙКИ ---
TOKEN = "8377110375:AAGvsfsE3GXbDqQG_IS1Kmb8BL91GPDzO-Y"
CHANNEL_ID = -1002476535560  # Твой канал
# Ссылка на картинку для красоты (можешь заменить на свою)
IMAGE_URL = "https://img.freepik.com"

DB_URL = os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql+asyncpg://", 1)

# --- БАЗА ДАННЫХ ---
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    user_id = Column(BigInteger, primary_key=True)
    balance = Column(Integer, default=0)
    tap_power = Column(Integer, default=1)
    ref_count = Column(Integer, default=0)
    sub_bonus = Column(Integer, default=0)

engine = create_async_engine(DB_URL)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# --- КЛАВИАТУРЫ ---
def main_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 ТАПАТЬ", callback_data="tap")
    builder.button(text="🛒 Магазин/Донат", callback_data="shop")
    builder.button(text="🏆 ТОП", callback_data="top")
    builder.button(text="👥 Друзья", callback_data="refs")
    builder.button(text="🎁 Бонус за канал", callback_data="check_sub")
    builder.adjust(1, 2, 2)
    return builder.as_markup()

# --- ХЕНДЛЕРЫ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    async with async_session() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            # Логика реферала
            args = message.text.split()
            if len(args) > 1 and args[1].isdigit():
                ref_id = int(args[1])
                referrer = await session.get(User, ref_id)
                if referrer:
                    referrer.ref_count += 1
                    referrer.balance += 250 # Бонус за приглашение
            
            user = User(user_id=message.from_user.id)
            session.add(user)
            await session.commit()
    
    await message.answer_photo(
        photo=IMAGE_URL,
        caption=f"🎮 *Добро пожаловать в FenixTap!*\n\nТапай монеты, приглашай друзей и стань самым богатым!",
        reply_markup=main_kb(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "tap")
async def handle_tap(callback: types.CallbackQuery):
    async with async_session() as session:
        user = await session.get(User, callback.from_user.id)
        user.balance += user.tap_power
        await session.commit()
        await callback.answer(f"Баланс: {user.balance} (+{user.tap_power}) 🪙")

@dp.callback_query(F.data == "top")
async def handle_top(callback: types.CallbackQuery):
    async with async_session() as session:
        res = await session.execute(select(User).order_by(User.balance.desc()).limit(10))
        users = res.scalars().all()
        text = "🏆 *ТОП-10 ИГРОКОВ:*\n\n"
        for i, u in enumerate(users):
            text += f"{i+1}. `ID:{u.user_id}` — *{u.balance}* 🪙\n"
        await callback.message.answer(text, parse_mode="Markdown")
        await callback.answer()

@dp.callback_query(F.data == "refs")
async def handle_refs(callback: types.CallbackQuery):
    async with async_session() as session:
        user = await session.get(User, callback.from_user.id)
        me = await bot.get_me()
        link = f"https://t.me{me.username}?start={user.user_id}"
        await callback.message.answer(
            f"👥 *Твои рефералы:* {user.ref_count}\n"
            f"🎁 *Бонус за друга:* 250 🪙\n\n"
            f"🔗 *Твоя ссылка:* \n`{link}`",
            parse_mode="Markdown"
        )
        await callback.answer()

@dp.callback_query(F.data == "shop")
async def shop(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="⚡ Мультитап (500 🪙)", callback_data="buy_multi")
    builder.button(text="⭐ 1000 🪙 (50 Stars)", callback_data="buy_stars")
    builder.button(text="🔙 Назад", callback_data="back")
    await callback.message.edit_caption(caption="🛒 *Магазин и Донат:*", reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "buy_multi")
async def buy_multi(callback: types.CallbackQuery):
    async with async_session() as session:
        user = await session.get(User, callback.from_user.id)
        if user.balance >= 500:
            user.balance -= 500
            user.tap_power += 1
            await session.commit()
            await callback.answer("Успешно куплено!", show_alert=True)
        else:
            await callback.answer("Недостаточно монет!", show_alert=True)

@dp.callback_query(F.data == "buy_stars")
async def buy_stars(callback: types.CallbackQuery):
    await bot.send_invoice(
        callback.from_user.id,
        title="1000 монет FenixTap",
        description="Донат игровой валюты",
        payload="coins_1000",
        provider_token="",
        currency="XTR",
        prices=[types.LabeledPrice(label="XTR", amount=50)]
    )

@dp.callback_query(F.data == "back")
async def back(callback: types.CallbackQuery):
    await callback.message.edit_caption(caption="🎮 *Главное меню:*", reply_markup=main_kb(), parse_mode="Markdown")

@dp.pre_checkout_query()
async def pre_checkout(query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(query.id, ok=True)

@dp.message(F.successful_payment)
async def pay_ok(message: types.Message):
    async with async_session() as session:
        user = await session.get(User, message.from_user.id)
        user.balance += 1000
        await session.commit()
    await message.answer("✅ Оплата прошла! Начислено 1000 🪙")

@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(dp.start_polling(bot))

@app.get("/")
async def root(): return {"status": "ok"}
