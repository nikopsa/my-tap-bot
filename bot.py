import os, asyncio, json, time, logging, httpx
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import LabeledPrice, PreCheckoutQuery, Update
from sqlalchemy import Column, BigInteger, Integer, String, DateTime, update, select, desc, func, text, Boolean
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8377110375:AAG31LE62g88acAmbSkdxk_pyeMRmLtqwdM"
APP_URL = "https://my-tap-bot.onrender.com" 
WEBHOOK_PATH = f"/webhook/{TOKEN}"

DB_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///db.sqlite3").strip().replace("postgres://", "postgresql+asyncpg://")
engine = create_async_engine(DB_URL, pool_pre_ping=True)
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
    last_touch = Column(Integer, default=int(time.time()))
    streak = Column(Integer, default=0)
    last_checkin = Column(DateTime, default=datetime.utcnow() - timedelta(days=1))
    referrer_id = Column(BigInteger, nullable=True)
    is_banned = Column(Boolean, default=False)
    boost_end = Column(DateTime, nullable=True)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- ФОНОВЫЕ ЗАДАЧИ ---
async def keep_alive():
    async with httpx.AsyncClient() as client:
        while True:
            try: await client.get(APP_URL)
            except: pass
            await asyncio.sleep(600) # 10 минут

async def recovery():
    while True:
        await asyncio.sleep(60)
        try:
            async with async_session() as session:
                await session.execute(update(User).where(User.energy < User.max_energy).values(
                    energy=func.least(User.max_energy, User.energy + 25)
                ))
                await session.commit()
        except: pass

# --- API ЭНДПОИНТЫ ---
@app.get("/", response_class=HTMLResponse)
async def index():
    with open("index.html", "r", encoding="utf-8") as f: return f.read()

@app.get("/get_user")
async def get_user(id: int):
    async with async_session() as session:
        user = await session.get(User, id)
        if not user:
            user = User(user_id=id, last_touch=int(time.time()))
            session.add(user); await session.commit(); await session.refresh(user)
        
        bonus_auto = 0
        if user.boost_end and user.boost_end > datetime.utcnow():
            bonus_auto = 50
            
        return {
            "score": user.balance, 
            "mult": user.tap_power, 
            "auto": user.auto_power + bonus_auto, 
            "energy": user.energy, 
            "max_energy": user.max_energy,
            "boost_active": bonus_auto > 0
        }

@app.post("/s")
async def save(request: Request):
    d = await request.json()
    uid = int(d['id'])
    async with async_session() as session:
        user = await session.get(User, uid)
        if user and not user.is_banned:
            user.balance, user.energy, user.last_touch = int(d['score']), int(d['energy']), int(time.time())
            await session.commit()
    return {"ok": True}

@app.post("/buy_miner")
async def buy_miner(request: Request):
    d = await request.json()
    async with async_session() as session:
        user = await session.get(User, int(d['id']))
        cost = (user.auto_power + 1) * 1200
        if user.balance >= cost:
            user.balance -= cost
            user.auto_power += 1
            await session.commit()
            return {"ok": True, "auto": user.auto_power, "balance": user.balance}
        return {"ok": False}

@app.post("/create_miner_invoice")
async def cmi(request: Request):
    d = await request.json()
    p = {
        "star_mini": ["Птенец", 150, 5], 
        "star_mega": ["Король", 500, 25],
        "boost_7d": ["Огненный Буст (7 дней)", 300, 50],
        "energy_5k": ["Энергия 5000", 100, 0]
    }.get(d['type'])
    
    link = await bot.create_invoice_link(title=p[0], description=f"Улучшение профиля", payload=f"pay_{d['type']}_{d['id']}", provider_token="", currency="XTR", prices=[LabeledPrice(label="Stars", amount=p[1])])
    return {"link": link}

# --- ОБРАБОТКА ПЛАТЕЖЕЙ ---
@dp.pre_checkout_query()
async def pre(q: PreCheckoutQuery): await q.answer(ok=True)

@dp.message(F.successful_payment)
async def pay_ok(m: types.Message):
    pay = m.successful_payment.invoice_payload.split('_')
    uid = int(pay[2])
    async with async_session() as session:
        user = await session.get(User, uid)
        if user:
            p_type = pay[1]
            if p_type == "star_mini": user.auto_power += 5
            elif p_type == "star_mega": user.auto_power += 25
            elif p_type == "energy_5k": 
                user.max_energy = 5000
                user.energy = 5000
            elif p_type == "boost_7d":
                user.boost_end = datetime.utcnow() + timedelta(days=7)
            await session.commit()

# --- ЗАПУСК И ИНИЦИАЛИЗАЦИЯ (ИСПРАВЛЕНО) ---
@app.on_event("startup")
async def on_startup():
    # 1. Создание базовых таблиц
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 2. Безопасное добавление колонок по одной (для PostgreSQL)
    columns_to_add = [
        ("is_banned", "BOOLEAN DEFAULT FALSE"),
        ("boost_end", "TIMESTAMP")
    ]
    
    for col_name, col_type in columns_to_add:
        async with engine.begin() as conn:
            try:
                await conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))
                logger.info(f"Колонка {col_name} добавлена.")
            except Exception:
                logger.info(f"Колонка {col_name} уже существует.")

    # 3. Вебхук и задачи
    await bot.set_webhook(url=f"{APP_URL}{WEBHOOK_PATH}", drop_pending_updates=True)
    asyncio.create_task(recovery())
    asyncio.create_task(keep_alive())

@app.post(WEBHOOK_PATH)
async def webhook(request: Request):
    data = await request.json()
    await dp.feed_update(bot, Update.model_validate(data, context={"bot": bot}))
    return Response(content='ok')

@dp.message(Command("start"))
async def start(m: types.Message):
    builder = InlineKeyboardBuilder().button(text="🔥 ИГРАТЬ", web_app=types.WebAppInfo(url=APP_URL))
    await m.answer("Феникс пробудился! Начинай тапать прямо сейчас.", reply_markup=builder.as_markup())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
