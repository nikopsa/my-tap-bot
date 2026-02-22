import os, asyncio, time, httpx, logging
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery, Update
from sqlalchemy import Column, BigInteger, Integer, String, select, desc, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")

# --- КОНФИГ ---
TOKEN = "8377110375:AAG31LE62g88acAmbSkdxk_pyeMRmLtqwdM"
APP_URL = "https://my-tap-bot.onrender.com" 
WEBHOOK_PATH = f"/webhook/{TOKEN}"

DB_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///db.sqlite3")
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DB_URL, pool_pre_ping=True)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    user_id = Column(BigInteger, primary_key=True)
    username = Column(String)
    balance = Column(Integer, default=1000)
    tap_power = Column(Integer, default=1)
    auto_power = Column(Integer, default=0)
    energy = Column(Integer, default=2500)
    max_energy = Column(Integer, default=2500)
    last_save = Column(Integer, default=lambda: int(time.time()))
    last_bonus = Column(Integer, default=0)
    referrer_id = Column(BigInteger, nullable=True)

bot = Bot(token=TOKEN)
dp = Dispatcher()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Проверка базы данных...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Принудительное добавление колонок для PostgreSQL
        cols = [("last_save", "INTEGER DEFAULT 0"), ("last_bonus", "INTEGER DEFAULT 0"), ("referrer_id", "BIGINT"), ("auto_power", "INTEGER DEFAULT 0")]
        for col, c_type in cols:
            try: await conn.execute(text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {c_type}"))
            except: pass
        # Сброс NULL значений в автомайнинге
        await conn.execute(text("UPDATE users SET auto_power = 0 WHERE auto_power IS NULL"))

    await bot.set_webhook(url=f"{APP_URL}{WEBHOOK_PATH}", drop_pending_updates=True)
    yield
    await engine.dispose()

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/", response_class=HTMLResponse)
async def index():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f: return f.read()
    return "<h1>Server is Live</h1>"

@app.post(WEBHOOK_PATH)
async def handle_webhook(request: Request):
    try:
        data = await request.json()
        update = Update.model_validate(data, context={"bot": bot})
        await dp.feed_update(bot, update)
        return Response(content="ok")
    except Exception as e:
        logger.error(f"Error: {e}")
        return Response(status_code=500)

@app.get("/get_user")
async def get_user(id: int):
    async with async_session() as session:
        user = await session.get(User, id)
        if not user:
            user = User(user_id=id, balance=1000, tap_power=1, auto_power=0, energy=2500, max_energy=2500)
            session.add(user)
            await session.commit()
            await session.refresh(user)
        return {"score": int(user.balance), "mult": int(user.tap_power or 1), "auto": int(user.auto_power or 0), "energy": int(user.energy), "max_energy": int(user.max_energy)}

@app.post("/s")
async def save(request: Request):
    d = await request.json()
    now = int(time.time())
    async with async_session() as session:
        user = await session.get(User, int(d['id']))
        if user:
            elapsed = max(now - (user.last_save or now), 1)
            limit = ((user.tap_power * 30) + (user.auto_power or 0)) * elapsed + 3000
            diff = int(d['score']) - user.balance
            if 0 <= diff <= limit:
                user.balance, user.energy, user.last_save = int(d['score']), int(d['energy']), now
                await session.commit()
    return {"ok": True}

@app.post("/create_invoice")
async def create_invoice(request: Request):
    d = await request.json()
    prices = {
        "pack_light": ["⚡ Легкий старт (+8/с)", 100],
        "pack_mult": ["🚀 Мультитапер x5", 250],
        "pack_5m": ["💰 5M Монет", 999]
    }
    item = prices.get(d['type'], ["Донат", 100])
    link = await bot.create_invoice_link(title=item[0], description="Phoenix Upgrade", payload=f"buy_{d['type']}_{d['id']}", provider_token="", currency="XTR", prices=[LabeledPrice(label=item[0], amount=item[1])])
    return {"link": link}

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    now = int(time.time())
    name = m.from_user.first_name
    is_ru = m.from_user.language_code == 'ru'
    bonus_received = False
    
    async with async_session() as session:
        user = await session.get(User, m.from_user.id)
        if not user:
            args = m.text.split()
            ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
            if ref_id and ref_id != m.from_user.id:
                ref = await session.get(User, ref_id)
                if ref: ref.balance += 10000
            user = User(user_id=m.from_user.id, username=m.from_user.username, balance=1000, last_save=now, last_bonus=now)
            session.add(user)
            await session.commit()
        else:
            if now - (user.last_bonus or 0) > 86400:
                user.balance += 10000
                user.last_bonus = now
                await session.commit()
                bonus_received = True

    if is_ru:
        msg = f"🔥 Добро пожаловать, {name}!\n"
        if bonus_received: msg += "🎁 Твой бонус: +10,000 монет!\n"
        msg += "Твои сокровища ждут тебя."
        btn = "💸 ИГРАТЬ"
    else:
        msg = f"🔥 Welcome, {name}!\n"
        if bonus_received: msg += "🎁 Your bonus: +10,000 coins!\n"
        msg += "Your treasures are waiting."
        btn = "💸 PLAY"
    
    await m.answer(msg, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text=btn, web_app=types.WebAppInfo(url=APP_URL))]]))

@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)

@dp.message(F.successful_payment)
async def on_pay(m: types.Message):
    data = m.successful_payment.invoice_payload.split('_')
    async with async_session() as session:
        user = await session.get(User, int(data[2]))
        if user:
            if data[1] == "pack_light": user.auto_power = (user.auto_power or 0) + 8
            elif data[1] == "pack_mult": user.tap_power = (user.tap_power or 1) + 5
            elif data[1] == "pack_5m": user.balance += 5000000
            await session.commit()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
            
