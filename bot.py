import os, asyncio, json, time, logging
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import LabeledPrice, PreCheckoutQuery
from sqlalchemy import Column, BigInteger, Integer, String, DateTime, update, select, desc, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# Логирование для контроля атак
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- НАСТРОЙКИ ---
TOKEN = "8377110375:AAG31LE62g88acAmbSkdxk_pyeMRmLtqwdM"
ADMIN_ID = 1292046104 
APP_URL = "https://my-tap-bot.onrender.com" 

# Оптимизированное подключение к БД
DB_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///db.sqlite3").strip().replace("postgres://", "postgresql+asyncpg://")
engine = create_async_engine(DB_URL, pool_pre_ping=True, pool_size=20, max_overflow=10)
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
    last_save = Column(Integer, default=int(time.time())) # ЗАЩИТА ОТ СПАМА
    last_bonus = Column(DateTime, default=datetime.utcnow() - timedelta(days=1))
    referrer_id = Column(BigInteger, nullable=True)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- API С ЗАЩИТОЙ ---

@app.get("/u/{uid}")
async def get_user(uid: int):
    async with async_session() as session:
        user = await session.get(User, uid)
        if not user:
            user = User(user_id=uid, last_touch=int(time.time()))
            session.add(user); await session.commit(); await session.refresh(user)
        
        now = int(time.time())
        offline_earned = (now - user.last_touch) * user.auto_power
        if offline_earned > 0:
            # Ограничение оффлайн дохода за раз (защита)
            offline_earned = min(offline_earned, 1000000) 
            user.balance += offline_earned
            user.last_touch = now
            await session.commit()
            
        return {"score": user.balance, "mult": user.tap_power, "auto": user.auto_power, "energy": user.energy, "max_energy": user.max_energy, "offline": offline_earned}

@app.post("/s")
async def save_user(request: Request):
    data = await request.json()
    uid, now = int(data['id']), int(time.time())
    
    async with async_session() as session:
        user = await session.get(User, uid)
        if not user: return {"status": "error"}

        # 🛡 ЗАЩИТА №1: Анти-флуд (не чаще раз в 2 сек)
        if now - user.last_save < 2:
            return {"status": "too_fast"}

        # 🛡 ЗАЩИТА №2: Математическая проверка (не более 1000 монет в сек)
        time_diff = now - user.last_save
        max_possible = (time_diff * user.tap_power * 10) + (time_diff * user.auto_power) + 500
        if (data['score'] - user.balance) > max_possible:
            logger.warning(f"Cheat detected for user {uid}")
            return {"status": "cheat_detected"}

        user.balance = data['score']
        user.tap_power = data['mult']
        user.auto_power = data['auto']
        user.energy = data['energy']
        user.last_save = now
        user.last_touch = now
        await session.commit()
    return {"status": "ok"}

@app.get("/top")
async def get_top():
    async with async_session() as session:
        result = await session.execute(select(User).order_by(desc(User.balance)).limit(10))
        users = result.scalars().all()
        return [{"n": u.username or "Player", "s": u.balance} for u in users]

@app.post("/reward_ad")
async def reward_ad(request: Request):
    data = await request.json()
    async with async_session() as session:
        user = await session.get(User, int(data['id']))
        if user:
            user.balance += 5000; await session.commit()
            return {"status": "ok", "new_balance": user.balance}
    return {"status": "error"}

# --- ПЛАТЕЖИ (STARS) ---

@app.get("/create_invoice/{uid}/{item}")
async def create_invoice(uid: int, item: str):
    prices = {"mult": 50, "energy": 100}
    amt = prices.get(item, 50)
    link = await bot.create_invoice_link(
        title="Fenix Boost", 
        description="Upgrade your power!", 
        payload=f"{uid}_{item}", 
        provider_token="", 
        currency="XTR", 
        prices=[LabeledPrice(label="Stars", amount=amt)]
    )
    return {"link": link}

@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery): await q.answer(ok=True)

@dp.message(F.successful_payment)
async def pay_ok(m: types.Message):
    p = m.successful_payment.invoice_payload.split("_")
    uid, item = int(p[0]), p[1]
    async with async_session() as session:
        user = await session.get(User, uid)
        if item == "mult": user.tap_power += 1
        else: user.max_energy += 5000; user.energy = user.max_energy
        await session.commit()
    await m.answer("🔥 Улучшение успешно активировано!")

# --- СТАРТ И АДМИНКА ---

@dp.message(Command("start"))
async def start(m: types.Message, command: CommandObject):
    async with async_session() as session:
        user = await session.get(User, m.from_user.id)
        if not user:
            user = User(user_id=m.from_user.id, username=m.from_user.first_name)
            if command.args and command.args.isdigit():
                ref_parent = await session.get(User, int(command.args))
                if ref_parent: ref_parent.balance += 2500; user.balance += 2500
            session.add(user); await session.commit()
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔥 ИГРАТЬ", web_app=types.WebAppInfo(url=APP_URL))
    await m.answer("FenixTap: Твой путь к миллионам начался!", reply_markup=kb.as_markup())

async def recovery_loop():
    while True:
        await asyncio.sleep(60)
        async with async_session() as session:
            await session.execute(update(User).where(User.energy < User.max_energy).values(energy=User.energy + 15))
            await session.commit()

@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(dp.start_polling(bot, skip_updates=True))
    asyncio.create_task(recovery_loop())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
