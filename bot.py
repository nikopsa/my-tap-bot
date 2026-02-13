import logging
import os
import asyncio
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, BigInteger, Integer

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8377110375:AAG3GmbEpQGyIcfzyOByu6qPUPVbxhYpPSg"
BASE_URL = "https://my-tap-bot.onrender.com"

# Собираем URL напрямую, чтобы исключить любые ошибки парсинга
DATABASE_URL = "postgresql+asyncpg://fenix_tap_user:37ZKR3PCPIzEJ8VlOMNCwWPQ45azPJzw@://dpg-d67h43umcj7s739dfee0-a.oregon-postgres.render.com"

logging.basicConfig(level=logging.INFO)
Base = declarative_base()

# Настройка движка с защитой от разрыва соединения
engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class User(Base):
    __tablename__ = "users"
    user_id = Column(BigInteger, primary_key=True)
    score = Column(Integer, default=0)

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

@app.on_event("startup")
async def startup():
    # Попытка создать таблицы, но не падать при ошибке
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logging.info("✅ ТАБЛИЦЫ СОЗДАНЫ ИЛИ УЖЕ ЕСТЬ")
    except Exception as e:
        logging.error(f"❌ ОШИБКА БАЗЫ (НО БОТ ЗАПУСКАЕТСЯ): {e}")
    
    await bot.set_webhook(f"{BASE_URL}/webhook", drop_pending_updates=True)
    logging.info("🚀 БОТ ОНЛАЙН")

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = types.Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}

@dp.message()
async def start_handler(message: types.Message):
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 ИГРАТЬ", web_app=WebAppInfo(url=BASE_URL))]
    ])
    await message.answer(f"Привет! Твой счет в безопасности.", reply_markup=markup)

@app.get("/", response_class=HTMLResponse)
async def index():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Файл index.html не найден</h1>"

@app.get("/get_user/{user_id}")
async def get_user(user_id: int):
    try:
        async with async_session() as session:
            user = await session.get(User, user_id)
            return {"score": user.score if user else 0}
    except:
        return {"score": 0}

@app.post("/update_score")
async def update_score(data: dict):
    user_id = data.get("user_id")
    score = data.get("score")
    try:
        async with async_session() as session:
            user = await session.get(User, user_id)
            if not user:
                user = User(user_id=user_id, score=score)
                session.add(user)
            else:
                user.score = score
            await session.commit()
    except Exception as e:
        logging.error(f"Ошибка сохранения: {e}")
    return {"status": "ok"}
