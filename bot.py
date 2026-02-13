import logging, os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from aiogram import Bot, Dispatcher, types
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandObject, Command
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, BigInteger, Integer, select

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8377110375:AAG3GmbEpQGyIcfzyOByu6qPUPVbxhYpPSg"
BASE_URL = "https://my-tap-bot.onrender.com"
DATABASE_URL = os.getenv("DATABASE_URL_FIXED")

logging.basicConfig(level=logging.INFO)
Base = declarative_base()
app = FastAPI()

# ЖЕСТКИЙ CORS (Разрешаем всё, чтобы кнопки ожили)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Очистка ссылки базы
clean_url = DATABASE_URL.replace("@://", "@").strip() if DATABASE_URL else ""
if clean_url and not clean_url.endswith("/fenix_tap"):
    clean_url = clean_url.rstrip("/") + "/fenix_tap"
if clean_url.startswith("postgresql://"):
    clean_url = clean_url.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(clean_url, pool_pre_ping=True)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class User(Base):
    __tablename__ = "users"
    user_id = Column(BigInteger, primary_key=True)
    score = Column(Integer, default=0)
    mult = Column(Integer, default=1)
    auto_rate = Column(Integer, default=0)

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await bot.set_webhook(f"{BASE_URL}/webhook", drop_pending_updates=True)
    logging.info("🚀 FENIX SYSTEM ONLINE")

bot = Bot(token=TOKEN)
dp = Dispatcher()

@app.get("/")
async def index():
    with open("index.html", "r", encoding="utf-8") as f: return HTMLResponse(f.read())

@app.get("/get_user/{user_id}")
async def get_user(user_id: int):
    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user: return {"score": 0, "mult": 1, "auto": 0}
        return {"score": int(user.score), "mult": int(user.mult), "auto": int(user.auto_rate)}

@app.post("/update_score")
async def update_score(data: dict):
    async with async_session() as session:
        user = await session.get(User, data['user_id'])
        if user:
            user.score = int(data['score'])
            user.mult = int(data.get('mult', user.mult))
            user.auto_rate = int(data.get('auto', user.auto_rate))
            await session.commit()
    return {"status": "ok"}

@app.get("/get_leaders")
async def get_leaders():
    async with async_session() as session:
        res = await session.execute(select(User).order_by(User.score.desc()).limit(10))
        return [{"id": str(l.user_id)[:5], "score": l.score} for l in res.scalars().all()]

@app.post("/webhook")
async def webhook(request: Request):
    update = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}

@dp.message(Command("start"))
async def start(m: types.Message):
    await m.answer("Добро пожаловать!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 ИГРАТЬ", web_app=WebAppInfo(url=BASE_URL))]
    ]))
