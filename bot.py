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

async def recovery():
    while True:
        await asyncio.sleep(60)
        try:
            async with async_session() as session:
                await session.execute(update(User).where(User.energy < User.max_energy).values(energy=func.least(User.max_energy, User.energy + 25)))
                await session.commit()
        except: pass

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
        if user.is_banned: return {"error": "banned"}
        return {"score": user.balance, "mult": user.tap_power, "auto": user.auto_power, "energy": user.energy, "max_energy": user.max_energy}

@app.get("/get_top")
async def get_top():
    async with async_session() as session:
        res = await session.execute(select(User).order_by(desc(User.balance)).limit(10))
        users = res.scalars().all()
        return [{"username": u.username or f"TapMaster_{str(u.user_id)[-4:]}", "balance": u.balance} for u in users]

@app.post("/s")
async def save(request: Request):
    d = await request.json()
    uid = int(d['id'])
    async with async_session() as session:
        user = await session.get(User, uid)
        if user and not user.is_banned:
            now = int(time.time())
            seconds = max(1, now - user.last_touch)
            # Лимит защиты + запас на эволюцию
            max_gain = (user.tap_power * 18 * seconds) + (user.auto_power * seconds) + 500
            if (int(d['score']) - user.balance) > max_gain:
                return {"ok": False, "error": "security"}
            user.balance, user.energy, user.last_touch = int(d['score']), int(d['energy']), now
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

@app.post("/daily_claim")
async def daily(request: Request):
    d = await request.json()
    async with async_session() as session:
        user = await session.get(User, int(d['id']))
        now = datetime.utcnow()
        delta = (now - (user.last_checkin or (now - timedelta(days=2)))).total_seconds() / 3600
        if delta < 24: return {"status": "error", "message": f"Приходи через {int(24-delta)}ч."}
        user.streak = (user.streak + 1) if delta < 48 else 1
        bonus = min(user.streak * 1500, 10000)
        user.balance += bonus; user.last_checkin = now
        await session.commit()
        return {"status": "ok", "bonus": bonus}

@app.post("/create_miner_invoice")
async def cmi(request: Request):
    d = await request.json()
    p = {"star_mini": ["Птенец-Помощник", 150, 5], "star_mega": ["Король Феникс", 500, 25]}.get(d['type'])
    link = await bot.create_invoice_link(title=p[0], description=f"Автодоход +{p[2]}/с", payload=f"miner_{d['type']}_{d['id']}", provider_token="", currency="XTR", prices=[LabeledPrice(label="Stars", amount=p[1])])
    return {"link": link}

@app.post(WEBHOOK_PATH)
async def webhook(request: Request):
    data = await request.json()
    await dp.feed_update(bot, Update.model_validate(data, context={"bot": bot}))
    return Response(content='ok')

@dp.message(Command("start"))
async def start(m: types.Message, command: CommandObject):
    ref_id = int(command.args) if command.args and command.args.isdigit() else None
    async with async_session() as session:
        user = await session.get(User, m.from_user.id)
        if not user:
            user = User(user_id=m.from_user.id, username=m.from_user.username, referrer_id=ref_id)
            session.add(user)
            if ref_id:
                r = await session.get(User, ref_id)
                if r: r.balance += 5000
            await session.commit()
    builder = InlineKeyboardBuilder().button(text="🔥 ИГРАТЬ", web_app=types.WebAppInfo(url=APP_URL))
    await m.answer("Добро пожаловать в Fenix Tap! Вырасти свою легенду.", reply_markup=builder.as_markup())

@dp.pre_checkout_query()
async def pre(q: PreCheckoutQuery): await q.answer(ok=True)

@dp.message(F.successful_payment)
async def pay_ok(m: types.Message):
    pay = m.successful_payment.invoice_payload.split('_')
    async with async_session() as session:
        user = await session.get(User, int(pay[2]))
        if user:
            power = 5 if pay[1] == "star_mini" else 25
            user.auto_power += power
            await session.commit()

@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        try: await conn.execute(text("ALTER TABLE users ADD COLUMN is_banned BOOLEAN DEFAULT FALSE"))
        except: pass 
        await conn.run_sync(Base.metadata.create_all)
    await bot.set_webhook(url=f"{APP_URL}{WEBHOOK_PATH}", drop_pending_updates=True)
    asyncio.create_task(recovery()); asyncio.create_task(keep_alive())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
