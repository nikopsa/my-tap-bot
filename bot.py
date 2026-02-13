import os, logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from aiogram import Bot, Dispatcher, types
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, BigInteger, Integer, select

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8377110375:AAG3GmbEpQGyIcfzyOByu6qPUPVbxhYpPSg"
URL = "https://my-tap-bot.onrender.com"

# ВБИТО ЖЕСТКО: ИМЯ БАЗЫ fenix_tap В КОНЦЕ ОБЯЗАТЕЛЬНО
DATABASE_URL = "postgresql+asyncpg://fenix_tap_user:37ZKR3PCPIzEJ8VlOMNCwWPQ45azPJzw@://dpg-d67h43umcj7s739dfee0-a.oregon-postgres.render.com"

logging.basicConfig(level=logging.INFO)
Base = declarative_base()
engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True)
    score = Column(Integer, default=0)
    mult = Column(Integer, default=1)
    auto = Column(Integer, default=0)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
bot = Bot(TOKEN)
dp = Dispatcher()

@app.on_event("startup")
async def startup():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await bot.set_webhook(f"{URL}/webhook")
        logging.info("✅ БАЗА ПОДКЛЮЧЕНА: FENIX_TAP")
    except Exception as e:
        logging.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/u/{uid}")
async def get_u(uid: int):
    async with Session() as s:
        u = await s.get(User, uid)
        if not u:
            u = User(id=uid, score=0, mult=1, auto=0)
            s.add(u)
            await s.commit()
            return {"score": 0, "mult": 1, "auto": 0}
        return {"score": int(u.score), "mult": int(u.mult), "auto": int(u.auto)}

@app.post("/s")
async def save(request: Request):
    d = await request.json()
    async with Session() as s:
        u = await s.get(User, int(d['id']))
        if u:
            u.score, u.mult, u.auto = int(d['score']), int(d['mult']), int(d['auto'])
            await s.commit()
    return {"ok": True}

@app.get("/top")
async def top():
    async with Session() as s:
        res = await s.execute(select(User).order_by(User.score.desc()).limit(10))
        return [{"id": l.id, "s": l.score} for l in res.scalars().all()]

@app.post("/webhook")
async def wh(r: Request):
    upd = types.Update.model_validate(await r.json(), context={"bot": bot})
    await dp.feed_update(bot, upd)
    return {"ok": True}

@dp.message()
async def st(m: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚀 ИГРАТЬ", web_app=WebAppInfo(url=URL))]])
    await m.answer("SuPerKLikEr ЖДЕТ ТЕБЯ!", reply_markup=kb)
