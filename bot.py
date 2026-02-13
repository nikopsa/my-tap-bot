import logging
import os
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, BigInteger, Integer

# --- НАСТРОЙКИ ---
TOKEN = "8377110375:AAG3GmbEpQGyIcfzyOByu6qPUPVbxhYpPSg"
BASE_URL = "https://my-tap-bot.onrender.com"

logging.basicConfig(level=logging.INFO)
Base = declarative_base()
app = FastAPI()
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Супер-обработка URL: чистим всё, что может сломать запуск
raw_url = os.getenv("DATABASE_URL_FIXED", "")
clean_url = raw_url.replace("@://", "@").replace(":@", "@").strip()
if clean_url and not clean_url.endswith("/fenix_tap"):
    clean_url += "/fenix_tap"

# Создаем движок только если ссылка не пустая, иначе — заглушка
engine = None
if "postgresql" in clean_url:
    try:
        engine = create_async_engine(clean_url, pool_pre_ping=True)
        async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    except Exception as e:
        logging.error(f"Ошибка инициализации движка: {e}")
        engine = None

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
            logging.info("✅ БАЗА ПРИНЯТА")
        except Exception as e:
            logging.error(f"❌ БАЗА НЕ ОТВЕТИЛА: {e}")
    
    await bot.set_webhook(f"{BASE_URL}/webhook", drop_pending_updates=True)
    logging.info("🚀 СЕРВЕР ЗАПУЩЕН")

@app.get("/", response_class=HTMLResponse)
async def index():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Файл index.html не найден</h1>"

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
    await message.answer("Погнали тапать!", reply_markup=markup)

@app.get("/get_user/{user_id}")
async def get_user(user_id: int):
    if not engine: return {"score": 0}
    async with async_session() as session:
        user = await session.get(User, user_id)
        return {"score": user.score if user else 0}

@app.post("/update_score")
async def update_score(data: dict):
    if not engine: return {"status": "no_db"}
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
