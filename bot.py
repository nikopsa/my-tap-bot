import os, asyncio
from fastapi import FastAPI
import uvicorn
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import Column, BigInteger, Integer, String, update, ForeignKey
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# --- 1. КОНФИГУРАЦИЯ ---
TOKEN = "8377110375:AAGHQZZi-AP4cWMT_CsvsdO93fMcSaZz_jw"
ADMIN_ID = 1292046104 

# Каналы для подписки (ID должны быть точными, бот должен быть там админом)
PARTNER_CHANNELS = [
    {"id": -1001234567890, "link": "https://t.me", "reward": 5000, "name": "Fenix News"},
]

LEVELS = {
    1: {"name_ru": "Бронза", "name_en": "Bronze", "limit": 0, "img": "https://img.freepik.com"},
    2: {"name_ru": "Серебро", "name_en": "Silver", "limit": 5000, "img": "https://img.freepik.com"},
    3: {"name_ru": "Золото", "name_en": "Gold", "limit": 25000, "img": "https://img.freepik.com"},
    4: {"name_ru": "Феникс", "name_en": "Phoenix", "limit": 100000, "img": "https://img.freepik.com"}
}

# --- 2. БАЗА ---
DB_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///db.sqlite3").strip().replace("postgres://", "postgresql+asyncpg://")
engine = create_async_engine(DB_URL, pool_pre_ping=True)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    user_id = Column(BigInteger, primary_key=True)
    username = Column(String, nullable=True)
    language = Column(String, default="ru")
    balance = Column(Integer, default=0)
    tap_power = Column(Integer, default=1)
    energy = Column(Integer, default=2500)
    max_energy = Column(Integer, default=2500)

class UserTask(Base):
    __tablename__ = 'user_tasks'
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.user_id'))
    task_id = Column(String)

# --- 3. ЛОГИКА ТЕКСТОВ ---
TEXTS = {
    "ru": {
        "start": "🎮 *FenixTap:* Жми на Феникса!",
        "tap": "🔥 ТАПАТЬ", "shop": "🛒 МАГАЗИН", "top": "🏆 РЕЙТИНГ", "tasks": "🎁 ЗАДАНИЯ",
        "no_energy": "🪫 Нет энергии!", "lang_select": "Выбери язык:"
    },
    "en": {
        "start": "🎮 *FenixTap:* Tap the Phoenix!",
        "tap": "🔥 TAP", "shop": "🛒 SHOP", "top": "🏆 TOP", "tasks": "🎁 TASKS",
        "no_energy": "🪫 Out of energy!", "lang_select": "Choose language:"
    }
}

def main_kb(energy, balance, lang):
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{TEXTS[lang]['tap']} ({energy} 🔋)", callback_data="tap")
    builder.button(text=TEXTS[lang]['tasks'], callback_data="tasks")
    builder.button(text=TEXTS[lang]['top'], callback_data="top")
    builder.button(text=TEXTS[lang]['shop'], callback_data="shop")
    builder.adjust(1, 1, 2)
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
            kb = InlineKeyboardBuilder()
            kb.button(text="🇷🇺 Русский", callback_data="set_lang_ru")
            kb.button(text="🇺🇸 English", callback_data="set_lang_en")
            return await message.answer(TEXTS["ru"]["lang_select"], reply_markup=kb.as_markup())
        
        _, lvl_name, img = get_user_lvl(user.balance, user.language)
        await message.answer_photo(img, f"{TEXTS[user.language]['start']}\n\n🏆 {lvl_name}\n💰 Баланс: {user.balance}", 
                                   reply_markup=main_kb(user.energy, user.balance, user.language), parse_mode="Markdown")

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
        if user.energy >= user.tap_power:
            user.balance += user.tap_power; user.energy -= user.tap_power
            await session.commit()
            try:
                await callback.message.edit_reply_markup(reply_markup=main_kb(user.energy, user.balance, user.language))
            except: pass
            await callback.answer(f"🪙 +{user.tap_power}")
        else:
            await callback.answer(TEXTS[user.language]["no_energy"], show_alert=True)

@dp.callback_query(F.data == "tasks")
async def show_tasks(callback: types.CallbackQuery):
    user_lang = "ru" # По умолчанию
    async with async_session() as session:
        user = await session.get(User, callback.from_user.id)
        if user: user_lang = user.language

    builder = InlineKeyboardBuilder()
    for task in PARTNER_CHANNELS:
        builder.button(text=f"Подписаться на {task['name']} (+{task['reward']} 🪙)", url=task['link'])
        builder.button(text=f"Проверить {task['name']} ✅", callback_data=f"check_sub_{task['id']}")
    builder.adjust(1)
    await callback.message.answer("Выполни задания от партнеров:", reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("check_sub_"))
async def check_subscription(callback: types.CallbackQuery):
    channel_id = callback.data.replace("check_sub_", "")
    task_info = next((t for t in PARTNER_CHANNELS if str(t['id']) == channel_id), None)
    if not task_info: return

    try:
        member = await callback.bot.get_chat_member(chat_id=channel_id, user_id=callback.from_user.id)
        if member.status in ["member", "administrator", "creator"]:
            async with async_session() as session:
                from sqlalchemy import and_
                # Проверка в БД
                stmt = select(UserTask).where(and_(UserTask.user_id == callback.from_user.id, UserTask.task_id == f"sub_{channel_id}"))
                res = await session.execute(stmt)
                if res.scalar():
                    return await callback.answer("❌ Награда уже получена!", show_alert=True)
                
                user = await session.get(User, callback.from_user.id)
                user.balance += task_info['reward']
                session.add(UserTask(user_id=callback.from_user.id, task_id=f"sub_{channel_id}"))
                await session.commit()
            await callback.answer(f"✅ Успешно! +{task_info['reward']} 🪙", show_alert=True)
        else:
            await callback.answer("❌ Подписка не найдена!", show_alert=True)
    except:
        await callback.answer("Ошибка проверки. Бот должен быть админом в канале!", show_alert=True)

def get_user_lvl(balance, lang):
    for lvl, data in sorted(LEVELS.items(), reverse=True):
        if balance >= data["limit"]:
            return lvl, (data["name_ru"] if lang == "ru" else data["name_en"]), data["img"]
    return 1, "Bronze", LEVELS[1]["img"]

# --- 5. СТАРТ ---
@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(dp.start_polling(bot))

@app.get("/")
async def root(): return {"status": "alive"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
