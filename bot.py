import os, asyncio, json, time, logging
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery, Update
from sqlalchemy import Column, BigInteger, Integer, String, DateTime, update, select, desc, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# --- ТВОИ НАСТРОЙКИ ---
TOKEN = "8377110375:AAG31LE62g88acAmbSkdxk_pyeMRmLtqwdM"
APP_URL = "https://my-tap-bot.onrender.com" 
WEBHOOK_PATH = f"/webhook/{TOKEN}"

DB_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///db.sqlite3").strip().replace("postgres://", "postgresql+asyncpg://")
engine = create_async_engine(DB_URL)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()

# Твоя структура таблицы (со всеми колонками)
class User(Base):
    __tablename__ = 'users'
    user_id = Column(BigInteger, primary_key=True)
    username = Column(String)
    balance = Column(Integer, default=500)
    tap_power = Column(Integer, default=1)
    auto_power = Column(Integer, default=0)
    energy = Column(Integer, default=2500)
    max_energy = Column(Integer, default=2500)
    referrer_id = Column(BigInteger, nullable=True)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
bot = Bot(token=TOKEN)
dp = Dispatcher()

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("index.html", "r", encoding="utf-8") as f: return f.read()

# Получение данных (твоя старая логика)
@app.get("/get_user")
async def get_user(id: int):
    async with async_session() as session:
        user = await session.get(User, id)
        if not user:
            user = User(user_id=id)
            session.add(user); await session.commit(); await session.refresh(user)
        return {
            "score": user.balance, 
            "mult": user.tap_power, 
            "auto": user.auto_power, 
            "energy": user.energy, 
            "max_energy": user.max_energy
        }

# Исправленный ТОП (чтобы не было ошибок с именами)
@app.get("/get_top")
async def get_top():
    async with async_session() as session:
        res = await session.execute(select(User).order_by(desc(User.balance)).limit(10))
        users = res.scalars().all()
        return [{"username": u.username or f"Fenix_{str(u.user_id)[-4:]}", "balance": u.balance} for u in users]

# Сохранение (твоя старая логика)
@app.post("/s")
async def save(request: Request):
    d = await request.json()
    async with async_session() as session:
        user = await session.get(User, int(d['id']))
        if user:
            user.balance, user.energy = int(d['score']), int(d['energy'])
            await session.commit()
    return {"ok": True}

# --- ДОБАВЛЕННЫЙ БЛОК ЗВЕЗД (ВСТАВКА) ---
@app.post("/create_invoice")
async def create_invoice(request: Request):
    d = await request.json()
    prices = {
        "energy_5k": ["⚡ Энергия 5000", 100],
        "coins_1m": ["💰 1,000,000 монет", 500]
    }
    item = prices.get(d['type'])
    link = await bot.create_invoice_link(
        title=item[0],
        description="Покупка в Fenix Tap",
        payload=f"pay_{d['type']}_{d['id']}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=item[0], amount=item[1])]
    )
    return {"link": link}

@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)

@dp.message(F.successful_payment)
async def on_pay(m: types.Message):
    pay_data = m.successful_payment.invoice_payload.split('_')
    item, uid = pay_data[1], int(pay_data[2])
    async with async_session() as session:
        user = await session.get(User, uid)
        if user:
            if item == "energy_5k": user.max_energy = 5000; user.energy = 5000
            elif item == "coins_1m": user.balance += 1000000
            await session.commit()
# --- КОНЕЦ ВСТАВКИ ---

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
    # Сохраняем username при старте
    async with async_session() as session:
        user = await session.get(User, m.from_user.id)
        if not user:
            user = User(user_id=m.from_user.id, username=m.from_user.username)
            session.add(user)
        else:
            user.username = m.from_user.username
        await session.commit()
        
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="🔥 ИГРАТЬ", web_app=types.WebAppInfo(url=APP_URL))]])
    await m.answer("Феникс ждет тебя!", reply_markup=kb)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
