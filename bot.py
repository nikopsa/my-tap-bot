import os, asyncio, json, time, logging
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import LabeledPrice, PreCheckoutQuery
from sqlalchemy import Column, BigInteger, Integer, String, DateTime, update, select, desc, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- НАСТРОЙКИ ---
TOKEN = "8377110375:AAG31LE62g88acAmbSkdxk_pyeMRmLtqwdM"
ADMIN_ID = 1292046104 
APP_URL = "https://my-tap-bot.onrender.com" 

DB_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///db.sqlite3").strip().replace("postgres://", "postgresql+asyncpg://")
engine = create_async_engine(DB_URL, pool_pre_ping=True)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    user_id = Column(BigInteger, primary_key=True)
    username = Column(String)
    balance = Column(Integer, default=500)
    tap_power = Column(Integer, default=1)
    auto_power = Column(Integer, default=0)
    energy = Column(Integer, default=2500)
    max_energy = Column(Integer, default=2500)
    last_touch = Column(Integer, default=int(time.time()))
    level = Column(Integer, default=1)
    streak = Column(Integer, default=0)
    last_checkin = Column(DateTime, default=datetime.utcnow() - timedelta(days=1))
    referrer_id = Column(BigInteger, nullable=True)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- ДОБАВЛЕНО: ОТДАЧА ТВОЕГО INDEX.HTML ---
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    file_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>index.html не найден</h1>"

# --- ТВОЯ ЛОГИКА API ---
@app.get("/u/{uid}")
async def get_user(uid: int):
    async with async_session() as session:
        user = await session.get(User, uid)
        if not user:
            user = User(user_id=uid, last_touch=int(time.time()))
            session.add(user); await session.commit(); await session.refresh(user)
        now = int(time.time())
        off = (now - user.last_touch) * user.auto_power
        user.balance += off; user.last_touch = now; await session.commit()
        return {"score": user.balance, "mult": user.tap_power, "auto": user.auto_power, "energy": user.energy, "max_energy": user.max_energy, "lvl": user.level}

@app.post("/s")
async def save_user(request: Request):
    data = await request.json()
    async with async_session() as session:
        user = await session.get(User, int(data['id']))
        if user:
            user.balance = data['score']; user.tap_power = data['mult']
            user.auto_power = data['auto']; user.energy = data['energy']
            user.last_touch = int(time.time())
            user.level = (user.balance // 50000) + 1
            await session.commit()
    return {"status": "ok"}

# --- ТВОИ КОМАНДЫ БОТА ---
@dp.message(Command("start"))
async def start(m: types.Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="🔥 ИГРАТЬ", web_app=types.WebAppInfo(url=APP_URL))
    await m.answer(f"Здарова! Бот ожил. Твой ID: {m.from_user.id}", reply_markup=kb.as_markup())

async def recovery():
    while True:
        await asyncio.sleep(60)
        async with async_session() as session:
            await session.execute(update(User).where(User.energy < User.max_energy).values(energy=User.energy + 20))
            await session.commit()

# --- ДОБАВЛЕНО: ЖЕСТКИЙ СБРОС ДЛЯ RENDER ---
@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn: 
        await conn.run_sync(Base.metadata.create_all)
    
    # Сброс вебхуков и очистка всех сессий
    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(2) # Даем время серверам ТГ
    
    logger.info("--- БОТ ЗАПУСКАЕТСЯ БЕЗ КОНФЛИКТОВ ---")
    asyncio.create_task(dp.start_polling(bot, skip_updates=True))
    asyncio.create_task(recovery())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
