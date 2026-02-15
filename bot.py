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
    1: {"name_ru": "Бронза", "name_en": "Bronze", "limit": 0, "img": "https://img.freepik.com"},
    2: {"name_ru": "Серебро", "name_en": "Silver", "limit": 5000, "img": "https://img.freepik.com"},
    3: {"name_ru": "Золото", "name_en": "Gold", "limit": 25000, "img": "https://img.freepik.com"},
    4: {"name_ru": "Феникс", "name_en": "Phoenix", "limit": 100000, "img": "https://img.freepik.com"}
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
    language = Column(String, default="ru") # Колонка языка
    balance = Column(Integer, default=0)
    tap_power = Column(Integer, default=1)
    energy = Column(Integer, default=2500)
    max_energy = Column(Integer, default=2500)
    last_tap_time = Column(BigInteger, default=0)

# --- 3. ЛОГИКА ТЕКСТОВ ---
TEXTS = {
    "ru": {
        "start": "🎮 *FenixTap:* Жми на Феникса!",
        "tap": "🔥 ТАПАТЬ",
        "shop": "🛒 МАГАЗИН",
        "top": "🏆 РЕЙТИНГ",
        "no_energy": "🪫 Нет энергии!",
        "lang_select": "Выбери язык / Choose language:"
    },
    "en": {
        "start": "🎮 *FenixTap:* Tap the Phoenix!",
        "tap": "🔥 TAP",
        "shop": "🛒 SHOP",
        "top": "🏆 TOP",
        "no_energy": "🪫 Out of energy!",
        "lang_select": "Choose language / Выбери язык:"
    }
}

def get_user_lvl(balance, lang):
    for lvl, data in sorted(LEVELS.items(), reverse=True):
        if balance >= data["limit"]:
            name = data["name_ru"] if lang == "ru" else data["name_en"]
            return lvl, name, data["img"]
    return 1, "Bronze", LEVELS[1]["img"]

def main_kb(energy, balance, lang):
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{TEXTS[lang]['tap']} ({energy} 🔋)", callback_data="tap")
    builder.button(text=TEXTS[lang]['top'], callback_data="top")
    builder.button(text=TEXTS[lang]['shop'], callback_data="shop")
    builder.adjust(1, 2)
    return builder.as_markup()

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# --- 4. ХЕНДЛЕРЫ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    async with async_session() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            # Сначала просим выбрать язык
            kb = InlineKeyboardBuilder()
            kb.button(text="🇷🇺 Русский", callback_data="set_lang_ru")
            kb.button(text="🇺🇸 English", callback_data="set_lang_en")
            return await message.answer("Выбери язык / Choose language:", reply_markup=kb.as_markup())
        
    _, lvl_name, img = get_user_lvl(user.balance, user.language)
    await message.answer_photo(img, f"{TEXTS[user.language]['start']}\n\n🏆 {lvl_name}", reply_markup=main_kb(user.energy, user.balance, user.language), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("set_lang_"))
async def set_language(callback: types.CallbackQuery):
    lang = callback.data.split("_")[-1]
    async with async_session() as session:
        user = await session.get(User, callback.from_user.id)
        if not user:
            user = User(user_id=callback.from_user.id, username=callback.from_user.username, language=lang)
            session.add(user)
        else:
            user.language = lang
        await session.commit()
    await callback.message.delete()
    await cmd_start(callback.message)

@dp.callback_query(F.data == "tap")
async def handle_tap(callback: types.CallbackQuery):
    async with async_session() as session:
        user = await session.get(User, callback.from_user.id)
        if user.energy >= 1:
            user.balance += user.tap_power; user.energy -= 1
            await session.commit()
            await callback.answer(f"🪙 {user.balance} | 🔋 {user.energy}")
        else:
            await callback.answer(TEXTS[user.language]["no_energy"], show_alert=True)

@dp.message(Command("set_balance"))
async def set_balance(message: types.Message, command: CommandObject):
    if message.from_user.id == ADMIN_ID and command.args:
        async with async_session() as session:
            await session.execute(update(User).where(User.user_id == message.from_user.id).values(balance=int(command.args)))
            await session.commit()
        await message.answer("✅ Done!")

# --- 5. СТАРТ ---
@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(2)
    asyncio.create_task(dp.start_polling(bot))
    print("🚀 Fenix Multi-Lang Started!")

@app.get("/")
async def root(): return {"status": "alive"}
