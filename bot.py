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

TOKEN = "8377110375:AAG3GmbEpQGyIcfzyOByu6qPUPVbxhYpPSg"
BASE_URL = "https://my-tap-bot.onrender.com"
DATABASE_URL = os.getenv("DATABASE_URL_FIXED")

logging.basicConfig(level=logging.INFO)
Base = declarative_base()
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

clean_url = DATABASE_URL.replace("@://", "@").strip()
engine = create_async_engine(clean_url, echo=False)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class User(Base):
    __tablename__ = "users"
    user_id = Column(BigInteger, primary_key=True)
    score = Column(Integer, default=0)
    mult = Column(Integer, default=1)
    auto_rate = Column(Integer, default=0) # Очков в секунду

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await bot.set_webhook(f"{BASE_URL}/webhook", drop_pending_updates=True)

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
        return {"score": user.score, "mult": user.mult, "auto": user.auto_rate}

@app.post("/update_score")
async def update_score(data: dict):
    async with async_session() as session:
        user = await session.get(User, data['user_id'])
        if user:
            user.score = data['score']
            user.mult = data.get('mult', user.mult)
            user.auto_rate = data.get('auto', user.auto_rate)
            await session.commit()
    return {"status": "ok"}

@app.get("/get_leaders")
async def get_leaders():
    async with async_session() as session:
        result = await session.execute(select(User).order_by(User.score.desc()).limit(10))
        return [{"id": str(l.user_id)[:5] + "..", "score": l.score} for l in result.scalars().all()]

@app.post("/webhook")
async def webhook(request: Request):
    update = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}

@dp.message(Command("start"))
async def start_cmd(message: types.Message, command: CommandObject):
    # (Тут остается твоя логика рефералов из прошлого шага)
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚀 ИГРАТЬ", web_app=WebAppInfo(url=BASE_URL))]])
    await message.answer("Fenix Tap запущен!", reply_markup=markup)
