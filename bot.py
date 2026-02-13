import logging
import os
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, BigInteger, Integer
from sqlalchemy.engine.url import make_url

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8377110375:AAG3GmbEpQGyIcfzyOByu6qPUPVbxhYpPSg"
BASE_URL = "https://my-tap-bot.onrender.com"
RAW_URL = "postgresql+asyncpg://fenix_tap_user:37ZKR3PCPIzEJ8VlOMNCwWPQ45azPJzw@://dpg-d67h43umcj7s739dfee0-a.oregon-postgres.render.com"

# Очистка URL: удаляем порт, если он пустой, и исправляем формат
db_url_obj = make_url(RAW_URL.replace("postgresql://", "postgresql+asyncpg://"))
if db_url_obj.port is None:
    # Принудительно убираем двоеточие, которое вызывает ValueError
    DATABASE_URL = str(db_url_obj).replace(":None", "").replace("/None", "")
else:
    DATABASE_URL = str(db_url_obj)

logging.basicConfig(level=logging.INFO)

# --- БАЗА ДАННЫХ ---
Base = declarative_base()
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class User(Base):
    __tablename__ = "users"
    user_id = Column(BigInteger, primary_key=True)
    score = Column(Integer, default=0)

# --- ПРИЛОЖЕНИЕ ---
bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

@app.on_event("startup")
async def startup():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await bot.set_webhook(f"{BASE_URL}/webhook", drop_pending_updates=True)
        logging.info("🔥 FENIX SYSTEM ONLINE 🔥")
    except Exception as e:
        logging.error(f"CRITICAL STARTUP ERROR: {e}")

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = types.Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}

@dp.message()
async def start_handler(message: types.Message):
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 ИГРАТЬ (FENIX TAP)", web_app=WebAppInfo(url=BASE_URL))]
    ])
    await message.answer(f"Привет, {message.from_user.first_name}! Тапай и копи очки!", reply_markup=markup)

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/get_user/{user_id}")
async def get_user(user_id: int):
    async with async_session() as session:
        user = await session.get(User, user_id)
        return {"score": user.score if user else 0}

@app.post("/update_score")
async def update_score(data: dict):
    user_id = data.get("user_id")
    score = data.get("score")
    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            user = User(user_id=user_id, score=score)
            session.add(user)
        else:
            user.score = score
        await session.commit()
    return {"status": "ok"}
