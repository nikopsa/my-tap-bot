import logging
import os
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

logging.basicConfig(level=logging.INFO)
Base = declarative_base()
app = FastAPI()
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ЖЕСТКАЯ ОЧИСТКА ССЫЛКИ
raw_url = os.getenv("DATABASE_URL_FIXED", "")
# Убираем ту самую хрень "@://" и заменяем на нормальный "@"
clean_url = raw_url.replace("@://", "@").strip()

# Добавляем имя базы в конец, если его нет
if clean_url and not clean_url.endswith("/fenix_tap"):
    clean_url = clean_url.rstrip("/") + "/fenix_tap"

engine = None
if "postgresql" in clean_url:
    try:
        # Создаем движок из УЖЕ ЧИСТОЙ ссылки
        engine = create_async_engine(clean_url, pool_pre_ping=True)
        async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        logging.info(f"✅ Ссылка очищена и принята")
    except Exception as e:
        logging.error(f"❌ Ошибка в очищенной ссылке: {e}")

class User(Base):
    __tablename__ = "users"
    user_id = Column(BigInteger, primary_key=True)
    score = Column(Integer, default=0)

@app.on_event("startup")
async def startup():
    if engine:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logging.info("✅ База данных готова к работе")
        except Exception as e:
            logging.error(f"❌ База не ответила: {e}")
    
    await bot.set_webhook(f"{BASE_URL}/webhook", drop_pending_updates=True)
    logging.info("🚀 БОТ ЗАПУЩЕН")

@app.get("/", response_class=HTMLResponse)
async def index():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "<h1>Загрузка игры...</h1>"

@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
        update = types.Update.model_validate(data, context={"bot": bot})
        await dp.feed_update(bot, update)
    except: pass
    return {"ok": True}

@dp.message()
async def start_handler(message: types.Message):
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 ИГРАТЬ", web_app=WebAppInfo(url=BASE_URL))]
    ])
    await message.answer("Погнали тапать!", reply_markup=markup)

@app.get("/get_user/{user_id}")
async def get_user(user_id: int):
    if not engine: return {"score": 0}
    async with async_session() as session:
        user = await session.get(User, user_id)
        return {"score": user.score if user else 0}

@app.post("/update_score")
async def update_score(data: dict):
    if not engine: return {"status": "error"}
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
