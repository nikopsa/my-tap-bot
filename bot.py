import os, asyncio, json, time, httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery, Update
from sqlalchemy import Column, BigInteger, Integer, String, select, desc
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

TOKEN = "8377110375:AAG31LE62g88acAmbSkdxk_pyeMRmLtqwdM"
APP_URL = "https://my-tap-bot.onrender.com" 
WEBHOOK_PATH = f"/webhook/{TOKEN}"

DB_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///db.sqlite3").strip().replace("postgres://", "postgresql+asyncpg://")
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

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
bot = Bot(token=TOKEN)
dp = Dispatcher()

async def keep_alive():
    async with httpx.AsyncClient() as client:
        while True:
            try: await client.get(APP_URL)
            except: pass
            await asyncio.sleep(600)

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

@app.post("/s")
async def save(request: Request):
    d = await request.json()
    now = int(time.time())
    async with async_session() as session:
        user = await session.get(User, int(d['id']))
        if user:
            elapsed = now - user.last_save
            limit = ((user.tap_power * 15) + user.auto_power) * elapsed + 2000
            diff = int(d['score']) - user.balance
            if 0 <= diff <= limit:
                user.balance = int(d['score'])
                user.energy = int(d['energy'])
                user.last_save = now
                await session.commit()
    return {"ok": True}

# --- МАГАЗИН ПРЯМОЙ ПРИБЫЛИ ---
@app.post("/create_invoice")
async def create_invoice(request: Request):
    d = await request.json()
    # Цены в Звездах (XTR)
    offers = {
        "pack_mult": ["🚀 Мультитапер x5", "Увеличивает силу клика навсегда!", 250],
        "pack_energy": ["⚡ Энерго-Монстр", "Лимит энергии 10,000", 150],
        "pack_1m": ["💰 Сундук Феникса (1M)", "Миллион монет мгновенно", 400],
        "pack_5m": ["💎 Казна Империи (5M)", "Пять миллионов монет", 999]
    }
    item = offers.get(d['type'])
    link = await bot.create_invoice_link(
        title=item[0],
        description=item[1],
        payload=f"buy_{d['type']}_{d['id']}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=item[0], amount=item[2])]
    )
    return {"link": link}

@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery): await q.answer(ok=True)

@dp.message(F.successful_payment)
async def on_pay(m: types.Message):
    data = m.successful_payment.invoice_payload.split('_')
    item, uid = data[1], int(data[2])
    async with async_session() as session:
        user = await session.get(User, uid)
        if user:
            if item == "pack_mult": user.tap_power += 5
            elif item == "pack_energy": user.max_energy = 10000; user.energy = 10000
            elif item == "pack_1m": user.balance += 1000000
            elif item == "pack_5m": user.balance += 5000000
            await session.commit()

@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    await bot.set_webhook(url=f"{APP_URL}{WEBHOOK_PATH}")
    asyncio.create_task(keep_alive())

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
            session.add(User(user_id=m.from_user.id, username=m.from_user.username))
            await session.commit()
    await m.answer("🔥 Время зарабатывать!", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="💸 ВОЙТИ В ИГРУ", web_app=types.WebAppInfo(url=APP_URL))]]))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
