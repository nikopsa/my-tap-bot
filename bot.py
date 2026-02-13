import os, logging, re
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from aiogram import Bot, Dispatcher, types
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, BigInteger, Integer, select

# Настройки
TOKEN = "8377110375:AAG3GmbEpQGyIcfzyOByu6qPUPVbxhYpPSg"
URL = "https://my-tap-bot.onrender.com"
RAW_DB = os.getenv("DATABASE_URL_FIXED", "")

# Жесткий фикс ссылки: убираем мусор, ставим asyncpg и имя базы
DB_URL = re.sub(r':(?=/|$)', '', RAW_DB.replace("@://", "@").replace("postgresql://", "postgresql+asyncpg://")).strip()
if not DB_URL.endswith("/fenix_tap"): DB_URL = DB_URL.rstrip("/") + "/fenix_tap"

logging.basicConfig(level=logging.INFO)
Base = declarative_base()
engine = create_async_engine(DB_URL, pool_pre_ping=True)
Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class User(Base):
    __tablename__ = "users"; id = Column(BigInteger, primary_key=True)
    score = Column(Integer, default=0); mult = Column(Integer, default=1); auto = Column(Integer, default=0)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
bot, dp = Bot(TOKEN), Dispatcher()

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    await bot.set_webhook(f"{URL}/webhook")
    logging.info("🔥 SuPerKLikEr ENGINE ONLINE")

@app.get("/", response_class=HTMLResponse)
async def index(): return open("index.html", encoding="utf-8").read()

@app.get("/u/{uid}")
async def get_u(uid: int):
    async with Session() as s:
        u = await s.get(User, uid)
        if not u: u = User(id=uid); s.add(u); await s.commit()
        return {"score": u.score, "mult": u.mult, "auto": u.auto}

@app.post("/s")
async def save(r: Request):
    d = await r.json()
    async with Session() as s:
        u = await s.get(User, d['id'])
        if u: u.score, u.mult, u.auto = int(d['score']), int(d['mult']), int(d['auto']); await s.commit()
    return {"ok": True}

@app.get("/top")
async def top():
    async with Session() as s:
        res = await s.execute(select(User).order_by(User.score.desc()).limit(10))
        return [{"id": l.id, "s": l.score} for l in res.scalars().all()]

@app.post("/webhook")
async def wh(r: Request):
    await dp.feed_update(bot, types.Update.model_validate(await r.json(), context={"bot": bot}))
    return {"ok": True}

@dp.message()
async def st(m: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚀 ИГРАТЬ", web_app=WebAppInfo(url=URL))]])
    await m.answer("🔥 SuPerKLikEr", reply_markup=kb)
