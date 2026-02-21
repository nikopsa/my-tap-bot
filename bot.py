import os, asyncio, time, httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery, Update
from sqlalchemy import Column, BigInteger, Integer, String, select, desc
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# --- КОНФИГ ---
TOKEN = "8377110375:AAG31LE62g88acAmbSkdxk_pyeMRmLtqwdM"
# СЮДА ВСТАВЬ СВОЮ ССЫЛКУ ИЗ RENDER (БЕЗ СЛЭША В КОНЦЕ!)
APP_URL = "https://my-tap-bot.onrender.com" 
WEBHOOK_PATH = f"/webhook/{TOKEN}"

# Авто-настройка БД (SQLite или Postgres)
DB_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///db.sqlite3")
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DB_URL)
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
    last_save = Column(Integer, default=int(time.time()))
    referrer_id = Column(BigInteger, nullable=True)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- LIFESPAN (Запуск и стоп) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # При старте
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await bot.set_webhook(url=f"{APP_URL}{WEBHOOK_PATH}", drop_pending_updates=True)
    ping_task = asyncio.create_task(keep_alive())
    yield
    # При выключении
    await bot.delete_webhook()
    ping_task.cancel()

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

async def keep_alive():
    async with httpx.AsyncClient() as client:
        while True:
            await asyncio.sleep(600)
            try: await client.get(APP_URL)
            except: pass

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("index.html", "r", encoding="utf-8") as f: return f.read()

@app.get("/get_user")
async def get_user(id: int):
    async with async_session() as session:
        user = await session.get(User, id)
        if not user:
            user = User(user_id=id, last_save=int(time.time()))
            session.add(user); await session.commit(); await session.refresh(user)
        return {"score": user.balance, "mult": user.tap_power, "auto": user.auto_power, "energy": user.energy, "max_energy": user.max_energy}

@app.get("/get_top")
async def get_top():
    async with async_session() as session:
        res = await session.execute(select(User).order_by(desc(User.balance)).limit(10))
        return [{"username": u.username or f"Fen_{str(u.user_id)[-4:]}", "balance": u.balance} for u in res.scalars().all()]

@app.post("/s")
async def save(request: Request):
    d = await request.json()
    now = int(time.time())
    async with async_session() as session:
        user = await session.get(User, int(d['id']))
        if user:
            elapsed = max(now - user.last_save, 1)
            limit = ((user.tap_power * 20) + user.auto_power) * elapsed + 1000
            diff = int(d['score']) - user.balance
            if 0 <= diff <= limit:
                user.balance, user.energy, user.last_save = int(d['score']), int(d['energy']), now
                await session.commit()
    return {"ok": True}

@app.post("/create_invoice")
async def create_invoice(request: Request):
    d = await request.json()
    prices = {"pack_mult": ["🚀 Мультитапер x5", 250], "pack_energy": ["⚡ Энерго-Монстр", 150], "pack_5m": ["💰 5M Монет", 999]}
    item = prices.get(d['type'])
    link = await bot.create_invoice_link(title=item[0], description="VIP", payload=f"buy_{d['type']}_{d['id']}", provider_token="", currency="XTR", prices=[LabeledPrice(label=item[0], amount=item[1])])
    return {"link": link}

@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery): await q.answer(ok=True)

@dp.message(F.successful_payment)
async def on_pay(m: types.Message):
    data = m.successful_payment.invoice_payload.split('_')
    async with async_session() as session:
        user = await session.get(User, int(data[2]))
        if user:
            if data[1] == "pack_mult": user.tap_power += 5
            elif data[1] == "pack_energy": user.max_energy = 10000; user.energy = 10000
            elif data[1] == "pack_5m": user.balance += 5000000
            await session.commit()

@app.post(WEBHOOK_PATH)
async def webhook(request: Request):
    data = await request.json()
    await dp.feed_update(bot, Update.model_validate(data, context={"bot": bot}))
    return Response(content='ok')

@dp.message(Command("start"))
async def start(m: types.Message):
    async with async_session() as session:
        user = await session.get(User, m.from_user.id)
        if not user:
            user = User(user_id=m.from_user.id, username=m.from_user.username)
            session.add(user); await session.commit()
    await m.answer("🔥 Погнали!", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="💸 ИГРАТЬ", web_app=types.WebAppInfo(url=APP_URL))]]))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
