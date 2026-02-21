import os, asyncio, json, time, logging, httpx
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery, Update
from sqlalchemy import Column, BigInteger, Integer, String, DateTime, update, select, desc, func, text, Boolean
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# --- НАСТРОЙКИ ---
TOKEN = "8377110375:AAG31LE62g88acAmbSkdxk_pyeMRmLtqwdM"
APP_URL = "https://my-tap-bot.onrender.com" 
WEBHOOK_PATH = f"/webhook/{TOKEN}"

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
    boost_end = Column(DateTime, nullable=True)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
bot = Bot(token=TOKEN)
dp = Dispatcher()

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("index.html", "r", encoding="utf-8") as f: return f.read()

@app.get("/get_user")
async def get_user(id: int):
    async with async_session() as session:
        user = await session.get(User, id)
        if not user:
            user = User(user_id=id)
            session.add(user); await session.commit(); await session.refresh(user)
        return {"score": user.balance, "mult": user.tap_power, "auto": user.auto_power, "energy": user.energy, "max_energy": user.max_energy}

@app.get("/get_top")
async def get_top():
    async with async_session() as session:
        res = await session.execute(select(User).order_by(desc(User.balance)).limit(10))
        users = res.scalars().all()
        return [{"username": u.username or f"User_{str(u.user_id)[-4:]}", "balance": u.balance} for u in users]

@app.post("/s")
async def save(request: Request):
    d = await request.json()
    async with async_session() as session:
        user = await session.get(User, int(d['id']))
        if user:
            user.balance, user.energy = int(d['score']), int(d['energy'])
            await session.commit()
    return {"ok": True}

@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    await bot.set_webhook(url=f"{APP_URL}{WEBHOOK_PATH}", drop_pending_updates=True)

@app.post(WEBHOOK_PATH)
async def webhook(request: Request):
    data = await request.json()
    await dp.feed_update(bot, Update.model_validate(data, context={"bot": bot}))
    return Response(content='ok')

@dp.message(Command("start"))
async def start(m: types.Message):
    await m.answer("Феникс ждет!", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="🔥 ИГРАТЬ", web_app=types.WebAppInfo(url=APP_URL))]]))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
