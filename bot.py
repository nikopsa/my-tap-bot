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
    energy = Column(Integer, default=100)
    max_energy = Column(Integer, default=100)
    last_tap_time = Column(BigInteger, default=0)

engine = create_async_engine(DB_URL, pool_pre_ping=True)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# --- ЛОГИКА ЭНЕРГИИ ---
def calculate_energy(user):
    now = int(time.time())
    elapsed = now - user.last_tap_time
    regen = elapsed // 3 # Реген 1 ед. каждые 3 секунды
    if regen > 0:
        user.energy = min(user.max_energy, user.energy + regen)
        user.last_tap_time = now
    return user.energy

# --- КЛАВИАТУРЫ ---
def main_kb(energy):
    builder = InlineKeyboardBuilder()
    builder.button(text=f"⚡ ТАП ({energy}🔋)", callback_data="tap")
    builder.button(text="🛒 Магазин", callback_data="shop")
    builder.button(text="🏆 ТОП", callback_data="top")
    builder.button(text="👥 Друзья", callback_data="refs")
    builder.button(text="💳 ВЫВОД", callback_data="withdraw") # ТА САМАЯ КНОПКА
    builder.adjust(1, 2, 2)
    return builder.as_markup()

# --- ХЕНДЛЕРЫ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    async with async_session() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            # Реферальная система
            args = message.text.split()
            if len(args) > 1 and args.isdigit():
                referrer = await session.get(User, int(args))
                if referrer:
                    referrer.ref_count += 1
                    referrer.balance += 250
            
            user = User(user_id=message.from_user.id, last_tap_time=int(time.time()))
            session.add(user)
            await session.commit()
    
    await message.answer_photo(
        photo=IMAGE_URL,
        caption="🎮 *FenixTap запущен!*\n\nТапай монеты, качай энергию и жди листинга!",
        reply_markup=main_kb(100),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "tap")
async def handle_tap(callback: types.CallbackQuery):
    async with async_session() as session:
        user = await session.get(User, callback.from_user.id)
        energy = calculate_energy(user)
        
        if energy >= 1:
            user.balance += user.tap_power
            user.energy -= 1
            user.last_tap_time = int(time.time())
            await session.commit()
            await callback.answer(f"Баланс: {user.balance} | Энергия: {user.energy}🔋")
            
            if user.energy % 10 == 0: # Обновляем кнопку реже, чтобы не спамить
                await callback.message.edit_reply_markup(reply_markup=main_kb(user.energy))
        else:
            await callback.answer("❌ Энергия на нуле! Отдохни.", show_alert=True)

@dp.callback_query(F.data == "withdraw")
async def handle_withdraw(callback: types.CallbackQuery):
    # Логика "В разработке"
    await callback.answer("⏳ Функция вывода в разработке! Ожидайте листинга.", show_alert=True)

@dp.callback_query(F.data == "shop")
async def shop(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="⚡ Мультитап +1 (500 🪙)", callback_data="buy_multi")
    builder.button(text="🔋 Энергия +50 (1000 🪙)", callback_data="buy_energy")
    builder.button(text="⭐ 1000 🪙 (50 Stars)", callback_data="buy_stars")
    builder.button(text="🔙 Назад", callback_data="back")
    builder.adjust(1)
    await callback.message.edit_caption(caption="🛒 *Магазин улучшений:*", reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "top")
async def handle_top(callback: types.CallbackQuery):
    async with async_session() as session:
        res = await session.execute(select(User).order_by(User.balance.desc()).limit(10))
        users = res.scalars().all()
        text = "🏆 *ТОП ИГРОКОВ:*\n\n" + "\n".join([f"{i+1}. ID:{u.user_id} — {u.balance} 🪙" for i, u in enumerate(users)])
        await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "back")
async def back(callback: types.CallbackQuery):
    async with async_session() as session:
        user = await session.get(User, callback.from_user.id)
        energy = calculate_energy(user)
    await callback.message.edit_caption(caption="🎮 *Главное меню:*", reply_markup=main_kb(energy), parse_mode="Markdown")

# --- ДОНАТ (STARS) ---
@dp.callback_query(F.data == "buy_stars")
async def buy_stars(callback: types.CallbackQuery):
    await bot.send_invoice(
        callback.from_user.id, title="1000 🪙", description="Пополнение баланса",
        payload="c1000", provider_token="", currency="XTR",
        prices=[types.LabeledPrice(label="XTR", amount=50)]
    )

@dp.pre_checkout_query()
async def pre_checkout(q: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(q.id, ok=True)

@dp.message(F.successful_payment)
async def pay_ok(m: types.Message):
    async with async_session() as session:
        u = await session.get(User, m.from_user.id)
        u.balance += 1000
        await session.commit()
    await m.answer("✅ Успешно начислено 1000 🪙!")

# --- ЗАПУСК ---
@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(dp.start_polling(bot))

@app.get("/")
async def root(): return {"status": "ok"}
